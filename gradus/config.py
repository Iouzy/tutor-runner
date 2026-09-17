"""Which course he chose. Written by the program, never edited by hand.

Whoever is learning to program does not edit TOML to say they want Python:
the screen writes this, and everything else reads it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .model import CourseError

FICHEIRO = "gradus.json"


@dataclass
class Config:
    curso: str                       # caminho relativo à raiz, ex.: "cursos/python"
    criado_em: str = ""

    def course_dir(self, raiz: Path) -> Path:
        return raiz / self.curso


def caminho(raiz: Path) -> Path:
    return raiz / FICHEIRO


def load(raiz: Path) -> Config | None:
    alvo = caminho(raiz)
    if not alvo.exists():
        return None
    dados = json.loads(alvo.read_text(encoding="utf-8"))
    if not dados.get("curso"):
        return None
    return Config(curso=dados["curso"], criado_em=dados.get("criado_em", ""))


def save(raiz: Path, config: Config) -> Path:
    alvo = caminho(raiz)
    config.criado_em = config.criado_em or datetime.now().isoformat(timespec="seconds")
    alvo.write_text(
        json.dumps({"curso": config.curso, "criado_em": config.criado_em}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return alvo


@dataclass(frozen=True)
class CursoDisponivel:
    caminho: str
    nome: str
    linguagem: str
    extensao: str


def disponiveis(raiz: Path) -> list[CursoDisponivel]:
    """The cards on the first screen. Reads only the header of each curso.toml."""
    import tomllib

    achados = []
    for toml in sorted((raiz / "cursos").glob("*/curso.toml")):
        try:
            dados = tomllib.loads(toml.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            raise CourseError(f"{toml} não é TOML válido ({exc}) — corre `gradus lint`") from None
        achados.append(CursoDisponivel(
            caminho=str(toml.parent.relative_to(raiz)),
            nome=dados.get("nome", toml.parent.name),
            linguagem=dados.get("linguagem", ""),
            extensao=dados.get("extensao", ""),
        ))
    return achados
