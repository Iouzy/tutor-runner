"""A aplicação de secretária. tkinter, biblioteca padrão, sem dependências.

Thin on purpose: every decision lives in `controller.py`, which has no tkinter
in it and is tested headless. What is left here is layout, colour, and the one
thing a window must get right — never freezing while a session thinks.
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from tkinter import messagebox

from .. import config as config_mod, course as course_mod, doctor as doctor_mod
from ..adapter import Claude
from ..conversation import Conversa
from ..fake import ConversaSeca
from ..model import NOMES_TIPO, CourseError
from . import pecas, tema
from .controller import PERGUNTAS, Estudo, Simulacao, escolher_curso, guardar_perfil

MARGEM = 36


class App(tk.Tk):
    """Uma janela, quatro ecrãs: três de arranque e o do estudo."""

    def __init__(self, raiz: Path, trabalho: Path | None = None, seco: bool = False) -> None:
        super().__init__()
        self.raiz = raiz
        self.trabalho_raiz = trabalho
        self.seco = seco
        self.title("gradus")
        self.geometry("1280x860")
        self.minsize(1100, 720)
        self.configure(bg=tema.FUNDO)
        self.respostas: dict[str, str] = {}
        self.config_atual = config_mod.load(raiz)
        self.fontes_em_falta = _fixar_fontes(self)
        self.container = tk.Frame(self, bg=tema.FUNDO)
        self.container.pack(fill="both", expand=True)
        self.mostrar(EcraLinguagem if self.config_atual is None else EcraEstudo)

    def mostrar(self, classe, **kw) -> None:
        for filho in self.container.winfo_children():
            filho.destroy()
        classe(self.container, self, **kw).pack(fill="both", expand=True)

    # --- work off the main loop ------------------------------------------
    def em_fundo(self, funcao, quando_acabar) -> None:
        """tkinter has one thread. A session that thinks for twenty seconds must
        not be the reason the window stops repainting."""
        caixa: queue.Queue = queue.Queue(maxsize=1)

        def correr() -> None:
            try:
                caixa.put(("ok", funcao()))
            except Exception as exc:                  # noqa: BLE001 - vai para o ecrã
                caixa.put(("erro", exc))

        threading.Thread(target=correr, daemon=True).start()

        def espreitar() -> None:
            try:
                estado, valor = caixa.get_nowait()
            except queue.Empty:
                self.after(100, espreitar)
                return
            if estado == "erro":
                messagebox.showerror("gradus", str(valor))
                quando_acabar(None)
            else:
                quando_acabar(valor)

        self.after(100, espreitar)

    def curso(self):
        cfg = self.config_atual or config_mod.load(self.raiz)
        if cfg is None:
            raise CourseError("ainda não há curso escolhido — passa pelo primeiro ecrã")
        return course_mod.load(cfg.course_dir(self.raiz)), cfg.course_dir(self.raiz)

    def trabalho(self, course_dir: Path) -> Path:
        return self.trabalho_raiz or (self.raiz / "trabalho" / course_dir.name)


def _fixar_fontes(root: tk.Misc) -> list[str]:
    existentes = set(tkfont.families(root))
    em_falta = tema.em_falta(existentes)
    for pedida in list(tema.ALTERNATIVAS):
        tema.ALTERNATIVAS[pedida] = (tema.familia_disponivel(pedida, existentes),)
    return em_falta


def topo(pai, passo: int | None = None, direita: str = "") -> tk.Frame:
    """A mesma barra em todos os ecrãs, com a linha por baixo: sem ela cada ecrã
    parece uma aplicação diferente."""
    fora = tk.Frame(pai, bg=tema.FUNDO)
    linha = tk.Frame(fora, bg=tema.FUNDO)
    linha.pack(fill="x", padx=MARGEM, pady=(20, 16))
    tk.Label(
        linha, text="gradus", bg=tema.FUNDO, fg=tema.TEXTO, font=pecas.fonte(tema.TITULO)
    ).pack(side="left")
    tk.Frame(linha, bg=tema.LINHA, width=1, height=20).pack(side="left", padx=14, pady=2)
    if passo is not None:
        pecas.paragrafo(linha, f"arranque · passo {passo} de 3").pack(side="left")
        pecas.Passos(linha, passo).pack(side="right")
    elif direita:
        pecas.paragrafo(linha, direita, largura=900).pack(side="left")
    pecas.separador(fora).pack(fill="x")
    return fora


def rodape(pai) -> tuple[tk.Frame, tk.Frame]:
    """A barra de baixo, com a linha por cima. Devolve a moldura e onde pôr coisas."""
    fora = tk.Frame(pai, bg=tema.FUNDO)
    pecas.separador(fora).pack(fill="x")
    dentro = tk.Frame(fora, bg=tema.FUNDO)
    dentro.pack(fill="x", padx=MARGEM, pady=18)
    return fora, dentro


# --- ecrã 1: a linguagem ---------------------------------------------------
class EcraLinguagem(tk.Frame):
    def __init__(self, pai, app: App) -> None:
        super().__init__(pai, bg=tema.FUNDO)
        self.app = app
        topo(self, 1).pack(fill="x")

        corpo = tk.Frame(self, bg=tema.FUNDO)
        corpo.pack(fill="both", expand=True, padx=MARGEM)
        pecas.titulo(corpo, "Que linguagem queres aprender?", "grande").pack(fill="x", pady=(40, 10))
        pecas.paragrafo(
            corpo,
            "Escolhes aqui, e podes trocar depois. O programa trata do resto — "
            "não há um único ficheiro para editares.",
            largura=760,
        ).pack(fill="x")

        cartoes = tk.Frame(corpo, bg=tema.FUNDO)
        cartoes.pack(fill="x", pady=32, anchor="w")
        for disponivel in config_mod.disponiveis(app.raiz):
            self._cartao(cartoes, disponivel).pack(side="left", padx=(0, 18), anchor="n")

        pecas.paragrafo(
            corpo,
            "A seguir: seis perguntas sobre ti, e uma verificação da máquina. "
            "Dois minutos, e não voltas a ver isto.",
            fonte_=tema.PEQUENO, largura=760,
        ).pack(fill="x")

        pecas.espaco(corpo).pack(fill="both", expand=True)
        if app.fontes_em_falta:
            self._aviso_fontes(corpo).pack(fill="x", pady=(0, 24))

    def _cartao(self, pai, disponivel):
        caixa = pecas.cartao(pai)
        dentro = tk.Frame(caixa, bg=tema.PAINEL)
        dentro.pack(fill="both", expand=True, padx=26, pady=24)
        dentro.config(width=260)
        dentro.pack_propagate(False)
        pecas.rotulo(dentro, disponivel.linguagem or "curso").pack(fill="x")
        pecas.titulo(dentro, disponivel.nome, "medio").pack(fill="x", pady=(8, 8))
        pecas.paragrafo(dentro, disponivel.resumo, fonte_=tema.PEQUENO, largura=230).pack(fill="x")
        pecas.espaco(dentro).pack(fill="both", expand=True)
        pecas.mono(dentro, disponivel.build.replace(" {ficheiro}", "")).pack(fill="x", pady=(0, 14))
        pecas.Botao(
            dentro, "Escolher", lambda: self._escolher(disponivel.caminho), papel="principal"
        ).pack(anchor="w")
        dentro.config(height=250)
        return caixa

    def _aviso_fontes(self, pai):
        caixa = pecas.cartao(pai)
        dentro = tk.Frame(caixa, bg=tema.PAINEL)
        dentro.pack(fill="x", padx=20, pady=16)
        pecas.paragrafo(
            dentro,
            "Faltam as fontes do desenho, por isso isto está com a fonte do sistema. "
            "Para ficar como deve ser:",
            largura=900,
        ).pack(fill="x")
        pacotes = " ".join(tema.PACOTES[f] for f in self.app.fontes_em_falta if f in tema.PACOTES)
        pecas.mono(dentro, f"sudo apt install {pacotes}", cor=tema.TEXTO).pack(fill="x", pady=(8, 0))
        return caixa

    def _escolher(self, caminho: str) -> None:
        self.app.config_atual = escolher_curso(self.app.raiz, caminho)
        self.app.mostrar(EcraPerfil)


# --- ecrã 2: o perfil ------------------------------------------------------
class EcraPerfil(tk.Frame):
    """Rail à esquerda com as seis, a pergunta à direita. Sem o rail ele não sabe
    onde está nem quanto falta, e o ecrã fica um vazio com um título."""

    def __init__(self, pai, app: App, indice: int = 0) -> None:
        super().__init__(pai, bg=tema.FUNDO)
        self.app = app
        self.indice = indice
        self.pergunta = PERGUNTAS[indice]

        topo(self, 2).pack(fill="x")
        fora, dentro = rodape(self)
        fora.pack(fill="x", side="bottom")
        corpo = tk.Frame(self, bg=tema.FUNDO)
        corpo.pack(fill="both", expand=True)
        self._rail(corpo).pack(side="left", fill="y")
        pecas.separador(corpo).pack(side="left", fill="y")
        self._pergunta(corpo).pack(side="left", fill="both", expand=True)
        if indice:
            pecas.Botao(dentro, "Anterior", self._anterior).pack(side="left")
        pecas.paragrafo(dentro, "Podes mudar tudo isto depois, em Perfil.").pack(side="left", padx=16)
        pecas.Botao(
            dentro, "Seguinte" if indice + 1 < len(PERGUNTAS) else "Guardar e verificar",
            self._seguinte, papel="principal",
        ).pack(side="right")
        pecas.Botao(dentro, "Saltar esta", lambda: self._seguinte(saltar=True), papel="fantasma").pack(
            side="right", padx=10
        )

    def _rail(self, pai):
        fora = tk.Frame(pai, bg=tema.FUNDO, width=330)
        fora.pack_propagate(False)
        dentro = tk.Frame(fora, bg=tema.FUNDO)
        dentro.pack(fill="both", expand=True, padx=26, pady=24)
        pecas.rotulo(dentro, "seis perguntas").pack(fill="x", pady=(0, 14))

        for i, pergunta in enumerate(PERGUNTAS):
            atual = i == self.indice
            feita = bool(self.app.respostas.get(pergunta.id)) and not atual
            linha = tk.Frame(dentro, bg=tema.PAINEL if atual else tema.FUNDO)
            linha.pack(fill="x", pady=2)
            tk.Frame(linha, bg=tema.LARANJA if atual else (tema.PAINEL if not atual else tema.LINHA),
                     width=3).pack(side="left", fill="y")
            numero = tk.Label(
                linha, text="✓" if feita else str(i + 1), bg=linha["bg"],
                fg=tema.LARANJA if atual else (tema.VERDE if feita else tema.APAGADO),
                font=pecas.fonte(tema.CODIGO_PEQUENO), width=3, anchor="w", padx=8,
            )
            numero.pack(side="left", anchor="n", pady=10)
            tk.Label(
                linha, text=pergunta.texto, bg=linha["bg"],
                fg=tema.TEXTO if atual else tema.APAGADO, font=pecas.fonte(tema.INTERFACE),
                anchor="w", justify="left", wraplength=230, padx=0, pady=10,
            ).pack(side="left", fill="x", expand=True)

        pecas.espaco(dentro).pack(fill="both", expand=True)
        nota = pecas.cartao(dentro)
        nota.pack(fill="x")
        corpo_nota = tk.Frame(nota, bg=tema.PAINEL)
        corpo_nota.pack(fill="x", padx=16, pady=14)
        pecas.paragrafo(
            corpo_nota,
            "As respostas viram o aluno/perfil.md — cerca de 800 B que vão dentro de "
            "todos os briefings. Escreve como falas.",
            fonte_=tema.PEQUENO, largura=250,
        ).pack(fill="x")
        return fora

    def _pergunta(self, pai):
        fora = tk.Frame(pai, bg=tema.FUNDO)
        dentro = tk.Frame(fora, bg=tema.FUNDO)
        dentro.pack(fill="both", expand=True, padx=48, pady=36)

        pecas.mono(
            dentro, f"pergunta {self.indice + 1} de {len(PERGUNTAS)}", cor=tema.LARANJA
        ).pack(fill="x", pady=(0, 12))
        tk.Label(
            dentro, text=self.pergunta.texto, bg=tema.FUNDO, fg=tema.TEXTO,
            font=pecas.fonte(tema.TITULO_GRANDE), anchor="w", justify="left", wraplength=700,
        ).pack(fill="x")
        if self.pergunta.ajuda:
            pecas.paragrafo(dentro, self.pergunta.ajuda, largura=700).pack(fill="x", pady=(12, 0))

        guardada = self.app.respostas.get(self.pergunta.id, "")
        if self.pergunta.opcoes:
            self.lista = pecas.ListaEscolha(dentro, self.pergunta.opcoes, guardada)
            self.lista.pack(fill="x", pady=26)
            self.caixa = None
        else:
            self.lista = None
            pecas.rotulo(dentro, "a tua resposta").pack(fill="x", pady=(26, 8))
            self.caixa = pecas.caixa_de_texto(dentro, altura=7)
            self.caixa.pack(fill="x")
            self.caixa.insert("1.0", guardada)
            self.caixa.bind("<KeyRelease>", lambda _e: self._contar())
            medida = tk.Frame(dentro, bg=tema.FUNDO)
            medida.pack(fill="x", pady=(10, 0))
            self.etiqueta_bytes = pecas.mono(medida, "0 B")
            self.etiqueta_bytes.pack(side="left")
            self.medidor = pecas.Medidor(medida, largura=240)
            self.medidor.pack(side="left", padx=14)
            pecas.paragrafo(medida, "não precisa de ser bonito", fonte_=tema.PEQUENO).pack(side="left")
            self.caixa.focus_set()
            self._contar()

        pecas.espaco(dentro).pack(fill="both", expand=True)
        if self.indice == 0:
            self._porque(dentro).pack(fill="x", pady=(24, 0))
        return fora

    def _porque(self, pai):
        caixa = pecas.cartao(pai)
        dentro = tk.Frame(caixa, bg=tema.PAINEL)
        dentro.pack(fill="x", padx=18, pady=16)
        pecas.rotulo(dentro, "porque é que isto importa", cor=tema.VERDE).pack(fill="x", pady=(0, 8))
        pecas.paragrafo(
            dentro,
            "Onde paraste da última vez é onde o programa vai ter mais cuidado. Se disseres "
            "«desisti nos arrays», os arrays aparecem mais cedo, em bocados mais pequenos, "
            "e por previsão antes de construção.",
            largura=660,
        ).pack(fill="x")
        return caixa

    def _contar(self) -> None:
        n = len(self._resposta().encode("utf-8"))
        self.etiqueta_bytes.config(text=f"{n} B")
        self.medidor.por(n / 400)

    def _resposta(self) -> str:
        if self.caixa is not None:
            return self.caixa.get("1.0", "end").strip()
        return self.lista.valor

    def _anterior(self) -> None:
        self.app.respostas[self.pergunta.id] = self._resposta()
        self.app.mostrar(EcraPerfil, indice=self.indice - 1)

    def _seguinte(self, saltar: bool = False) -> None:
        self.app.respostas[self.pergunta.id] = "" if saltar else self._resposta()
        if self.indice + 1 < len(PERGUNTAS):
            self.app.mostrar(EcraPerfil, indice=self.indice + 1)
            return
        guardar_perfil(self.app.raiz, self.app.respostas)
        self.app.mostrar(EcraVerificacao)


# --- ecrã 3: a verificação -------------------------------------------------
class EcraVerificacao(tk.Frame):
    def __init__(self, pai, app: App) -> None:
        super().__init__(pai, bg=tema.FUNDO)
        self.app = app
        topo(self, 3).pack(fill="x")

        fora, dentro = rodape(self)
        fora.pack(fill="x", side="bottom")
        corpo = tk.Frame(self, bg=tema.FUNDO)
        corpo.pack(fill="both", expand=True, padx=MARGEM, pady=(24, 0))
        pecas.titulo(corpo, "A tua máquina aguenta este curso?", "grande").pack(fill="x")
        pecas.paragrafo(
            corpo,
            "Cada queixa traz o comando do conserto. Isto corre outra vez sempre que quiseres, "
            "com `gradus doctor`.",
            largura=820,
        ).pack(fill="x", pady=(8, 20))

        colunas = tk.Frame(corpo, bg=tema.FUNDO)
        colunas.pack(fill="both", expand=True)
        colunas.columnconfigure(0, weight=5, uniform="v")
        colunas.columnconfigure(1, weight=4, uniform="v")
        colunas.rowconfigure(0, weight=1)
        self.lista = tk.Frame(colunas, bg=tema.FUNDO)
        self.lista.grid(row=0, column=0, sticky="nsew")
        self.destaque = tk.Frame(colunas, bg=tema.FUNDO)
        self.destaque.grid(row=0, column=1, sticky="nsew", padx=(24, 0))

        pecas.Botao(dentro, "Verificar outra vez", self._verificar).pack(side="left")
        self.estado = pecas.paragrafo(dentro, "a verificar…", largura=600)
        self.estado.pack(side="left", padx=16)
        self.comecar = pecas.Botao(
            dentro, "Começar a estudar", self._comecar, papel="principal", estado="disabled"
        )
        self.comecar.pack(side="right")
        self._verificar()

    def _verificar(self) -> None:
        for zona in (self.lista, self.destaque):
            for filho in zona.winfo_children():
                filho.destroy()
        self.estado.config(text="a verificar…")
        self.comecar.estado("disabled")
        curso, curso_dir = self.app.curso()
        trabalho = self.app.trabalho(curso_dir)
        self.app.em_fundo(lambda: doctor_mod.run(curso, trabalho), self._mostrar)

    def _mostrar(self, checks) -> None:
        if checks is None:
            return
        # O tkinter só existe se esta janela existe: quem o verifica é o terminal.
        checks = [c for c in checks if c.nome != "tkinter"]
        falhas = 0
        for c in checks:
            if c.nome == "regex_erro":
                self._painel_regex(c).pack(fill="both", expand=True)
            else:
                self._linha(c).pack(fill="x", pady=(0, 8))
            falhas += int(not c.ok and c.nivel == doctor_mod.ERRO)
        self.estado.config(
            text="Está tudo. Podes começar." if not falhas
            else f"Falta resolver {falhas}. O comando está aí ao lado."
        )
        self.comecar.estado("normal" if not falhas else "disabled")

    def _linha(self, check):
        mau = not check.ok
        caixa = pecas.cartao(self.lista, borda=tema.LARANJA if mau else tema.LINHA)
        dentro = tk.Frame(caixa, bg=tema.PAINEL)
        dentro.pack(fill="x", padx=18, pady=14)
        cabeca = tk.Frame(dentro, bg=tema.PAINEL)
        cabeca.pack(fill="x")
        tk.Label(
            cabeca, text="✓" if check.ok else "✗", bg=tema.PAINEL,
            fg=tema.VERDE if check.ok else tema.LARANJA,
            font=pecas.fonte(tema.INTERFACE_FORTE), width=2,
        ).pack(side="left")
        tk.Label(
            cabeca, text=check.nome, bg=tema.PAINEL, fg=tema.TEXTO,
            font=pecas.fonte(tema.CODIGO_PEQUENO), width=20, anchor="w",
        ).pack(side="left")
        pecas.paragrafo(
            cabeca, check.detalhe, cor=tema.LARANJA if mau else tema.APAGADO, largura=380
        ).pack(side="left", fill="x", expand=True)
        if check.conserto:
            conserto = tk.Frame(dentro, bg=tema.PAINEL)
            conserto.pack(fill="x", pady=(10, 0))
            tk.Label(
                conserto, text=check.conserto, bg=tema.FUNDO, fg=tema.TEXTO,
                font=pecas.fonte(tema.CODIGO_PEQUENO), anchor="w", justify="left",
                wraplength=420, padx=12, pady=10,
            ).pack(side="left", fill="x", expand=True)
            pecas.Botao(
                conserto, "Copiar", lambda t=check.conserto: self._copiar(t)
            ).pack(side="left", padx=(8, 0))
        return caixa

    def _painel_regex(self, check):
        """A verificação que interessa fica sozinha, com o tamanho que merece."""
        caixa = pecas.cartao(self.destaque, borda=tema.VERDE if check.ok else tema.LARANJA)
        dentro = tk.Frame(caixa, bg=tema.PAINEL)
        dentro.pack(fill="both", expand=True, padx=22, pady=20)
        cabeca = tk.Frame(dentro, bg=tema.PAINEL)
        cabeca.pack(fill="x")
        tk.Label(
            cabeca, text="✓" if check.ok else "✗", bg=tema.PAINEL,
            fg=tema.VERDE if check.ok else tema.LARANJA,
            font=pecas.fonte(tema.INTERFACE_FORTE), width=2,
        ).pack(side="left")
        pecas.mono(cabeca, "regex_erro", cor=tema.TEXTO).pack(side="left")

        pecas.titulo(
            dentro,
            "Parti um ficheiro de propósito e o teu curso apanhou o erro." if check.ok
            else "O ficheiro partido não foi apanhado.",
            "pequeno", largura=400,
        ).pack(fill="x", pady=(14, 6))
        pecas.paragrafo(
            dentro,
            "Se isto falhasse, as tuas compilações ficavam guardadas como linhas cruas durante "
            "semanas — sem nunca dar erro nenhum.",
            largura=420,
        ).pack(fill="x")

        pecas.rotulo(dentro, "apanhado" if check.ok else "o que aconteceu").pack(fill="x", pady=(18, 8))
        tk.Label(
            dentro, text=check.detalhe.replace("apanhou: ", ""), bg=tema.FUNDO,
            fg=tema.TEXTO if check.ok else tema.LARANJA, font=pecas.fonte(tema.CODIGO_PEQUENO),
            anchor="w", justify="left", wraplength=400, padx=14, pady=12,
        ).pack(fill="x")
        if check.conserto:
            pecas.paragrafo(dentro, check.conserto, largura=420).pack(fill="x", pady=(12, 0))
        pecas.espaco(dentro).pack(fill="both", expand=True)
        pecas.paragrafo(
            dentro,
            "É este o texto que fica em telemetria/ a cada tentativa, e que volta no briefing "
            "seguinte como «os teus últimos erros».",
            fonte_=tema.PEQUENO, largura=420,
        ).pack(fill="x", pady=(16, 0))
        return caixa

    def _copiar(self, texto: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(texto)

    def _comecar(self) -> None:
        self.app.mostrar(EcraEstudo)


# --- o ecrã principal ------------------------------------------------------
class EcraEstudo(tk.Frame):
    """Conversa à esquerda, editor em cima à direita, saída em baixo, rodapé com
    o custo à vista."""

    def __init__(self, pai, app: App) -> None:
        super().__init__(pai, bg=tema.FUNDO)
        self.app = app
        self.curso, self.curso_dir = app.curso()
        self.trabalho = app.trabalho(self.curso_dir)
        self.estudo = Estudo(self.curso, self.curso_dir, self.trabalho, self._dialogo)
        self.ocupado = False

        self._cabeca().pack(fill="x")
        fora, dentro = rodape(self)
        fora.pack(fill="x", side="bottom")
        meio = tk.Frame(self, bg=tema.FUNDO)
        meio.pack(fill="both", expand=True, padx=MARGEM, pady=(4, 0))
        meio.columnconfigure(0, weight=5, uniform="m")
        meio.columnconfigure(1, weight=6, uniform="m")
        meio.rowconfigure(0, weight=3)
        meio.rowconfigure(1, weight=2)

        self._conversa(meio).grid(row=0, column=0, rowspan=2, sticky="nsew")
        self._editor(meio).grid(row=0, column=1, sticky="nsew", padx=(20, 0))
        self._saida(meio).grid(row=1, column=1, sticky="nsew", padx=(20, 0), pady=(16, 0))
        self._rodape(dentro)
        self._trancar(False)        # um só sítio decide o que está ligado
        self._pintar_rodape()

    # --- peças ------------------------------------------------------------
    def _cabeca(self):
        fora = tk.Frame(self, bg=tema.FUNDO)
        linha = tk.Frame(fora, bg=tema.FUNDO)
        linha.pack(fill="x", padx=MARGEM, pady=(20, 16))
        tk.Label(
            linha, text="gradus", bg=tema.FUNDO, fg=tema.TEXTO, font=pecas.fonte(tema.TITULO)
        ).pack(side="left")
        tk.Frame(linha, bg=tema.LINHA, width=1, height=20).pack(side="left", padx=14, pady=2)
        self.etiqueta_no = pecas.paragrafo(linha, "nada a decorrer", largura=560)
        self.etiqueta_no.pack(side="left")

        self.botao_principal = pecas.Botao(
            linha, "Começar exercício", self._principal, papel="principal"
        )
        self.botao_principal.pack(side="right")
        self.botao_cortar = pecas.Botao(
            linha, "Cortar aqui", lambda: self._terminar(False), estado="disabled"
        )
        self.botao_cortar.pack(side="right", padx=10)
        self.botao_simulador = pecas.Botao(linha, "Simulador", self._simulador, papel="fantasma")
        self.botao_simulador.pack(side="right", padx=10)
        pecas.separador(fora).pack(fill="x")
        return fora

    def _conversa(self, pai):
        caixa = pecas.cartao(pai)
        cabeca = tk.Frame(caixa, bg=tema.PAINEL)
        cabeca.pack(fill="x", padx=20, pady=(16, 0))
        pecas.rotulo(cabeca, "conversa").pack(side="left")
        self.etiqueta_tipo = pecas.mono(cabeca, "")
        self.etiqueta_tipo.pack(side="right")

        self.painel = pecas.Painel(
            caixa, "Carrega em «Começar exercício».\nO gradus escolhe o próximo e abre a sessão.",
            altura=10,
        )
        self.painel.pack(fill="both", expand=True, pady=(8, 0))
        self.painel.texto.tag_configure("quem", foreground=tema.APAGADO, spacing1=10)
        self.painel.texto.tag_configure("gradus", foreground=tema.TEXTO, spacing3=12)
        self.painel.texto.tag_configure("aluno", foreground=tema.VERDE, spacing3=12)
        self.painel.texto.tag_configure("sistema", foreground=tema.APAGADO, spacing3=12)

        baixo = tk.Frame(caixa, bg=tema.PAINEL)
        baixo.pack(fill="x", padx=16, pady=16)
        self.entrada = pecas.entrada(baixo)
        self.entrada.pack(side="left", fill="x", expand=True, ipady=9, padx=(0, 10))
        self.entrada.bind("<Return>", lambda _: self._enviar())
        self.botao_enviar = pecas.Botao(baixo, "Enviar", self._enviar, estado="disabled")
        self.botao_enviar.pack(side="left")
        return caixa

    def _editor(self, pai):
        caixa = pecas.cartao(pai)
        cabeca = tk.Frame(caixa, bg=tema.PAINEL)
        cabeca.pack(fill="x", padx=20, pady=(16, 10))
        esquerda = tk.Frame(cabeca, bg=tema.PAINEL)
        esquerda.pack(side="left")
        pecas.rotulo(esquerda, "exercício").pack(anchor="w")
        self.etiqueta_ficheiro = pecas.mono(esquerda, "nenhum ainda", cor=tema.TEXTO)
        self.etiqueta_ficheiro.pack(anchor="w", pady=(4, 0))

        self.botao_compilar = pecas.Botao(
            cabeca, "Compilar e correr", self._compilar, papel="principal", estado="disabled"
        )
        self.botao_compilar.pack(side="right")
        self.botao_guardar = pecas.Botao(cabeca, "Guardar", self._guardar, estado="disabled")
        self.botao_guardar.pack(side="right", padx=10)

        self.editor = pecas.caixa_de_texto(caixa, altura=16, mono_=True)
        self.editor.config(highlightthickness=0)
        self.editor.pack(fill="both", expand=True, padx=1, pady=(0, 1))
        self.editor.insert("1.0", "\n  o exercício aparece aqui quando começares.\n")
        self.editor.config(state="disabled")
        return caixa

    def _saida(self, pai):
        caixa = pecas.cartao(pai)
        cabeca = tk.Frame(caixa, bg=tema.PAINEL)
        cabeca.pack(fill="x", padx=20, pady=(16, 8))
        pecas.rotulo(cabeca, "compilador").pack(side="left")
        self.etiqueta_tentativas = pecas.mono(cabeca, "")
        self.etiqueta_tentativas.pack(side="right")
        self.saida = pecas.Painel(
            caixa, "ainda não compilaste nada.\ncada tentativa vai para telemetria/ sozinha.",
            fonte_=tema.CODIGO_PEQUENO, cor=tema.TEXTO, fundo=tema.FUNDO, altura=6,
        )
        self.saida.pack(fill="both", expand=True, padx=1, pady=(0, 1))
        self.saida.texto.tag_configure("erro", foreground=tema.LARANJA)
        self.saida.texto.tag_configure("ok", foreground=tema.VERDE)
        self.saida.texto.tag_configure("comando", foreground=tema.APAGADO)
        return caixa

    def _rodape(self, dentro) -> None:
        self.etiqueta_briefing = pecas.mono(dentro, "briefing —")
        self.etiqueta_briefing.pack(side="left")
        tk.Frame(dentro, bg=tema.LINHA, width=1, height=16).pack(side="left", padx=16, pady=2)
        self.etiqueta_fraquezas = pecas.paragrafo(dentro, "", fonte_=tema.PEQUENO, largura=520)
        self.etiqueta_fraquezas.pack(side="left")
        self.etiqueta_contexto = pecas.mono(dentro, "0.0 / 15 KB")
        self.etiqueta_contexto.pack(side="right")
        self.medidor = pecas.Medidor(dentro, largura=200)
        self.medidor.pack(side="right", padx=14)

    # --- ações ------------------------------------------------------------
    def _dialogo(self, abertura, exercicio):
        if self.app.seco:
            return ConversaSeca(
                abertura.briefing.texto, abertura.node.id, exercicio, self.curso.teto_contexto_kb
            )
        return Conversa(
            course=self.curso, claude=Claude(), node_id=abertura.node.id,
            tipo=abertura.choice.tipo, briefing=abertura.briefing.texto, exercicio=exercicio,
        )

    def _principal(self) -> None:
        if self.ocupado:
            return
        self._comecar() if self.estudo.abertura is None else self._terminar(True)

    def _comecar(self) -> None:
        abertura = self.estudo.comecar()
        if abertura is None:
            messagebox.showinfo(
                "gradus", "Não há nada elegível no grafo por agora. Volta daqui a uns dias."
            )
            return
        self.etiqueta_no.config(text=f"{abertura.node.nome} — {abertura.choice.motivo}", fg=tema.TEXTO)
        self.etiqueta_tipo.config(text=NOMES_TIPO.get(abertura.choice.tipo, abertura.choice.tipo),
                                  fg=tema.LARANJA)
        self.etiqueta_ficheiro.config(text=self.estudo.exercicio)
        self.editor.config(state="normal")
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", self.estudo.caminho_exercicio().read_text(encoding="utf-8"))
        self.painel.limpar()
        self.saida.limpar()
        self.etiqueta_tentativas.config(text="")
        self._trancar(True)
        self.app.em_fundo(self.estudo.primeira_fala, lambda t: self._chegou("gradus", t))

    def _enviar(self) -> None:
        texto = self.entrada.get().strip()
        if not texto or self.ocupado or self.estudo.abertura is None:
            return
        self.entrada.delete(0, "end")
        self._escrever("aluno", texto)
        self._trancar(True)
        self.app.em_fundo(lambda: self.estudo.enviar(texto), lambda t: self._chegou("gradus", t))

    def _guardar(self) -> None:
        if self.estudo.abertura is None:
            return
        self.estudo.caminho_exercicio().write_text(self.editor.get("1.0", "end-1c"), encoding="utf-8")

    def _compilar(self) -> None:
        if self.ocupado or self.estudo.abertura is None:
            return
        self._guardar()
        self._trancar(True)
        self.app.em_fundo(self.estudo.compilar, self._compilou)

    def _compilou(self, resultado) -> None:
        if resultado is None:
            self._trancar(False)
            return
        attempt, resposta = resultado
        self.saida.limpar()
        self.saida.escrever(f"$ {attempt.comando}\n", "comando")
        if attempt.erro:
            self.saida.escrever(attempt.erro + "\n", "erro")
        else:
            self.saida.escrever((attempt.saida or "(correu, sem saída)") + "\n", "ok")
        tentativas = len(self.estudo.dialogo.compilacoes) if self.estudo.dialogo else 0
        self.etiqueta_tentativas.config(text=f"{tentativas} tentativa(s)")
        self._chegou("gradus", resposta)

    def _terminar(self, passou: bool) -> None:
        if self.ocupado or self.estudo.abertura is None:
            return
        self._guardar()
        self._trancar(True)
        self.app.em_fundo(lambda: self.estudo.terminar(passou), self._terminou)

    def _terminou(self, relatorio) -> None:
        self._trancar(False)
        self.etiqueta_tipo.config(text="")
        if relatorio is None:
            return
        p = relatorio.passage
        recado = [
            f"{p.no} · {p.tipo} · {p.resultado}",
            f"{p.compilacoes} tentativa(s) · {p.kb_contexto} KB · {p.duracao_min} min",
        ]
        if relatorio.promocao:
            recado.append(relatorio.promocao)
        if p.resultado != "passou":
            recado.append("O exercício fica aberto: a próxima passagem retoma-o com o bilhete.")
        self.etiqueta_no.config(text="nada a decorrer", fg=tema.APAGADO)
        messagebox.showinfo("gradus", "\n".join(recado))
        self._pintar_rodape()

    def _simulador(self) -> None:
        if not self.estudo.exercicio or not self.estudo.caminho_exercicio().exists():
            messagebox.showinfo(
                "gradus",
                "O simulador faz perguntas sobre código que tu escreveste. "
                "Acaba um exercício primeiro.",
            )
            return
        no = self.estudo.abertura.node.id if self.estudo.abertura else ""
        JanelaSimulador(self, self.curso, self.trabalho, no, self.estudo.exercicio)

    # --- pintura ----------------------------------------------------------
    def _chegou(self, papel: str, texto) -> None:
        self._trancar(False)
        if texto:
            self._escrever(papel, texto)
        self._pintar_rodape()
        if self.estudo.dialogo is not None and self.estudo.deve_cortar():
            self._escrever(
                "sistema",
                "O contexto chegou ao teto. Carrega em «Cortar aqui»: esta sessão morre e a "
                "próxima retoma o exercício com um bilhete de 400 B.",
            )

    def _escrever(self, papel: str, texto: str) -> None:
        self.painel.escrever(f"{'tu' if papel == 'aluno' else 'gradus'}\n", "quem")
        self.painel.escrever(texto.strip() + "\n", papel)

    def _trancar(self, ocupado: bool) -> None:
        self.ocupado = ocupado
        a_decorrer = self.estudo.abertura is not None
        ligado = "normal" if not ocupado and a_decorrer else "disabled"
        for b in (self.botao_compilar, self.botao_guardar, self.botao_cortar, self.botao_enviar):
            b.estado(ligado)
        self.botao_principal.config(text="Passou" if a_decorrer else "Começar exercício")
        self.botao_principal.estado("disabled" if ocupado else "normal")
        self.editor.config(state="normal" if a_decorrer else "disabled")
        tipo = NOMES_TIPO.get(self.estudo.abertura.choice.tipo, "") if a_decorrer else ""
        self.etiqueta_tipo.config(text="a pensar…" if ocupado else tipo)

    def _pintar_rodape(self) -> None:
        r = self.estudo.rodape()
        self.etiqueta_briefing.config(text=f"briefing {r.briefing}" if r.briefing else "briefing —")
        self.etiqueta_fraquezas.config(
            text=("a treinar: " + ", ".join(r.fraquezas)) if r.fraquezas else "sem fraquezas ativas"
        )
        self.etiqueta_contexto.config(text=f"{r.kb:.1f} / {r.teto_kb:.0f} KB")
        self.medidor.por(r.cheio)


# --- o simulador -----------------------------------------------------------
class JanelaSimulador(tk.Toplevel):
    """Dez seguidas certas sobre o ficheiro dele. Nada aqui pergunta a um modelo:
    a resposta certa saiu de correr o código."""

    def __init__(self, pai, curso, trabalho: Path, node_id: str, exercicio: str) -> None:
        super().__init__(pai, bg=tema.FUNDO)
        self.title("gradus · simulador")
        self.geometry("760x820")
        self.app = pai.app
        self.sim = Simulacao(curso, trabalho, node_id, exercicio)

        cabeca = tk.Frame(self, bg=tema.FUNDO)
        cabeca.pack(fill="x", padx=28, pady=(24, 0))
        pecas.rotulo(cabeca, "simulador").pack(side="left")
        self.conta = pecas.mono(cabeca, "0 de 10", cor=tema.LARANJA)
        self.conta.pack(side="right")

        self.pergunta = tk.Label(
            self, text="a preparar…", bg=tema.FUNDO, fg=tema.TEXTO,
            font=pecas.fonte(tema.TITULO_PEQUENO), anchor="w", justify="left", wraplength=690,
        )
        self.pergunta.pack(fill="x", padx=28, pady=(12, 4))
        pecas.paragrafo(
            self, "Dez seguidas certas levam o nó a automático — e nunca as dez no mesmo dia.",
            fonte_=tema.PEQUENO, largura=690,
        ).pack(fill="x", padx=28)

        caixa = pecas.cartao(self)
        caixa.pack(fill="both", expand=True, padx=28, pady=16)
        self.codigo = tk.Text(
            caixa, bg=tema.PAINEL, fg=tema.TEXTO, font=pecas.fonte(tema.CODIGO_PEQUENO),
            relief="flat", bd=0, padx=18, pady=16, wrap="none", state="disabled",
            highlightthickness=0,
        )
        self.codigo.pack(fill="both", expand=True)

        baixo = tk.Frame(self, bg=tema.FUNDO)
        baixo.pack(fill="x", padx=28)
        self.entrada = pecas.entrada(baixo)
        self.entrada.pack(side="left", fill="x", expand=True, ipady=9, padx=(0, 10))
        self.entrada.bind("<Return>", lambda _: self._responder())
        pecas.Botao(baixo, "Responder", self._responder, papel="principal").pack(side="left")

        self.resposta = pecas.paragrafo(self, "", largura=690)
        self.resposta.pack(fill="x", padx=28, pady=20)
        self._proxima()

    def _proxima(self) -> None:
        self.entrada.delete(0, "end")
        self.pergunta.config(text="a preparar a próxima…")
        self.app.em_fundo(self.sim.proxima, self._mostrar)

    def _mostrar(self, previsao) -> None:
        if previsao is None:
            self.pergunta.config(
                text="Não consegui mudar nada neste ficheiro que ainda corresse. Escreve mais um bocado."
            )
            return
        self.pergunta.config(text=previsao.pergunta)
        self.codigo.config(state="normal")
        self.codigo.delete("1.0", "end")
        self.codigo.insert("1.0", previsao.codigo)
        self.codigo.config(state="disabled")
        self.entrada.focus_set()

    def _responder(self) -> None:
        if self.sim.atual is None:
            return
        r = self.sim.responder(self.entrada.get())
        if r.certo:
            self.resposta.config(text=f"certo · faltam {r.em_falta}", fg=tema.VERDE)
        else:
            self.resposta.config(text=f"não — era: {r.certa}. A conta volta a zero.", fg=tema.LARANJA)
        self.conta.config(text=f"{r.seguidas} de 10")
        if r.promocao:
            messagebox.showinfo("gradus", r.promocao)
            self.destroy()
            return
        self.after(1400, self._proxima)


def correr(raiz: Path, trabalho: Path | None = None, seco: bool = False) -> int:
    try:
        app = App(raiz, trabalho, seco)
    except tk.TclError as exc:
        raise CourseError(
            f"o tkinter não conseguiu abrir uma janela ({exc}) — "
            f"se estás por SSH, falta o DISPLAY"
        ) from None
    app.mainloop()
    return 0
