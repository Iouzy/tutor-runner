"""Sensors. Everything here is counted by the program; the model never sees it."""
from __future__ import annotations

import json
import re
import shlex
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

CERCA = "```"


@dataclass(frozen=True)
class Compilation:
    t: str
    no: str
    ficheiro: str
    erro: str | None

    @property
    def ok(self) -> bool:
        return self.erro is None


@dataclass(frozen=True)
class Erro:
    msg: str
    pelo_regex: bool        # False: the course's regex missed and this is the raw line


def extrair_erro(stderr: str, regex_erro: str) -> Erro:
    """Normalises what the compiler said, and says whether the regex did the work.

    `gradus doctor` checks that flag against a file broken on purpose: a regex that
    never matches turns weeks of telemetry into noise without ever failing.
    """
    texto = stderr.strip()
    if not texto:
        return Erro("erro sem mensagem", False)
    m = re.search(regex_erro, texto, re.MULTILINE)
    if m and "msg" in (m.groupdict() or {}):
        return Erro(m.group("msg"), True)
    return Erro(texto.splitlines()[0], False)


def record(telemetria: Path, comp: Compilation) -> None:
    telemetria.mkdir(parents=True, exist_ok=True)
    linha = json.dumps(
        {"t": comp.t, "no": comp.no, "ficheiro": comp.ficheiro, "erro": comp.erro}, ensure_ascii=False
    )
    with (telemetria / "compilacoes.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(linha + "\n")


def compile_and_record(telemetria: Path, *, build: str, regex_erro: str, no: str, ficheiro: Path) -> Compilation:
    """The real wrapper: runs the course's own build command and logs what it said.

    This is the cheapest, highest-signal sensor in the system — every attempt is a
    labelled data point, and it costs no tokens because no model is involved.
    """
    cmd = build.format(ficheiro=str(ficheiro), classe=ficheiro.stem)
    proc = subprocess.run(shlex.split(cmd), capture_output=True, text=True)
    erro = extrair_erro(proc.stderr, regex_erro).msg if proc.returncode != 0 else None
    comp = Compilation(
        t=datetime.now().isoformat(timespec="seconds"), no=no, ficheiro=ficheiro.name, erro=erro
    )
    record(telemetria, comp)
    return comp


def count_messages(transcript: list[dict]) -> tuple[int, int]:
    """(mensagens antes do primeiro código dele, mensagens totais).

    Counted from the transcript, never asked of the model at the end of a session —
    a model reconstructing this from memory corrupts the dataset it is meant to build.
    A fenced block in a user turn is what counts as 'he wrote code'.
    """
    total = len(transcript)
    for i, msg in enumerate(transcript):
        if msg.get("papel") == "aluno" and CERCA in msg.get("texto", ""):
            return i, total
    return total, total
