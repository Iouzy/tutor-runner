"""gradus doctor — the only part of the program that touches the machine.

Every check ends in a command he can paste. The one that matters is the last:
it breaks a file on purpose, builds it, and demands that the course's own regex
catch the error. Without that, `telemetria/` fills up with raw noise for weeks
and nothing ever fails.
"""
from __future__ import annotations

import importlib.util
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .adapter import encontrar
from .model import Course
from .telemetry import extrair_erro

ERRO, AVISO = "erro", "aviso"


@dataclass(frozen=True)
class Check:
    nome: str
    ok: bool
    detalhe: str
    conserto: str = ""
    nivel: str = ERRO


def _python() -> Check:
    v = sys.version_info
    ok = v >= (3, 11)
    return Check(
        "python", ok, f"{v.major}.{v.minor}.{v.micro}",
        "" if ok else "o gradus lê TOML com tomllib, que só existe a partir do 3.11",
    )


def _tkinter() -> Check:
    ok = importlib.util.find_spec("tkinter") is not None
    return Check(
        "tkinter", ok, "presente" if ok else "em falta",
        "" if ok else "sudo apt install python3-tk   (no macOS: brew install python-tk)",
    )


def _binario(campo: str, comando: str, extensao: str) -> Check:
    try:
        primeiro = shlex.split(comando.format(ficheiro="x" + extensao, classe="x"))[0]
    except (ValueError, IndexError, KeyError):
        return Check(campo, False, "o comando não se consegue partir", "corre `gradus lint`")
    caminho = shutil.which(primeiro)
    return Check(
        campo, caminho is not None, caminho or f"'{primeiro}' não está no PATH",
        "" if caminho else f"instala o {primeiro} ou corrige {campo} em curso.toml",
    )


def _claude() -> Check:
    """Sem isto não há sessão nenhuma, por isso é um erro e não um aviso: um
    arranque que diz «0 por resolver» e depois não arranca é pior do que nada."""
    caminho = encontrar("claude")
    return Check(
        "claude", caminho is not None, caminho or "não o encontrei",
        "" if caminho else (
            "instala o Claude Code; se já o tens mas noutro sítio, diz onde: "
            "export GRADUS_CLAUDE=$(command -v claude)"
        ),
    )


def _api_key() -> Check:
    posta = bool(os.environ.get("ANTHROPIC_API_KEY"))
    return Check(
        "ANTHROPIC_API_KEY", not posta, "ausente, como deve ser" if not posta else "está posta",
        "" if not posta else "unset ANTHROPIC_API_KEY — com ela o claude -p gasta a API em vez da subscrição",
    )


def _escrita(workdir: Path) -> Check:
    try:
        workdir.mkdir(parents=True, exist_ok=True)
        alvo = workdir / ".gradus-escrita"
        alvo.write_text("x", encoding="utf-8")
        alvo.unlink()
        return Check("escrita", True, str(workdir))
    except OSError as exc:
        return Check("escrita", False, f"{workdir}: {exc}", "dá permissão de escrita a esta pasta")


def _ficheiro_partido(course: Course) -> Check:
    """The check the whole doctor exists for."""
    nome = "regex_erro"
    v = course.verificacao
    if v is None:
        return Check(
            nome, False, "o curso não traz um ficheiro partido",
            "acrescenta [verificacao] com ficheiro e codigo a curso.toml — sem isso ninguém "
            "garante que o regex apanha seja o que for",
        )
    with tempfile.TemporaryDirectory() as d:
        alvo = Path(d) / v.ficheiro
        alvo.write_text(v.codigo.strip() + "\n", encoding="utf-8")
        cmd = course.build.format(ficheiro=str(alvo), classe=alvo.stem)
        try:
            proc = subprocess.run(
                shlex.split(cmd), capture_output=True, text=True, cwd=d, timeout=120
            )
        except FileNotFoundError:
            return Check(nome, False, "não dá para testar: falta o comando de build", "vê o check acima")
        except subprocess.TimeoutExpired:
            return Check(nome, False, "o build ficou pendurado mais de 2 minutos", "corre-o à mão")

    if proc.returncode == 0:
        return Check(
            nome, False, f"{v.ficheiro} compilou — já não está partido",
            "parte-o outra vez em [verificacao]; um exemplo que compila não prova nada",
        )
    erro = extrair_erro(proc.stderr, course.regex_erro)
    if not erro.pelo_regex:
        return Check(
            nome, False, f"o regex não apanhou nada; a linha crua é: {erro.msg[:70]}",
            "corrige regex_erro em curso.toml até apanhar esta linha, com o grupo (?P<msg>...)",
        )
    if v.espera and v.espera not in erro.msg:
        return Check(
            nome, False, f"apanhou '{erro.msg[:50]}', esperava algo com '{v.espera}'",
            "o regex apanha a linha errada, ou [verificacao].espera está desatualizado",
        )
    return Check(nome, True, f"apanhou: {erro.msg[:70]}")


def run(course: Course, workdir: Path) -> list[Check]:
    return [
        _python(),
        _tkinter(),
        _binario("build", course.build, course.extensao),
        _binario("run", course.run, course.extensao),
        _claude(),
        _api_key(),
        _escrita(workdir),
        _ficheiro_partido(course),
    ]
