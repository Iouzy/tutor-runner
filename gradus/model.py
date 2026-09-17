"""Domain types. The engine knows about nodes and mastery; never about Java."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class Mastery(IntEnum):
    """The ladder a node climbs. Ordered, so comparisons are the scheduler's rule."""

    POR_TOCAR = 0
    VISTO = 1
    ESCRITO_COM_AJUDA = 2
    ESCRITO_SOZINHO = 3
    AUTOMATICO = 4

    @property
    def label(self) -> str:
        # Escrito como se lê em português: é isto que aparece no ESTADO.md e no ecrã.
        return {Mastery.AUTOMATICO: "automático"}.get(self, self.name.lower().replace("_", " "))


TIPOS_EXERCICIO = ("previsao", "erro-plantado", "construcao", "reescrita", "explicar")

NOMES_TIPO = {
    "previsao": "previsão",
    "erro-plantado": "erro plantado",
    "construcao": "construção",
    "reescrita": "reescrita",
    "explicar": "explicar",
}


@dataclass(frozen=True)
class Anchor:
    """A hand-written exercise, known good. Control values are mandatory: without
    them correctness is a model's opinion, which is how 12550 got accepted once."""

    tipo: str
    enunciado: str
    ficheiro: str = ""
    controlo: tuple[dict[str, str], ...] = ()


@dataclass(frozen=True)
class Node:
    id: str
    nome: str
    objetivo: str
    depende_de: tuple[str, ...] = ()
    armadilhas: tuple[str, ...] = ()
    treina: tuple[str, ...] = ()
    tipos: tuple[str, ...] = ()
    ancoras: tuple[Anchor, ...] = ()


@dataclass(frozen=True)
class Weakness:
    id: str
    nome: str
    descricao: str


@dataclass(frozen=True)
class Verification:
    """A file broken on purpose. `gradus doctor` writes it, builds it, and demands
    that the course's own regex catch the error — otherwise the telemetry records
    raw noise for weeks and nothing ever fails."""

    ficheiro: str
    codigo: str
    espera: str = ""        # a fragment the caught message must contain


@dataclass(frozen=True)
class Course:
    nome: str
    perfil: str
    build: str
    run: str
    regex_erro: str
    nodes: dict[str, Node]
    weaknesses: dict[str, Weakness]
    linguagem: str = ""
    extensao: str = ""
    teto_briefing_bytes: int = 2048
    teto_bilhete_bytes: int = 400
    teto_contexto_kb: float = 15.0
    decaimento_dias: int = 21
    verificacao: Verification | None = None

    def node(self, node_id: str) -> Node:
        try:
            return self.nodes[node_id]
        except KeyError:
            raise CourseError(
                f"o nó '{node_id}' não existe em grafo.toml — "
                f"acrescenta-o, ou corrige quem lhe chama"
            ) from None


class CourseError(Exception):
    """Raised with the fix in the message, never just the symptom."""


@dataclass
class Handoff:
    """The note a dying session leaves. Capped, or it becomes a transcript."""

    onde_ficou: str = ""
    ultimo_erro: str = ""
    ja_explicado: list[str] = field(default_factory=list)
    nao_repetir: str = ""

    def to_json(self) -> str:
        import json

        return json.dumps(
            {
                "onde_ficou": self.onde_ficou,
                "ultimo_erro": self.ultimo_erro,
                "ja_explicado": self.ja_explicado,
                "nao_repetir": self.nao_repetir,
            },
            ensure_ascii=False,
        )
