"""Records everything, verbatim. Nothing reads it back — that is the point."""
from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path

from .event import Passage

# Redaction happens before anything touches disk: a secret in a pushed transcript
# is cheap to prevent and impossible to take back.
PADROES_SEGREDO = [
    re.compile(r"gh[pousr]_[A-Za-z0-9]{16,}"),
    re.compile(r"sk-[A-Za-z0-9\-_]{16,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]{16,}"),
    re.compile(r"(?i)(api[_-]?key|token|password|senha)\s*[:=]\s*\S+"),
]


def redact(texto: str) -> str:
    for padrao in PADROES_SEGREDO:
        texto = padrao.sub("[REDIGIDO]", texto)
    return texto


def store(arquivo: Path, dia: str, passage: Passage, transcript: list[dict], terminal: str) -> Path:
    """Raw first, rendered second. Never keep only the pretty version."""
    dest = arquivo / dia
    dest.mkdir(parents=True, exist_ok=True)
    base = f"{passage.id}-{passage.no}"

    cru = dest / f"{base}.jsonl"
    with cru.open("w", encoding="utf-8") as fh:
        for msg in transcript:
            fh.write(json.dumps({**msg, "texto": redact(msg.get("texto", ""))}, ensure_ascii=False) + "\n")

    (dest / f"{base}.terminal").write_text(redact(terminal), encoding="utf-8")
    (dest / f"{base}.md").write_text(_render(passage, transcript), encoding="utf-8")

    # The join: raw text, statistics and compilations share one id.
    manifesto = {
        "id": passage.id,
        "no": passage.no,
        "exercicio": passage.exercicio,
        "resultado": passage.resultado,
        "fraquezas": [j.fraqueza for j in passage.juizos if j.fraqueza],
        "compilacoes": passage.compilacoes,
        "kb_contexto": passage.kb_contexto,
        "cru": cru.name,
        "linhas": len(transcript),
    }
    indice = dest / "estudo.json"
    existente = json.loads(indice.read_text(encoding="utf-8")) if indice.exists() else {"dia": dia, "passagens": []}
    existente["passagens"] = [p for p in existente["passagens"] if p["id"] != passage.id] + [manifesto]
    indice.write_text(json.dumps(existente, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return cru


def _render(passage: Passage, transcript: list[dict]) -> str:
    linhas = [f"# {passage.id} — {passage.no}", "", f"Resultado: {passage.resultado}", ""]
    for msg in transcript:
        quem = "Leonardo" if msg.get("papel") == "aluno" else "gradus"
        linhas += [f"**{quem}:** {redact(msg.get('texto', ''))}", ""]
    return "\n".join(linhas)


def leitura_permitida(caminho: str, permitidas: tuple[str, ...]) -> bool:
    """Used by the briefing assembler. The archive is absent from `permitidas`
    on purpose, and tests/test_guard.py fails if it ever stops being."""
    return any(caminho.startswith(p) for p in permitidas)
