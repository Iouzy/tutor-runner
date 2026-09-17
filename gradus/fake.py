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

    def __init__(self, beats: list[Beat], inicio: str = "14:02", fraquezas: set[str] | None = None) -> None:
        self.beats = list(beats)
        self.relogio = datetime.fromisoformat(f"2026-09-17T{inicio}:00")
        self._usados: dict[str, int] = {}
        # A real session can only name the weaknesses its briefing named. This day
        # was written for Java; against another course the Java-only ones drop.
        self.fraquezas = fraquezas

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

    def _juizos(self, beat: Beat) -> list[Judgement]:
        juizos = beat.juizos or []
        if self.fraquezas is None:
            return juizos
        return [j for j in juizos if j.fraqueza is None or j.fraqueza in self.fraquezas]

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
            juizos=self._juizos(beat),
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


ABERTURA_SECA = {
    "previsao": "Lê o código do enunciado e diz-me o que achas que ele escreve — antes de o correres.",
    "erro-plantado": "Este programa compila e dá o resultado errado. Lê-o e diz-me onde achas que está o furo.",
    "construcao": "Escreve do zero. Começa pela primeira linha que souberes escrever, mesmo que não seja a primeira do programa.",
    "reescrita": "Pega no que já escreveste e torna-o mais simples, sem mudar o que ele faz.",
    "explicar": "Explica-me o teu código linha a linha. Eu só pergunto.",
}

# A sessão seca não pensa. Estas frases existem para o ciclo poder ser percorrido
# sem gastar uma sessão a sério — e são várias porque uma só, repetida, parece
# uma avaria em vez de um boneco.
RESPOSTAS_SECAS = (
    "Escreve isso no editor e carrega em «Compilar e correr».",
    "Corre outra vez e lê a mensagem do compilador toda, até ao fim.",
    "Não te adianto nada: sou um boneco. Numa sessão a sério é aqui que vinha a pista.",
    "Vai por partes: qual é a primeira linha de que tens a certeza?",
)


class ConversaSeca:
    """A dry stand-in for a real cold session, for trying the interface without
    spending a single one. Same seam as `conversation.Conversa`."""

    def __init__(self, briefing: str, node_id: str, exercicio: str, teto_kb: float = 15.0,
                 tipo: str = "construcao") -> None:
        self.briefing = briefing
        self.node_id = node_id
        self.exercicio = exercicio
        self.teto_kb = teto_kb
        self.tipo = tipo
        self.transcript: list[dict] = []
        self.compilacoes: list[Compilation] = []
        self.inicio = datetime.now()
        self._volta = 0

    def abrir(self) -> str:
        self.transcript.append({"papel": "gradus", "texto": self.briefing})
        return self._responder(
            "(sessão seca: não há modelo nenhum do outro lado, as respostas são fixas)\n"
            + ABERTURA_SECA.get(self.tipo, ABERTURA_SECA["construcao"])
        )

    def dizer(self, texto: str) -> str:
        self.transcript.append({"papel": "aluno", "texto": texto})
        self._volta += 1
        return self._responder(RESPOSTAS_SECAS[self._volta % len(RESPOSTAS_SECAS)])

    def tentativa(self, attempt, codigo: str) -> str:
        self.transcript.append({"papel": "aluno", "texto": f"```\n{codigo.strip()}\n```"})
        self.compilacoes.append(
            Compilation(t=datetime.now().strftime("%H:%M"), no=self.node_id,
                        ficheiro=self.exercicio, erro=attempt.erro)
        )
        self.transcript.append({"papel": "sistema", "texto": attempt.erro or attempt.saida})
        if attempt.erro:
            return self._responder(f"O compilador diz: {attempt.erro}\nOnde é que isso acontece?")
        return self._responder(
            "Correu. Compara o que saiu com o que tinhas previsto — e se bateu certo, "
            "carrega em «Passou»."
        )

    def deve_cortar(self) -> bool:
        return self.kb >= self.teto_kb

    @property
    def kb(self) -> float:
        return sum(len(m["texto"].encode("utf-8")) for m in self.transcript) / 1024

    def fechar(self, passou: bool) -> RawRun:
        return RawRun(
            transcript=list(self.transcript),
            terminal="\n".join(m["texto"] for m in self.transcript if m["papel"] == "sistema"),
            compilacoes=list(self.compilacoes),
            exercicio=self.exercicio,
            passou=passou,
            kb_contexto=round(self.kb, 1),
            duracao_min=max(1, int((datetime.now() - self.inicio).total_seconds() // 60)),
            handoff=None if passou else Handoff(onde_ficou="sessão seca", ultimo_erro="", ja_explicado=[]),
            juizos=[],          # uma sessão seca não declara nada: ninguém observou nada
            duvidas_novas=[],
            ja_registadas=True,
        )

    def _responder(self, texto: str) -> str:
        self.transcript.append({"papel": "gradus", "texto": texto})
        return texto
