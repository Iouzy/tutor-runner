"""The exercises on disk, and the one button that measures.

Every attempt lands in `telemetria/` by itself. He never has to remember to
record anything — that is the whole reason the button exists instead of a
terminal wrapper he would have to think about.
"""
from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .model import Course, CourseError
from .telemetry import Compilation, extrair_erro, record, hora


@dataclass(frozen=True)
class Attempt:
    """One press of the button: what the machine did, and what it said."""

    comando: str
    compilou: bool
    correu: bool
    saida: str
    erro: str | None

    @property
    def ok(self) -> bool:
        return self.compilou and self.correu and self.erro is None


class Workspace:
    """`exercicios/` is his, not the program's: the files stay put, readable by
    any editor. Whoever prefers o nano continues no nano."""

    def __init__(self, course: Course, workdir: Path) -> None:
        self.course = course
        self.raiz = workdir / "exercicios"
        self.telemetria = workdir / "telemetria"

    def caminho(self, exercicio: str) -> Path:
        nome = Path(exercicio).name
        if nome != exercicio or not nome:
            raise CourseError(
                f"'{exercicio}' não é um nome de ficheiro — os exercícios vivem todos "
                f"em exercicios/, sem subpastas"
            )
        if self.course.extensao and not nome.endswith(self.course.extensao):
            raise CourseError(
                f"'{nome}' não acaba em '{self.course.extensao}' — este curso não lhe pega"
            )
        return self.raiz / nome

    def criar(self, exercicio: str, esqueleto: str = "") -> Path:
        """Never overwrites: his work is the one thing here that cannot be regenerated."""
        alvo = self.caminho(exercicio)
        alvo.parent.mkdir(parents=True, exist_ok=True)
        if not alvo.exists():
            alvo.write_text(esqueleto, encoding="utf-8")
        return alvo

    def _correr(self, comando: str, alvo: Path) -> subprocess.CompletedProcess:
        cmd = comando.format(ficheiro=str(alvo), classe=alvo.stem)
        return subprocess.run(
            shlex.split(cmd), capture_output=True, text=True, cwd=self.raiz, timeout=120
        )

    def tentar(self, node_id: str, exercicio: str) -> Attempt:
        """Build, and run if it built. One press, one line in telemetria/.

        Some languages keep almost all the signal in the run — `py_compile` only
        catches syntax — so the run's error counts as much as the build's.
        """
        alvo = self.caminho(exercicio)
        if not alvo.exists():
            raise CourseError(f"{alvo} não existe — cria o exercício antes de o compilar")

        build = self._correr(self.course.build, alvo)
        comando = self.course.build.format(ficheiro=alvo.name, classe=alvo.stem)
        if build.returncode != 0:
            erro = extrair_erro(build.stderr, self.course.regex_erro).msg
            self._registar(node_id, alvo.name, erro)
            return Attempt(comando, False, False, build.stdout, erro)

        corrida = self._correr(self.course.run, alvo)
        comando = self.course.run.format(ficheiro=alvo.name, classe=alvo.stem)
        erro = None
        if corrida.returncode != 0:
            erro = extrair_erro(corrida.stderr, self.course.regex_erro).msg
        self._registar(node_id, alvo.name, erro)
        return Attempt(comando, True, corrida.returncode == 0, corrida.stdout, erro)

    def _registar(self, node_id: str, ficheiro: str, erro: str | None) -> None:
        record(self.telemetria, Compilation(t=hora(), no=node_id, ficheiro=ficheiro, erro=erro))
