"""One exercise, one cold session, from the briefing to the RawRun.

This is the seam the interface drives: the human talks, the program compiles,
and everything countable is counted here — never asked of the model at the end.
The model is asked exactly two things, and only things it alone can know: which
weakness caused the error, and what the note for the next passage should say.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime

from .adapter import Claude, ClaudeError, Resposta
from .event import TIPOS_DUVIDA, Judgement
from .loop import RawRun
from .model import Course, Handoff
from .telemetry import Compilation, hora
from .workspace import Attempt

# The session mechanics. The pedagogy is in the briefing (perfil.md); this says
# only what is true about the room the session is in.
REGRAS = """És o gradus a dar uma aula de programação, em português de Portugal.

Como isto funciona:
- Ele escreve o código no editor ao lado, não no chat. Tu nunca escreves o código dele.
- Não tens ferramentas nem corres nada. Quem compila é o programa: o resultado do
  compilador chega-te como uma mensagem que começa por «compilador:».
- Uma mensagem de cada vez, curta. Sem listas longas, sem resumos do que já disseste.
- Esta sessão morre no fim deste exercício. Não prometas nada para depois.
- Nunca lhe peças contagens, nem faças o balanço da sessão: isso é medido pelo programa."""

ARRANQUE = (
    "Começa. Apresenta-lhe o exercício em poucas linhas, no tipo que o briefing pede, "
    "e dá-lhe a primeira coisa concreta para fazer."
)

PEDIDO_JUIZOS = """Acabou. Responde só com JSON, sem mais nada:
{"juizos": [{"fraqueza": "<id ou null>", "tipo_duvida": "conceito|sintaxe|ferramenta|null",
"resolvido_na_passagem": true|false}], "duvidas_novas": ["..."]}
As fraquezas só podem ser destes ids: %s
Nada de contagens nem de números: isso é do programa."""

PEDIDO_BILHETE = """Foi preciso cortar a meio. Deixa o bilhete para a próxima sessão, que
não vai ver nada disto. Só JSON, sem mais nada, e curto:
{"onde_ficou": "...", "ultimo_erro": "...", "ja_explicado": ["..."], "nao_repetir": "..."}"""


def _json_de(texto: str) -> dict:
    """The model answers in prose more often than it admits. Take the first object."""
    m = re.search(r"\{.*\}", texto, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


@dataclass
class Conversa:
    """Stateless about the past by design: it knows this exercise and nothing else."""

    course: Course
    claude: Claude
    node_id: str
    tipo: str
    briefing: str
    exercicio: str
    transcript: list[dict] = field(default_factory=list)
    compilacoes: list[Compilation] = field(default_factory=list)
    sessao: str | None = None
    tokens: int = 0
    custo_usd: float = 0.0
    inicio: datetime = field(default_factory=datetime.now)

    # --- what the interface calls ----------------------------------------
    def abrir(self) -> str:
        sistema = f"{REGRAS}\n\n{self.briefing}"
        self.transcript.append({"papel": "gradus", "texto": sistema})
        return self._guardar(self.claude.arrancar(sistema, ARRANQUE))

    def dizer(self, texto: str) -> str:
        self.transcript.append({"papel": "aluno", "texto": texto})
        return self._guardar(self._continuar(texto))

    def tentativa(self, attempt: Attempt, codigo: str) -> str:
        """The compiler's turn. His code goes in fenced, because that is what he
        wrote — the counter that measures postponement looks for exactly that."""
        self.transcript.append({"papel": "aluno", "texto": f"```\n{codigo.strip()}\n```"})
        self.compilacoes.append(
            Compilation(t=hora(), no=self.node_id, ficheiro=self.exercicio, erro=attempt.erro)
        )
        if attempt.erro:
            corpo = f"compilador: {attempt.comando}\n{attempt.erro}"
        else:
            corpo = f"compilador: {attempt.comando}\nsem erros. saída:\n{attempt.saida.strip()}"
        self.transcript.append({"papel": "sistema", "texto": corpo})
        return self._guardar(self._continuar(corpo))

    # --- the two things only the model knows ------------------------------
    def pedir_juizos(self) -> tuple[list[Judgement], list[str]]:
        ids = ", ".join(sorted(self.course.weaknesses)) or "nenhum"
        try:
            resposta = self._continuar(PEDIDO_JUIZOS % ids)
        except ClaudeError:
            return [], []          # a lost judgement is a gap; a lost passage is worse
        dados = _json_de(resposta.texto)
        juizos = []
        for cru in dados.get("juizos", [])[:5]:
            if not isinstance(cru, dict):
                continue
            fraqueza = cru.get("fraqueza")
            tipo = cru.get("tipo_duvida")
            juizos.append(Judgement(
                fraqueza=fraqueza if fraqueza in self.course.weaknesses else None,
                tipo_duvida=tipo if tipo in TIPOS_DUVIDA else None,
                resolvido_na_passagem=bool(cru.get("resolvido_na_passagem")),
            ))
        duvidas = [str(d)[:120] for d in dados.get("duvidas_novas", [])[:5] if d]
        return juizos, duvidas

    def pedir_bilhete(self) -> Handoff | None:
        try:
            resposta = self._continuar(PEDIDO_BILHETE)
        except ClaudeError:
            return None
        dados = _json_de(resposta.texto)
        if not dados:
            return None
        bilhete = Handoff(
            onde_ficou=str(dados.get("onde_ficou", ""))[:200],
            ultimo_erro=str(dados.get("ultimo_erro", ""))[:200],
            ja_explicado=[str(x)[:60] for x in dados.get("ja_explicado", [])[:6]],
            nao_repetir=str(dados.get("nao_repetir", ""))[:120],
        )
        return _encolher(bilhete, self.course.teto_bilhete_bytes)

    # --- what the runner needs -------------------------------------------
    @property
    def kb(self) -> float:
        bytes_ = sum(len(m.get("texto", "").encode("utf-8")) for m in self.transcript)
        return bytes_ / 1024

    def deve_cortar(self) -> bool:
        return self.kb >= self.course.teto_contexto_kb

    def fechar(self, passou: bool) -> RawRun:
        juizos, duvidas = self.pedir_juizos()
        bilhete = None if passou else self.pedir_bilhete()
        terminal = "\n".join(m["texto"] for m in self.transcript if m["papel"] == "sistema")
        return RawRun(
            transcript=list(self.transcript),
            terminal=terminal,
            compilacoes=list(self.compilacoes),
            exercicio=self.exercicio,
            passou=passou,
            kb_contexto=round(self.kb, 1),
            duracao_min=max(1, int((datetime.now() - self.inicio).total_seconds() // 60)),
            handoff=bilhete,
            juizos=juizos,
            duvidas_novas=duvidas,
            ja_registadas=True,
            tokens=self.tokens,
            custo_usd=round(self.custo_usd, 4),
        )

    # --- process ----------------------------------------------------------
    def _continuar(self, mensagem: str) -> Resposta:
        if self.sessao is None:
            raise ClaudeError("a conversa ainda não foi aberta — chama abrir() primeiro")
        return self.claude.continuar(self.sessao, mensagem)

    def _guardar(self, resposta: Resposta) -> str:
        self.sessao = resposta.sessao or self.sessao
        self.tokens += resposta.tokens_entrada + resposta.tokens_saida
        self.custo_usd += resposta.custo_usd
        self.transcript.append({"papel": "gradus", "texto": resposta.texto})
        return resposta.texto


def _encolher(bilhete: Handoff, teto: int) -> Handoff:
    """A note that outgrows its cap is a transcript. Cut the softest field first."""
    while len(bilhete.to_json().encode("utf-8")) > teto and bilhete.ja_explicado:
        bilhete.ja_explicado.pop()
    if len(bilhete.to_json().encode("utf-8")) > teto:
        bilhete.nao_repetir = ""
    if len(bilhete.to_json().encode("utf-8")) > teto:
        bilhete.onde_ficou = bilhete.onde_ficou[:120]
        bilhete.ultimo_erro = bilhete.ultimo_erro[:80]
    return bilhete
