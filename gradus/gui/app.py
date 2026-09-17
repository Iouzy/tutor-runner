"""A aplicação de secretária. tkinter, biblioteca padrão, sem dependências.

Thin on purpose: every decision lives in `controller.py`, which has no tkinter
in it and is tested headless. What is left here is placement, colour, and the
one thing a GUI must get right — never blocking the window while a session
is thinking, or the whole thing looks broken while it works.
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
from ..model import CourseError
from . import tema
from .controller import PERGUNTAS, Estudo, Simulacao, escolher_curso, guardar_perfil


class App(tk.Tk):
    """Uma janela, quatro ecrãs: três de arranque e o do estudo."""

    def __init__(self, raiz: Path, trabalho: Path | None = None, seco: bool = False) -> None:
        super().__init__()
        self.raiz = raiz
        self.trabalho_raiz = trabalho
        self.seco = seco
        self.title("gradus")
        self.geometry("1280x860")
        self.minsize(1040, 700)
        self.configure(bg=tema.FUNDO)
        self.respostas: dict[str, str] = {}
        self.config_atual = config_mod.load(raiz)
        _fixar_fontes(self)
        self.container = tk.Frame(self, bg=tema.FUNDO)
        self.container.pack(fill="both", expand=True)
        self.mostrar(EcraLinguagem if self.config_atual is None else EcraEstudo)

    def mostrar(self, classe, **kw) -> None:
        for filho in self.container.winfo_children():
            filho.destroy()
        ecra = classe(self.container, self, **kw)
        ecra.pack(fill="both", expand=True)

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


# --- peças comuns ----------------------------------------------------------
def _fixar_fontes(root: tk.Misc) -> None:
    existentes = set(tkfont.families(root))
    for pedida, _ in list(tema.ALTERNATIVAS.items()):
        tema.ALTERNATIVAS[pedida] = (tema.familia_disponivel(pedida, existentes),)


def _fonte(spec):
    familia, *resto = spec
    return (tema.ALTERNATIVAS.get(familia, (familia,))[0], *resto)


def titulo(pai, texto, grande=False):
    return tk.Label(
        pai, text=texto, bg=pai["bg"], fg=tema.TEXTO,
        font=_fonte(tema.TITULO_GRANDE if grande else tema.TITULO),
        anchor="w", justify="left",
    )


def legenda(pai, texto, cor=tema.APAGADO, fonte=None):
    return tk.Label(
        pai, text=texto, bg=pai["bg"], fg=cor, font=_fonte(fonte or tema.INTERFACE),
        anchor="w", justify="left", wraplength=760,
    )


def botao(pai, texto, comando, principal=False, estado="normal"):
    return tk.Button(
        pai, text=texto, command=comando, state=estado,
        bg=tema.LARANJA if principal else tema.PAINEL,
        fg=tema.FUNDO if principal else tema.TEXTO,
        activebackground=tema.LARANJA if principal else tema.LINHA,
        activeforeground=tema.FUNDO if principal else tema.TEXTO,
        disabledforeground=tema.APAGADO,
        font=_fonte(tema.INTERFACE_FORTE), relief="flat", padx=20, pady=10,
        highlightthickness=0, cursor="hand2",
    )


def barra(pai, passo: int):
    linha = tk.Frame(pai, bg=tema.FUNDO)
    tk.Label(linha, text="gradus", bg=tema.FUNDO, fg=tema.TEXTO, font=_fonte(tema.TITULO)).pack(side="left")
    tk.Label(
        linha, text=f"   arranque · passo {passo} de 3", bg=tema.FUNDO, fg=tema.APAGADO,
        font=_fonte(tema.INTERFACE),
    ).pack(side="left")
    marcas = tk.Frame(linha, bg=tema.FUNDO)
    marcas.pack(side="right")
    for i in (1, 2, 3):
        cor = tema.VERDE if i < passo else (tema.LARANJA if i == passo else tema.LINHA)
        tk.Frame(marcas, bg=cor, width=28, height=4).pack(side="left", padx=3)
    return linha


# --- ecrã 1: a linguagem ---------------------------------------------------
class EcraLinguagem(tk.Frame):
    def __init__(self, pai, app: App) -> None:
        super().__init__(pai, bg=tema.FUNDO)
        self.app = app
        barra(self, 1).pack(fill="x", padx=32, pady=(24, 0))
        titulo(self, "Que linguagem queres aprender?", grande=True).pack(fill="x", padx=32, pady=(40, 8))
        legenda(self, "Escolhes aqui. O programa trata do resto — não há ficheiros para editar.").pack(fill="x", padx=32)

        cartoes = tk.Frame(self, bg=tema.FUNDO)
        cartoes.pack(fill="both", expand=True, padx=32, pady=32)
        for disponivel in config_mod.disponiveis(app.raiz):
            self._cartao(cartoes, disponivel).pack(side="left", padx=(0, 16), anchor="n")

    def _cartao(self, pai, disponivel):
        caixa = tk.Frame(pai, bg=tema.PAINEL, highlightbackground=tema.LINHA, highlightthickness=1)
        tk.Label(
            caixa, text=disponivel.nome, bg=tema.PAINEL, fg=tema.TEXTO,
            font=_fonte(tema.TITULO), anchor="w",
        ).pack(fill="x", padx=24, pady=(24, 4))
        tk.Label(
            caixa, text=disponivel.extensao or disponivel.linguagem, bg=tema.PAINEL, fg=tema.APAGADO,
            font=_fonte(tema.CODIGO), anchor="w",
        ).pack(fill="x", padx=24)
        botao(caixa, "Escolher", lambda: self._escolher(disponivel.caminho), principal=True).pack(
            padx=24, pady=24, anchor="w"
        )
        return caixa

    def _escolher(self, caminho: str) -> None:
        self.app.config_atual = escolher_curso(self.app.raiz, caminho)
        self.app.mostrar(EcraPerfil)


# --- ecrã 2: o perfil ------------------------------------------------------
class EcraPerfil(tk.Frame):
    def __init__(self, pai, app: App, indice: int = 0) -> None:
        super().__init__(pai, bg=tema.FUNDO)
        self.app = app
        self.indice = indice
        pergunta = PERGUNTAS[indice]

        barra(self, 2).pack(fill="x", padx=32, pady=(24, 0))
        corpo = tk.Frame(self, bg=tema.FUNDO)
        corpo.pack(fill="both", expand=True, padx=32, pady=24)

        tk.Label(
            corpo, text=f"pergunta {indice + 1} de {len(PERGUNTAS)}", bg=tema.FUNDO,
            fg=tema.LARANJA, font=_fonte(tema.CODIGO_PEQUENO), anchor="w",
        ).pack(fill="x", pady=(16, 10))
        titulo(corpo, pergunta.texto, grande=True).pack(fill="x")
        if pergunta.ajuda:
            legenda(corpo, pergunta.ajuda).pack(fill="x", pady=(10, 0))

        self.escolha = tk.StringVar(value=app.respostas.get(pergunta.id, ""))
        if pergunta.opcoes:
            caixa = tk.Frame(corpo, bg=tema.FUNDO)
            caixa.pack(fill="x", pady=24)
            for opcao in pergunta.opcoes:
                tk.Radiobutton(
                    caixa, text=opcao, value=opcao, variable=self.escolha,
                    bg=tema.FUNDO, fg=tema.TEXTO, selectcolor=tema.PAINEL,
                    activebackground=tema.FUNDO, activeforeground=tema.TEXTO,
                    font=_fonte(tema.INTERFACE), anchor="w", highlightthickness=0,
                    padx=8, pady=6,
                ).pack(fill="x")
            self.caixa_texto = None
        else:
            self.caixa_texto = tk.Text(
                corpo, height=7, bg=tema.PAINEL, fg=tema.TEXTO, insertbackground=tema.LARANJA,
                font=_fonte(tema.INTERFACE), relief="flat", padx=16, pady=14, wrap="word",
                highlightbackground=tema.LINHA, highlightthickness=1,
            )
            self.caixa_texto.pack(fill="x", pady=24)
            self.caixa_texto.insert("1.0", app.respostas.get(pergunta.id, ""))
            self.caixa_texto.focus_set()

        legenda(
            corpo,
            "As respostas viram o aluno/perfil.md — cerca de 800 B que vão dentro de todos os "
            "briefings. Escreve como falas.",
            fonte=tema.PEQUENO,
        ).pack(fill="x", side="bottom")

        rodape = tk.Frame(self, bg=tema.FUNDO)
        rodape.pack(fill="x", padx=32, pady=(0, 24))
        if indice:
            botao(rodape, "Anterior", self._anterior).pack(side="left")
        botao(rodape, "Seguinte" if indice + 1 < len(PERGUNTAS) else "Guardar", self._seguinte,
              principal=True).pack(side="right")
        botao(rodape, "Saltar esta", lambda: self._seguinte(saltar=True)).pack(side="right", padx=8)

    def _resposta(self) -> str:
        if self.caixa_texto is not None:
            return self.caixa_texto.get("1.0", "end").strip()
        return self.escolha.get()

    def _anterior(self) -> None:
        self.app.respostas[PERGUNTAS[self.indice].id] = self._resposta()
        self.app.mostrar(EcraPerfil, indice=self.indice - 1)

    def _seguinte(self, saltar: bool = False) -> None:
        self.app.respostas[PERGUNTAS[self.indice].id] = "" if saltar else self._resposta()
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
        barra(self, 3).pack(fill="x", padx=32, pady=(24, 0))
        titulo(self, "A tua máquina aguenta este curso?", grande=True).pack(fill="x", padx=32, pady=(32, 6))
        legenda(
            self, "Cada queixa traz o comando do conserto. Isto corre outra vez com `gradus doctor`."
        ).pack(fill="x", padx=32)

        self.lista = tk.Frame(self, bg=tema.FUNDO)
        self.lista.pack(fill="both", expand=True, padx=32, pady=20)
        self.estado = legenda(self, "a verificar…")
        self.estado.pack(fill="x", padx=32)

        rodape = tk.Frame(self, bg=tema.FUNDO)
        rodape.pack(fill="x", padx=32, pady=24)
        botao(rodape, "Verificar outra vez", self._verificar).pack(side="left")
        self.comecar = botao(rodape, "Começar a estudar", self._comecar, principal=True, estado="disabled")
        self.comecar.pack(side="right")
        self._verificar()

    def _verificar(self) -> None:
        for filho in self.lista.winfo_children():
            filho.destroy()
        self.estado.config(text="a verificar…")
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
            falhas += int(not c.ok and c.nivel == doctor_mod.ERRO)
            self._linha(c).pack(fill="x", pady=3)
        self.estado.config(
            text="Está tudo." if not falhas else f"Falta resolver {falhas}. O comando está aí em cima."
        )
        self.comecar.config(state="normal" if not falhas else "disabled")

    def _linha(self, check):
        caixa = tk.Frame(self.lista, bg=tema.PAINEL, highlightbackground=tema.LINHA, highlightthickness=1)
        topo = tk.Frame(caixa, bg=tema.PAINEL)
        topo.pack(fill="x", padx=16, pady=(12, 0))
        cor = tema.VERDE if check.ok else (tema.LARANJA if check.nivel == doctor_mod.AVISO else tema.LARANJA)
        tk.Label(topo, text="✓" if check.ok else "✗", bg=tema.PAINEL, fg=cor,
                 font=_fonte(tema.INTERFACE_FORTE), width=2).pack(side="left")
        tk.Label(topo, text=check.nome, bg=tema.PAINEL, fg=tema.TEXTO,
                 font=_fonte(tema.CODIGO), width=20, anchor="w").pack(side="left")
        tk.Label(topo, text=check.detalhe, bg=tema.PAINEL, fg=tema.APAGADO,
                 font=_fonte(tema.INTERFACE), anchor="w").pack(side="left", fill="x", expand=True)
        if check.conserto:
            fundo = tk.Frame(caixa, bg=tema.PAINEL)
            fundo.pack(fill="x", padx=16, pady=(6, 12))
            tk.Label(fundo, text=check.conserto, bg=tema.FUNDO, fg=tema.TEXTO,
                     font=_fonte(tema.CODIGO_PEQUENO), anchor="w", padx=10, pady=8,
                     wraplength=820, justify="left").pack(side="left", fill="x", expand=True)
            botao(fundo, "Copiar", lambda t=check.conserto: self._copiar(t)).pack(side="left", padx=(8, 0))
        else:
            tk.Frame(caixa, bg=tema.PAINEL, height=12).pack(fill="x")
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

        self._topo().pack(fill="x", padx=20, pady=(16, 8))
        meio = tk.Frame(self, bg=tema.FUNDO)
        meio.pack(fill="both", expand=True, padx=20)
        self._conversa(meio).pack(side="left", fill="both", expand=True)
        direita = tk.Frame(meio, bg=tema.FUNDO)
        direita.pack(side="left", fill="both", expand=True, padx=(16, 0))
        self._editor(direita).pack(fill="both", expand=True)
        self._saida(direita).pack(fill="both", expand=False, pady=(12, 0))
        self._rodape().pack(fill="x", padx=20, pady=12)
        self._pintar_rodape()

    # --- peças ------------------------------------------------------------
    def _topo(self):
        linha = tk.Frame(self, bg=tema.FUNDO)
        tk.Label(linha, text="gradus", bg=tema.FUNDO, fg=tema.TEXTO, font=_fonte(tema.TITULO)).pack(side="left")
        self.etiqueta_no = tk.Label(linha, text="", bg=tema.FUNDO, fg=tema.APAGADO, font=_fonte(tema.INTERFACE))
        self.etiqueta_no.pack(side="left", padx=16)
        self.botao_comecar = botao(linha, "Começar exercício", self._comecar, principal=True)
        self.botao_comecar.pack(side="right")
        self.botao_passou = botao(linha, "Passou", lambda: self._terminar(True), estado="disabled")
        self.botao_passou.pack(side="right", padx=8)
        self.botao_cortar = botao(linha, "Cortar aqui", lambda: self._terminar(False), estado="disabled")
        self.botao_cortar.pack(side="right")
        botao(linha, "Simulador", self._simulador).pack(side="right", padx=8)
        return linha

    def _conversa(self, pai):
        caixa = tk.Frame(pai, bg=tema.PAINEL, highlightbackground=tema.LINHA, highlightthickness=1)
        self.texto_conversa = tk.Text(
            caixa, bg=tema.PAINEL, fg=tema.TEXTO, font=_fonte(tema.INTERFACE), relief="flat",
            padx=16, pady=14, wrap="word", state="disabled", highlightthickness=0,
        )
        self.texto_conversa.pack(fill="both", expand=True)
        self.texto_conversa.tag_configure("gradus", foreground=tema.TEXTO, spacing3=10)
        self.texto_conversa.tag_configure("aluno", foreground=tema.VERDE, spacing3=10)
        self.texto_conversa.tag_configure("sistema", foreground=tema.APAGADO, spacing3=10)

        baixo = tk.Frame(caixa, bg=tema.PAINEL)
        baixo.pack(fill="x", padx=12, pady=12)
        self.entrada = tk.Entry(
            baixo, bg=tema.FUNDO, fg=tema.TEXTO, insertbackground=tema.LARANJA,
            font=_fonte(tema.INTERFACE), relief="flat", highlightbackground=tema.LINHA,
            highlightthickness=1,
        )
        self.entrada.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 8))
        self.entrada.bind("<Return>", lambda _: self._enviar())
        botao(baixo, "Enviar", self._enviar).pack(side="left")
        return caixa

    def _editor(self, pai):
        caixa = tk.Frame(pai, bg=tema.PAINEL, highlightbackground=tema.LINHA, highlightthickness=1)
        topo = tk.Frame(caixa, bg=tema.PAINEL)
        topo.pack(fill="x", padx=12, pady=(10, 0))
        self.etiqueta_ficheiro = tk.Label(
            topo, text="—", bg=tema.PAINEL, fg=tema.APAGADO, font=_fonte(tema.CODIGO_PEQUENO)
        )
        self.etiqueta_ficheiro.pack(side="left")
        self.botao_compilar = botao(topo, "Compilar e correr", self._compilar, principal=True, estado="disabled")
        self.botao_compilar.pack(side="right")
        botao(topo, "Guardar", self._guardar).pack(side="right", padx=8)

        self.editor = tk.Text(
            caixa, bg=tema.PAINEL, fg=tema.TEXTO, insertbackground=tema.LARANJA,
            font=_fonte(tema.CODIGO), relief="flat", padx=14, pady=12, wrap="none",
            highlightthickness=0, undo=True,
        )
        self.editor.pack(fill="both", expand=True)
        return caixa

    def _saida(self, pai):
        caixa = tk.Frame(pai, bg=tema.PAINEL, highlightbackground=tema.LINHA, highlightthickness=1, height=200)
        caixa.pack_propagate(False)
        self.texto_saida = tk.Text(
            caixa, bg=tema.FUNDO, fg=tema.APAGADO, font=_fonte(tema.CODIGO_PEQUENO), relief="flat",
            padx=14, pady=12, wrap="word", state="disabled", highlightthickness=0,
        )
        self.texto_saida.pack(fill="both", expand=True)
        self.texto_saida.tag_configure("erro", foreground=tema.LARANJA)
        self.texto_saida.tag_configure("ok", foreground=tema.VERDE)
        return caixa

    def _rodape(self):
        linha = tk.Frame(self, bg=tema.FUNDO)
        self.etiqueta_briefing = tk.Label(
            linha, text="", bg=tema.FUNDO, fg=tema.APAGADO, font=_fonte(tema.CODIGO_PEQUENO), anchor="w"
        )
        self.etiqueta_briefing.pack(side="left")
        self.etiqueta_fraquezas = tk.Label(
            linha, text="", bg=tema.FUNDO, fg=tema.APAGADO, font=_fonte(tema.PEQUENO), anchor="w"
        )
        self.etiqueta_fraquezas.pack(side="left", padx=24)
        self.etiqueta_contexto = tk.Label(
            linha, text="", bg=tema.FUNDO, fg=tema.APAGADO, font=_fonte(tema.CODIGO_PEQUENO)
        )
        self.etiqueta_contexto.pack(side="right")
        self.medidor = tk.Frame(linha, bg=tema.LINHA, width=180, height=4)
        self.medidor.pack(side="right", padx=10)
        self.medidor.pack_propagate(False)
        self.cheio = tk.Frame(self.medidor, bg=tema.VERDE, width=0, height=4)
        self.cheio.pack(side="left")
        return linha

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

    def _comecar(self) -> None:
        abertura = self.estudo.comecar()
        if abertura is None:
            messagebox.showinfo("gradus", "Não há nada elegível no grafo. Vai daqui a uns dias.")
            return
        self.etiqueta_no.config(
            text=f"{abertura.node.nome} · {abertura.choice.tipo} — {abertura.choice.motivo}"
        )
        self.etiqueta_ficheiro.config(text=self.estudo.exercicio)
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", self.estudo.caminho_exercicio().read_text(encoding="utf-8"))
        self._trancar(True)
        self.app.em_fundo(self.estudo.primeira_fala, lambda t: self._chegou("gradus", t))

    def _enviar(self) -> None:
        texto = self.entrada.get().strip()
        if not texto or self.ocupado:
            return
        self.entrada.delete(0, "end")
        self._escrever("aluno", texto)
        self._trancar(True)
        self.app.em_fundo(lambda: self.estudo.enviar(texto), lambda t: self._chegou("gradus", t))

    def _guardar(self) -> None:
        self.estudo.caminho_exercicio().write_text(self.editor.get("1.0", "end-1c"), encoding="utf-8")

    def _compilar(self) -> None:
        if self.ocupado:
            return
        self._guardar()
        self._trancar(True)

        def correr():
            return self.estudo.compilar()

        self.app.em_fundo(correr, self._compilou)

    def _compilou(self, resultado) -> None:
        if resultado is None:
            self._trancar(False)
            return
        attempt, resposta = resultado
        self.texto_saida.config(state="normal")
        self.texto_saida.delete("1.0", "end")
        self.texto_saida.insert("end", f"$ {attempt.comando}\n")
        if attempt.erro:
            self.texto_saida.insert("end", attempt.erro + "\n", "erro")
        else:
            self.texto_saida.insert("end", (attempt.saida or "(sem saída)") + "\n", "ok")
        self.texto_saida.config(state="disabled")
        self._chegou("gradus", resposta)

    def _terminar(self, passou: bool) -> None:
        if self.ocupado:
            return
        self._guardar()
        self._trancar(True)
        self.app.em_fundo(lambda: self.estudo.terminar(passou), self._terminou)

    def _terminou(self, relatorio) -> None:
        self._trancar(False)
        self.botao_compilar.config(state="disabled")
        self.botao_passou.config(state="disabled")
        self.botao_cortar.config(state="disabled")
        if relatorio is None:
            return
        p = relatorio.passage
        recado = [
            f"{p.no} · {p.tipo} · {p.resultado}",
            f"{p.compilacoes} tentativa(s), {p.kb_contexto} KB, {p.duracao_min} min",
        ]
        if relatorio.promocao:
            recado.append(relatorio.promocao)
        if not p.resultado == "passou":
            recado.append("O exercício fica aberto: a próxima passagem retoma-o com o bilhete.")
        messagebox.showinfo("gradus", "\n".join(recado))
        self._pintar_rodape()

    # --- pintura ----------------------------------------------------------
    def _chegou(self, papel: str, texto) -> None:
        self._trancar(False)
        if texto:
            self._escrever(papel, texto)
        self._pintar_rodape()
        if self.estudo.dialogo is not None and self.estudo.deve_cortar():
            self._escrever(
                "sistema",
                "O contexto chegou ao teto. Carrega em «Cortar aqui»: a sessão morre e a "
                "próxima retoma este exercício com um bilhete de 400 B.",
            )

    def _escrever(self, papel: str, texto: str) -> None:
        self.texto_conversa.config(state="normal")
        prefixo = {"aluno": "tu", "gradus": "gradus", "sistema": "gradus"}[papel]
        self.texto_conversa.insert("end", f"{prefixo}\n{texto}\n\n", papel)
        self.texto_conversa.see("end")
        self.texto_conversa.config(state="disabled")

    def _trancar(self, ocupado: bool) -> None:
        self.ocupado = ocupado
        a_decorrer = self.estudo.abertura is not None
        estado = "disabled" if ocupado or not a_decorrer else "normal"
        self.botao_compilar.config(state=estado)
        self.botao_passou.config(state=estado)
        self.botao_cortar.config(state=estado)
        self.botao_comecar.config(state="disabled" if ocupado or a_decorrer else "normal")

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

    def _pintar_rodape(self) -> None:
        r = self.estudo.rodape()
        self.etiqueta_briefing.config(text=f"briefing {r.briefing}" if r.briefing else "")
        self.etiqueta_fraquezas.config(
            text=("a treinar: " + ", ".join(r.fraquezas)) if r.fraquezas else "sem fraquezas ativas"
        )
        self.etiqueta_contexto.config(text=f"{r.kb:.1f} / {r.teto_kb:.0f} KB")
        self.cheio.config(width=int(180 * r.cheio), bg=tema.LARANJA if r.cheio > 0.8 else tema.VERDE)


class JanelaSimulador(tk.Toplevel):
    """Dez seguidas certas sobre o ficheiro dele. Nada aqui pergunta a um modelo:
    a resposta certa saiu de correr o código."""

    def __init__(self, pai, curso, trabalho: Path, node_id: str, exercicio: str) -> None:
        super().__init__(pai, bg=tema.FUNDO)
        self.title("gradus · simulador")
        self.geometry("720x760")
        self.app = pai.app
        self.sim = Simulacao(curso, trabalho, node_id, exercicio)

        titulo(self, "O que é que ele escreve agora?").pack(fill="x", padx=24, pady=(24, 4))
        self.etiqueta_conta = legenda(self, "")
        self.etiqueta_conta.pack(fill="x", padx=24)
        self.etiqueta_pergunta = legenda(self, "a preparar…", cor=tema.TEXTO)
        self.etiqueta_pergunta.pack(fill="x", padx=24, pady=(16, 8))

        self.codigo = tk.Text(
            self, bg=tema.PAINEL, fg=tema.TEXTO, font=_fonte(tema.CODIGO_PEQUENO), relief="flat",
            padx=14, pady=12, wrap="none", state="disabled", height=18, highlightthickness=0,
        )
        self.codigo.pack(fill="both", expand=True, padx=24)

        baixo = tk.Frame(self, bg=tema.FUNDO)
        baixo.pack(fill="x", padx=24, pady=16)
        self.entrada = tk.Entry(
            baixo, bg=tema.PAINEL, fg=tema.TEXTO, insertbackground=tema.LARANJA,
            font=_fonte(tema.CODIGO), relief="flat", highlightbackground=tema.LINHA,
            highlightthickness=1,
        )
        self.entrada.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 8))
        self.entrada.bind("<Return>", lambda _: self._responder())
        botao(baixo, "Responder", self._responder, principal=True).pack(side="left")

        self.resposta = legenda(self, "")
        self.resposta.pack(fill="x", padx=24, pady=(0, 20))
        self._proxima()

    def _proxima(self) -> None:
        self.entrada.delete(0, "end")
        self.etiqueta_pergunta.config(text="a preparar a próxima…")
        self.app.em_fundo(self.sim.proxima, self._mostrar)

    def _mostrar(self, previsao) -> None:
        if previsao is None:
            self.etiqueta_pergunta.config(
                text="Não consegui mudar nada neste ficheiro que ainda corresse. Escreve mais um bocado."
            )
            return
        self.etiqueta_pergunta.config(text=previsao.pergunta)
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
            self.resposta.config(text=f"certo · {r.seguidas} seguidas, faltam {r.em_falta}", fg=tema.VERDE)
        else:
            self.resposta.config(text=f"não — era: {r.certa}. A conta volta a zero.", fg=tema.LARANJA)
        self.etiqueta_conta.config(text=f"{r.seguidas} de 10")
        if r.promocao:
            messagebox.showinfo("gradus", r.promocao)
            self.destroy()
            return
        self.after(1200, self._proxima)


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
