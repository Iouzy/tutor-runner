"""Everything the screens decide, with no tkinter in sight.

The window is a thin layer over this on purpose: a GUI that cannot be tested is
a GUI whose bugs are found by the person trying to learn.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable, Protocol

from .. import (
    briefing as briefing_mod, config as config_mod, course as course_mod,
    simulator as simulator_mod, state as state_mod,
)
from ..loop import Abertura, PassageReport, RawRun, Runner
from ..model import Course, CourseError, Handoff, Node
from ..workspace import Attempt, Workspace


# --- ecrã 2: o perfil ------------------------------------------------------
@dataclass(frozen=True)
class Pergunta:
    id: str
    texto: str
    ajuda: str
    opcoes: tuple[str, ...] = ()        # vazio: caixa de texto


PERGUNTAS = (
    Pergunta(
        "parou",
        "Já tentaste aprender a programar e paraste?",
        "Se sim, o que te fez parar — e em que ponto foi? É a resposta que mais muda "
        "a forma como vais ser ensinado.",
    ),
    Pergunta(
        "encrava",
        "Quando encravas, o que fazes a seguir?",
        "Não há resposta certa. Há a tua.",
        ("Leio mais sobre o assunto", "Pergunto a alguém", "Corro o código a ver o que dá", "Deixo para depois"),
    ),
    Pergunta(
        "percebe",
        "Como percebes melhor uma ideia nova?",
        "",
        ("Com uma analogia", "Com um exemplo a correr", "Com um desenho", "Com a definição exata"),
    ),
    Pergunta(
        "erro",
        "Quando houver um erro à vista, queres uma pista ou a resposta?",
        "",
        ("Uma pista de cada vez", "A resposta, e depois explica"),
    ),
    Pergunta(
        "tempo",
        "Quanto tempo seguido aguentas nisto?",
        "Serve para os exercícios caberem numa sessão tua.",
        ("20 minutos", "45 minutos", "Uma hora e meia", "O tempo que for preciso"),
    ),
    Pergunta(
        "objetivo",
        "O que queres conseguir fazer daqui a três meses?",
        "Concreto: «um programa que me organize os turnos» vale mais do que «saber Java».",
    ),
)

NUCLEO = """## Como ensinar este aluno

Nunca lhe dês código feito, mesmo quando insistir. Dá o objetivo, as peças e
pistas — ele escreve."""

DERIVADAS = {
    "encrava": {
        "Leio mais sobre o assunto": "Quando ele travar, empurra-o a correr o programa, não a mais uma explicação.",
        "Pergunto a alguém": "Diz-lhe quando estiver em loop: várias perguntas sobre o mesmo sem ter escrito uma linha.",
        "Corro o código a ver o que dá": "Ele desbloqueia a executar: manda-o correr cedo e lê com ele o que saiu.",
        "Deixo para depois": "Ele adia a parte difícil. Parte o exercício até a primeira coisa a fazer custar dois minutos.",
    },
    "percebe": {
        "Com uma analogia": "Explica conceitos com analogias.",
        "Com um exemplo a correr": "Explica com um exemplo pequeno que ele possa correr antes de perceber.",
        "Com um desenho": "Marca as peças visualmente em vez de texto corrido.",
        "Com a definição exata": "Dá a definição exata primeiro, curta, e só depois o exemplo.",
    },
    "erro": {
        "Uma pista de cada vez": "Corrige por cima do que ele colar: aponta o erro e a razão, nunca a linha corrigida.",
        "A resposta, e depois explica": "Diz o que está errado sem rodeios, e a seguir porquê. Ele prefere honestidade a encorajamento.",
    },
    "tempo": {
        "20 minutos": "Exercícios de 20 minutos. Se não cabe, parte-o.",
        "45 minutos": "Exercícios de uns 45 minutos. Se não cabe, parte-o.",
        "Uma hora e meia": "Ele aguenta sessões longas, mas não deixes passar meia hora sem código escrito.",
        "O tempo que for preciso": "Ele não se levanta: és tu que tens de o mandar correr o programa e parar.",
    },
}

FECHO = """Não avances de tema porque ele disse que percebeu. Pede-lhe para escrever.

