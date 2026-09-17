"""The contract between the two halves: measured facts, declared judgements."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

CAMPOS_JUIZO = {"fraqueza", "tipo_duvida", "dominio_atingido"}
TIPOS_DUVIDA = {"conceito", "sintaxe", "ferramenta"}


class EventError(Exception):
    """A malformed event is rejected and nothing is committed. Never patched silently."""


@dataclass
class Judgement:
    """What only the model can know. Everything else is counted, not asked."""

    fraqueza: str | None = None
    tipo_duvida: str | None = None
    resolvido_na_passagem: bool = False


@dataclass
class Passage:
    id: str
    dia: str
    no: str
    exercicio: str
    resultado: str                       # "passou" | "cortado" | "abandonado"
    # --- measured by the program ---
    duracao_min: int = 0
    compilacoes: int = 0
    versoes_ate_correr: int = 0
    msgs_antes_do_1o_codigo: int = 0
    msgs_total: int = 0
    kb_contexto: float = 0.0
    briefing_bytes: int = 0
    motivo_corte: str = ""
    # --- declared by the model ---
    juizos: list[Judgement] = field(default_factory=list)
    duvidas_novas: list[str] = field(default_factory=list)

    RESULTADOS = ("passou", "cortado", "abandonado")

    def validate(self, fraquezas_validas: set[str]) -> None:
        if self.resultado not in self.RESULTADOS:
            raise EventError(
                f"resultado '{self.resultado}' inválido — usa um de {', '.join(self.RESULTADOS)}"
            )
        if self.resultado == "cortado" and not self.motivo_corte:
            raise EventError("uma passagem cortada tem de dizer motivo_corte — o programa sabe qual foi")
        if self.msgs_antes_do_1o_codigo > self.msgs_total:
            raise EventError(
                "msgs_antes_do_1o_codigo é maior que msgs_total — "
                "estes dois números são contados, não estimados: verifica o parser"
            )
        for j in self.juizos:
            if j.fraqueza is not None and j.fraqueza not in fraquezas_validas:
                raise EventError(
                    f"fraqueza '{j.fraqueza}' não está declarada em curso.toml — "
                    f"o modelo não pode inventar categorias novas"
                )
            if j.tipo_duvida is not None and j.tipo_duvida not in TIPOS_DUVIDA:
                raise EventError(
                    f"tipo_duvida '{j.tipo_duvida}' inválido — usa um de {', '.join(sorted(TIPOS_DUVIDA))}"
                )

    @property
    def racio_adiamento(self) -> str:
        if not self.msgs_total:
            return "-"
        return f"{self.msgs_antes_do_1o_codigo}/{self.msgs_total}"


def write(path: Path, passage: Passage) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(passage), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_all(directory: Path) -> list[Passage]:
    passagens = []
    for f in sorted(directory.glob("*.json")):
        raw = json.loads(f.read_text(encoding="utf-8"))
        raw["juizos"] = [Judgement(**j) for j in raw.get("juizos", [])]
        passagens.append(Passage(**raw))
    return passagens
