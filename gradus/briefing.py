"""Assembles the ~2 KB a cold session gets. Everything else is deliberately absent."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .model import Course, CourseError, Handoff, Node
from .state import State

# The only paths a briefing may ever draw from. The archive is not here, and a
# test asserts it never will be: that omission is the whole context economy.
FONTES_PERMITIDAS = ("perfil.md", "grafo.toml", "curso.toml", "estado.json", "telemetria/")


@dataclass
class Slot:
    nome: str
    texto: str
    teto: int

    @property
    def bytes(self) -> int:
        return len(self.texto.encode("utf-8"))


@dataclass
class Briefing:
    slots: list[Slot] = field(default_factory=list)
    teto_total: int = 2048

    @property
    def texto(self) -> str:
        return "\n\n".join(s.texto for s in self.slots if s.texto)

    @property
    def bytes(self) -> int:
        return len(self.texto.encode("utf-8"))

    def relatorio(self) -> str:
        partes = " · ".join(f"{s.nome} {s.bytes}" for s in self.slots if s.texto)
        return f"{self.bytes} B  [{partes}]"

    def check(self) -> None:
        """Fail loudly: a briefing over budget is the one bug that hides itself."""
        for s in self.slots:
            if s.bytes > s.teto:
                raise CourseError(
                    f"o slot '{s.nome}' tem {s.bytes} B e o teto é {s.teto} B — "
                    f"encurta a fonte, não subas o teto sem pensar"
                )
        if self.bytes > self.teto_total:
            raise CourseError(
                f"briefing com {self.bytes} B, teto {self.teto_total} B — "
                f"corta um slot ou baixa o nº de erros recentes incluídos"
            )


def _erros_recentes(telemetria: Path, node_id: str, limite: int = 3) -> list[str]:
    """The highest-value bytes in the whole briefing: his own last mistakes, raw."""
    import json

    ficheiro = telemetria / "compilacoes.jsonl"
    if not ficheiro.exists():
        return []
    linhas = []
    for linha in ficheiro.read_text(encoding="utf-8").splitlines():
        if not linha.strip():
            continue
        reg = json.loads(linha)
        if reg.get("no") == node_id and reg.get("erro"):
            linhas.append(f"{reg['ficheiro']}: {reg['erro']}")
    return linhas[-limite:]


def build(
    course: Course,
    state: State,
    node: Node,
    *,
    telemetria: Path,
    handoff: Handoff | None = None,
    revisao: bool = False,
) -> Briefing:
    perfil = Slot("perfil", course.perfil, teto=1100)

    cabecalho = "REVISÃO (já esteve automático)" if revisao else "EXERCÍCIO"
    linhas = [f"## {cabecalho}: {node.nome}", f"Objetivo: {node.objetivo}"]
    if node.armadilhas:
        linhas.append("Armadilhas: " + "; ".join(node.armadilhas))
    no_slot = Slot("nó", "\n".join(linhas), teto=500)

    ativas = state.fraquezas_ativas()
    if ativas:
        corpo = ["## Fraquezas ativas — mete-as no exercício se fizer sentido"]
        corpo += [f"- {course.weaknesses[w].nome}: {course.weaknesses[w].descricao}" for w in ativas]
        fraquezas = Slot("fraquezas", "\n".join(corpo), teto=400)
    else:
        fraquezas = Slot("fraquezas", "", teto=400)

    erros = _erros_recentes(telemetria, node.id)
    if erros:
        corpo = ["## Últimos erros dele neste tópico (em bruto)"] + [f"- {e}" for e in erros]
        erros_slot = Slot("erros", "\n".join(corpo), teto=450)
    else:
        erros_slot = Slot("erros", "", teto=450)

    slots = [perfil, no_slot, fraquezas, erros_slot]

    if handoff is not None:
        corpo = [
            "## Retoma (a passagem anterior foi cortada a meio)",
            f"- onde ficou: {handoff.onde_ficou}",
            f"- último erro: {handoff.ultimo_erro}",
            f"- já explicado, não repitas: {', '.join(handoff.ja_explicado)}",
        ]
        if handoff.nao_repetir:
            corpo.append(f"- evita: {handoff.nao_repetir}")
        slots.append(Slot("bilhete", "\n".join(corpo), teto=course.teto_bilhete_bytes + 120))

    briefing = Briefing(slots=slots, teto_total=course.teto_briefing_bytes)
    briefing.check()
    return briefing