Português de Portugal."""


def perfil_md(respostas: dict[str, str]) -> str:
    """The six answers become the instructions the tutor reads every single time."""
    linhas = [NUCLEO, ""]

    parou = (respostas.get("parou") or "").strip()
    if parou:
        linhas += [f"Já parou antes, nas palavras dele: «{_curto(parou, 220)}»", ""]

    for chave in ("percebe", "erro", "encrava", "tempo"):
        frase = DERIVADAS.get(chave, {}).get((respostas.get(chave) or "").strip())
        if frase:
            linhas += [frase, ""]

    objetivo = (respostas.get("objetivo") or "").strip()
    if objetivo:
        linhas += [f"O que ele quer conseguir fazer: {_curto(objetivo, 140)}. Liga os exercícios a isso quando der.", ""]

    linhas.append(FECHO)
    texto = "\n".join(linhas).strip() + "\n"
    return _caber(texto, briefing_mod.TETO_PERFIL)


def _curto(texto: str, n: int) -> str:
    texto = " ".join(texto.split())
    return texto if len(texto) <= n else texto[: n - 1].rstrip() + "…"


def _caber(texto: str, teto: int) -> str:
    """The profile rides inside every briefing; over its ceiling it stops riding."""
    while len(texto.encode("utf-8")) > teto:
        blocos = [b for b in texto.split("\n\n") if b.strip()]
        if len(blocos) <= 3:
            return texto.encode("utf-8")[: teto - 1].decode("utf-8", "ignore") + "\n"
        blocos.pop(-2)           # o último antes do fecho: o menos essencial
        texto = "\n\n".join(blocos)
    return texto


def guardar_perfil(raiz: Path, respostas: dict[str, str]) -> Path:
    alvo = raiz / "aluno" / "perfil.md"
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(perfil_md(respostas), encoding="utf-8")
    return alvo


# --- ecrã 1: a linguagem ---------------------------------------------------
def escolher_curso(raiz: Path, caminho_curso: str) -> config_mod.Config:
    """The program writes the choice; he never opens a TOML to say he wants Python."""
    if not (raiz / caminho_curso / "curso.toml").exists():
        raise CourseError(f"não há curso em {caminho_curso} — escolhe um dos cartões")
    cfg = config_mod.Config(curso=caminho_curso)
    config_mod.save(raiz, cfg)
    return cfg


# --- o ecrã principal ------------------------------------------------------
class Dialogo(Protocol):
    """What the main screen needs from whoever is on the other side."""

    def abrir(self) -> str: ...
    def dizer(self, texto: str) -> str: ...
    def tentativa(self, attempt: Attempt, codigo: str) -> str: ...
    def deve_cortar(self) -> bool: ...
    def fechar(self, passou: bool) -> RawRun: ...


@dataclass
class Rodape:
    """The bottom bar: what this session is costing, in bytes he can see."""

    no: str
    tipo: str
    exercicio: str
    briefing: str
    fraquezas: list[str]
    kb: float
    teto_kb: float

    @property
    def cheio(self) -> float:
        return min(1.0, self.kb / self.teto_kb) if self.teto_kb else 0.0


class Estudo:
    """One study session: several cold sessions, one exercise each."""

    def __init__(
        self,
        course: Course,
        course_dir: Path,
        workdir: Path,
        dialogo: Callable[[Abertura, str], Dialogo],
        dia: str | None = None,
    ) -> None:
        self.course = course
        self.runner = Runner(course, course_dir, workdir)
        self.workspace = Workspace(course, workdir)
        self.dia = dia or date.today().isoformat()
        self._fazer_dialogo = dialogo
        self.abertura: Abertura | None = None
        self.dialogo: Dialogo | None = None
        self.exercicio: str = ""
        self.bilhete: Handoff | None = None

    # --- ciclo ------------------------------------------------------------
    def comecar(self) -> Abertura | None:
        st = state_mod.load(self.runner.estado_path)
        abertura = self.runner.abrir(self.dia, self.bilhete)
        if abertura is None:
            return None
        self.abertura = abertura
        self.exercicio = st.exercicio_aberto or nome_de_ficheiro(self.course, abertura)
        self.workspace.criar(self.exercicio, esqueleto(self.course, abertura))
        self.dialogo = self._fazer_dialogo(abertura, self.exercicio)
        return abertura

    def primeira_fala(self) -> str:
        return self._exige_dialogo().abrir()

    def enviar(self, texto: str) -> str:
        return self._exige_dialogo().dizer(texto)

    def compilar(self) -> tuple[Attempt, str]:
        """The button: compile, run, record — and tell the tutor what came out."""
        dialogo = self._exige_dialogo()
        attempt = self.workspace.tentar(self.abertura.node.id, self.exercicio)
        codigo = self.caminho_exercicio().read_text(encoding="utf-8")
        resposta = dialogo.tentativa(attempt, codigo)
        return attempt, resposta

    def deve_cortar(self) -> bool:
        return self._exige_dialogo().deve_cortar()

    def terminar(self, passou: bool) -> PassageReport:
        raw = self._exige_dialogo().fechar(passou)
        relatorio = self.runner.fechar(self.abertura, raw, self.dia)
        self.runner.regenerate()
        self.bilhete = None if passou else relatorio.handoff
        self.abertura, self.dialogo = None, None
        return relatorio

    # --- o que o ecrã mostra ----------------------------------------------
    def rodape(self) -> Rodape:
        ab = self.abertura
        st = state_mod.load(self.runner.estado_path)
        ativas = st.fraquezas_ativas(conhecidas=set(self.course.weaknesses))
        return Rodape(
            no=ab.node.nome if ab else "",
            tipo=ab.choice.tipo if ab else "",
            exercicio=self.exercicio,
            briefing=ab.briefing.relatorio() if ab else "",
            fraquezas=[self.course.weaknesses[w].nome for w in ativas],
            kb=round(self.dialogo.kb, 1) if self.dialogo is not None else 0.0,
            teto_kb=self.course.teto_contexto_kb,
        )

    def caminho_exercicio(self) -> Path:
        return self.workspace.caminho(self.exercicio)

    def _exige_dialogo(self) -> Dialogo:
        if self.dialogo is None:
            raise CourseError("não há sessão a decorrer — carrega em Começar")
        return self.dialogo


def nome_de_ficheiro(course: Course, abertura: Abertura) -> str:
    """The anchor's file when there is one; otherwise the node's name, in the shape
    this language needs — Java refuses a class whose file is named otherwise."""
    tipo = abertura.choice.tipo
    ancora = next((a for a in abertura.node.ancoras if a.tipo == tipo and a.ficheiro), None)
    if ancora:
        return ancora.ficheiro
    base = re.sub(r"[^a-z0-9]+", " ", abertura.node.id.lower()).split()
    if course.estilo_ficheiro == "camel":
        return "".join(p.capitalize() for p in base) + course.extensao
    return "_".join(base) + course.extensao


def esqueleto(course: Course, abertura: Abertura) -> str:
    """Comments only. A scaffold is code he did not write, and the profile's first
    rule is that he writes it."""
    marca = "#" if course.extensao in (".py", ".rb", ".sh") else "//"
    linhas = [
        f"{marca} {abertura.node.nome} — {abertura.choice.tipo}",
        f"{marca} {abertura.node.objetivo}",
        f"{marca}",
        f"{marca} escreve aqui. o botão compila e corre, e guarda cada tentativa.",
        "",
    ]
    return "\n".join(linhas)


# --- o simulador -----------------------------------------------------------
@dataclass
class Resultado:
    certo: bool
    certa: str
    promocao: str | None
    seguidas: int
    em_falta: int


class Simulacao:
    """Ten in a row, about his own file. The questions come out of the file and the
    answers out of the machine — the whole point is that nobody's opinion is in it."""

    def __init__(self, course: Course, workdir: Path, node_id: str, exercicio: str,
                 dia: str | None = None) -> None:
        self.course = course
        self.estado_path = workdir / "estado.json"
        self.workspace = Workspace(course, workdir)
        self.node_id = node_id
        self.exercicio = exercicio
        self.dia = dia or date.today().isoformat()
        self.atual: simulator_mod.Previsao | None = None

    def proxima(self) -> simulator_mod.Previsao | None:
        codigo = self.workspace.caminho(self.exercicio).read_text(encoding="utf-8")
        previsoes = simulator_mod.gerar(self.course, self.exercicio, codigo, quantas=1)
        self.atual = previsoes[0] if previsoes else None
        return self.atual

    def responder(self, texto: str) -> Resultado:
        if self.atual is None:
            raise CourseError("não há pergunta na mesa — pede a próxima previsão")
        certo = simulator_mod.acertou(self.atual, texto)
        st = state_mod.load(self.estado_path)
        promocao = simulator_mod.registar(st, self.node_id, certo, date.fromisoformat(self.dia))
        state_mod.save(self.estado_path, st)
        resultado = Resultado(
            certo=certo, certa=self.atual.saida_certa, promocao=promocao,
            seguidas=st.node(self.node_id).previsoes_seguidas,
            em_falta=simulator_mod.em_falta(st, self.node_id),
        )
        self.atual = None
        return resultado
