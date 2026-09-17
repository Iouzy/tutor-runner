"""A scripted stand-in for a real cold session.

Nothing in tests/ or in `gradus demo` may need credentials, a network or a real
`claude` binary. This fake produces raw material only — transcripts, compiler
output, and the handful of judgements a model would declare — so the runner's
measuring code is the same code that runs for real.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from .event import Judgement
from .loop import RawRun
from .model import Handoff
from .telemetry import Compilation


EXERCICIOS = {
    "base-entrada": ["PedeIdade.java", "PedeIdade.java"],
    "base-listas": ["MediaArray.java", "MediaArray.java", "MaiorArray.java"],
    "base-escolha": ["MenuNotas.java"],
    "base-objetos": ["ContaSimples.java"],
    "base-funcoes": ["Conversor.java"],
}


@dataclass
class Beat:
    passou: bool
    kb_contexto: float
    duracao_min: int
    perguntas: int          # aluno messages before he writes any code
    trocas: int             # exchanges after the first code block
    erros: list[str]
    handoff: Handoff | None = None
    juizos: list[Judgement] = None
    duvidas: list[str] = None


class ScriptedSession:
    """Plays a fixed study day so the cycle can be watched end to end."""

    def __init__(self, beats: list[Beat], inicio: str = "14:02") -> None:
        self.beats = list(beats)
        self.relogio = datetime.fromisoformat(f"2026-09-17T{inicio}:00")
        self._usados: dict[str, int] = {}

    def _exercicio(self, node_id: str, retoma: Handoff | None, briefing: str = "") -> str:
        # A real session would use the anchor the briefing names; this one does too,
        # so the demo shows the anchor actually arriving.
        ancora = re.search(r"Âncora \(([^)]+)\):", briefing)
        if ancora and retoma is None:
            return ancora.group(1)
        nomes = EXERCICIOS.get(node_id, [f"{node_id}.java"])
        i = self._usados.get(node_id, 0)
        if retoma is None:
            i = min(i + 1, len(nomes) - 1) if node_id in self._usados else 0
            self._usados[node_id] = i
        return nomes[self._usados.get(node_id, 0)]

    def run(self, texto_briefing: str, node_id: str, retoma: Handoff | None) -> RawRun:
        beat = self.beats.pop(0)
        exercicio = self._exercicio(node_id, retoma, texto_briefing)
        transcript: list[dict] = [{"papel": "gradus", "texto": texto_briefing[:200] + " …"}]

        for i in range(beat.perguntas):
            transcript.append({"papel": "aluno", "texto": f"pergunta {i + 1} sobre {node_id}"})
            transcript.append({"papel": "gradus", "texto": "pista, sem código feito"})

        transcript.append({"papel": "aluno", "texto": "```java\n// primeira tentativa\n```"})

        compilacoes: list[Compilation] = []
        for erro in beat.erros:
            self.relogio += timedelta(minutes=4)
            compilacoes.append(
                Compilation(
                    t=self.relogio.strftime("%H:%M"),
                    no=node_id,
                    ficheiro=exercicio,
                    erro=erro or None,
                )
            )
            transcript.append({"papel": "gradus", "texto": "aponta o erro e a razão"})
            transcript.append({"papel": "aluno", "texto": "```java\n// outra versão\n```"})

        for _ in range(beat.trocas):
            transcript.append({"papel": "gradus", "texto": "e agora corre-o"})
            transcript.append({"papel": "aluno", "texto": "corri"})

        terminal = "\n".join(
            f"$ javac -d out {exercicio}\n{c.erro or ''}".rstrip() for c in compilacoes
        )

        return RawRun(
            transcript=transcript,
            terminal=terminal,
            compilacoes=compilacoes,
            exercicio=exercicio,
            passou=beat.passou,
            kb_contexto=beat.kb_contexto,
            duracao_min=beat.duracao_min,
            handoff=beat.handoff,
            juizos=beat.juizos or [],
            duvidas_novas=beat.duvidas or [],
        )


DIA_TIPO = [
    Beat(
        passou=False,
        kb_contexto=15.2,
        duracao_min=31,
        perguntas=4,
        trocas=2,
        erros=["cannot find symbol: soma", "incompatible types: double cannot be converted to int"],
        handoff=Handoff(
            onde_ficou="tem o for escrito, falta o acumulador",
            ultimo_erro="incompatible types: double cannot be converted to int",
            ja_explicado=["for-each", "âmbito do bloco"],
            nao_repetir="analogia da prateleira",
        ),
        juizos=[Judgement(fraqueza="limites-ciclos", tipo_duvida="conceito")],
        duvidas=["for-each vs for com índice"],
    ),
    Beat(
        passou=True,
        kb_contexto=4.8,
        duracao_min=18,
        perguntas=1,
        trocas=1,
        erros=["array index out of bounds: 5", ""],
        juizos=[Judgement(fraqueza="limites-ciclos", tipo_duvida="sintaxe", resolvido_na_passagem=True)],
    ),
    Beat(
        passou=True,
        kb_contexto=5.1,
        duracao_min=22,
        perguntas=2,
        trocas=1,
        erros=["cannot find symbol: lenght", ""],
        juizos=[Judgement(fraqueza="limites-ciclos", tipo_duvida="sintaxe")],
        duvidas=["length é campo ou método?"],
    ),
    Beat(
        passou=True,
        kb_contexto=5.6,
        duracao_min=26,
        perguntas=3,
        trocas=2,
        erros=["", ],
        juizos=[Judgement(fraqueza="encapsulamento-furado", tipo_duvida="conceito")],
    ),
    Beat(
        passou=True,
        kb_contexto=4.4,
        duracao_min=19,
        perguntas=1,
        trocas=1,
        erros=["", ],
        juizos=[Judgement(fraqueza="buffer-scanner", tipo_duvida="sintaxe", resolvido_na_passagem=True)],
    ),
]
