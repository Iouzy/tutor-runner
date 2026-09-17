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
        return self.name.lower().replace("_", " ")


@dataclass(frozen=True)
class Node:
    id: str
    nome: str
    objetivo: str
    depende_de: tuple[str, ...] = ()
    armadilhas: tuple[str, ...] = ()
    treina: tuple[str, ...] = ()


@dataclass(frozen=True)
class Weakness:
    id: str
    nome: str
    descricao: str


@dataclass(frozen=True)
class Course:
    nome: str
    perfil: str
    build: str
    run: str
    regex_erro: str
    nodes: dict[str, Node]
    weaknesses: dict[str, Weakness]
    teto_briefing_bytes: int = 2048
    teto_bilhete_bytes: int = 400
    teto_contexto_kb: float = 15.0
    decaimento_dias: int = 21

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
