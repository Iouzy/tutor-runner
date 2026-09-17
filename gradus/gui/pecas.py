"""The parts the screens are built from.

Raw tkinter widgets on a dark background look like raw tkinter widgets on a dark
background: a radiobutton is a tiny circle, a Frame has no edge, and an empty
panel is a hole. Everything here exists so the screens read as one surface —
cards with an edge, rows that light up when chosen, and panels that say what
they are waiting for instead of showing nothing.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont

from . import tema


def quebrar(rotulo):
    """Um Label não quebra sozinho: sem isto a pergunta mais comprida perde as
    últimas palavras pela direita fora, e é a pergunta que ele tem de ler. Numa
    DPI alta acontece mesmo a textos que cabiam no desenho."""
    def ajustar(evento):
        if evento.width > 1 and int(rotulo.cget("wraplength")) != evento.width:
            rotulo.config(wraplength=evento.width)

    rotulo.bind("<Configure>", ajustar)
    return rotulo


def fonte(spec):
    familia, *resto = spec
    return (tema.ALTERNATIVAS.get(familia, (familia,))[0], *resto)


# --- superfícies -----------------------------------------------------------
class Cartao(tk.Frame):
    """Um painel com aresta e cantos redondos.

    Um Frame do tk é sempre um retângulo, por isso a aresta é desenhada num
    canvas por trás e o conteúdo vive num frame afastado do bordo pelo raio —
    assim os cantos ficam à vista e o pack continua a mandar no tamanho, que é
    o que se perde se se puser o conteúdo dentro do próprio canvas."""

    RAIO = 12

    def __init__(self, pai, cor=None, borda=None, folga=None) -> None:
        super().__init__(pai, bg=pai["bg"])
        self.cor = cor or tema.PAINEL
        self.tela = tk.Canvas(self, bg=pai["bg"], highlightthickness=0, bd=0)
        self.tela.place(x=0, y=0, relwidth=1, relheight=1)
        self.forma = self.tela.create_polygon(
            (0, 0), smooth=True, splinesteps=16, fill=self.cor, outline=borda or tema.LINHA,
        )
        # criado depois do canvas, por isso fica por cima dele
        self.dentro = tk.Frame(self, bg=self.cor)
        folga = self.RAIO if folga is None else folga
        self.dentro.pack(fill="both", expand=True, padx=folga, pady=folga)
        self.bind("<Configure>", self._redesenhar)

    def _redesenhar(self, evento) -> None:
        self.tela.coords(
            self.forma, cantos(1, 1, evento.width - 2, evento.height - 2, self.RAIO)
        )

    def borda(self, cor: str) -> None:
        self.tela.itemconfig(self.forma, outline=cor)


def cartao(pai, cor=None, borda=None) -> Cartao:
    return Cartao(pai, cor=cor, borda=borda)


def moldura(pai, cor=None) -> Cartao:
    """A mesma aresta redonda à volta de uma caixa onde ele escreve, e que acende
    quando lá está o cursor. Um Entry do tk também é um retângulo."""
    return Cartao(pai, cor=cor or tema.PAINEL, folga=6)


def acender(moldura_: Cartao, widget) -> None:
    widget.bind("<FocusIn>", lambda _e: moldura_.borda(tema.LARANJA), add="+")
    widget.bind("<FocusOut>", lambda _e: moldura_.borda(tema.LINHA), add="+")


def separador(pai) -> tk.Frame:
    return tk.Frame(pai, bg=tema.LINHA, height=1)


def espaco(pai, altura=0) -> tk.Frame:
    """An expanding gap, so what belongs at the bottom sits at the bottom."""
    return tk.Frame(pai, bg=pai["bg"], height=altura)


# --- texto -----------------------------------------------------------------
def titulo(pai, texto, tamanho="medio", cor=None, largura=0) -> tk.Label:
    """`largura` 0 = quebra sozinho pela largura que lhe derem."""
    spec = {"grande": tema.TITULO_GRANDE, "medio": tema.TITULO, "pequeno": tema.TITULO_PEQUENO}[tamanho]
    etiqueta = tk.Label(
        pai, text=texto, bg=pai["bg"], fg=cor or tema.TEXTO, font=fonte(spec),
        anchor="w", justify="left", wraplength=largura,
    )
    return etiqueta if largura else quebrar(etiqueta)


def paragrafo(pai, texto, cor=None, fonte_=None, largura=0) -> tk.Label:
    etiqueta = tk.Label(
        pai, text=texto, bg=pai["bg"], fg=cor or tema.APAGADO, font=fonte(fonte_ or tema.INTERFACE),
        anchor="w", justify="left", wraplength=largura,
    )
    return etiqueta if largura else quebrar(etiqueta)


def rotulo(pai, texto, cor=None) -> tk.Label:
    """The small uppercase label over a block. Cheap, and it makes a layout read."""
    return tk.Label(
        pai, text=texto.upper(), bg=pai["bg"], fg=cor or tema.APAGADO,
        font=fonte(tema.ROTULO), anchor="w",
    )


def mono(pai, texto, cor=None, fonte_=None) -> tk.Label:
    return tk.Label(
        pai, text=texto, bg=pai["bg"], fg=cor or tema.APAGADO,
        font=fonte(fonte_ or tema.CODIGO_PEQUENO), anchor="w",
    )


# --- botões ----------------------------------------------------------------
def cantos(x1, y1, x2, y2, raio):
    """Os pontos de um retângulo de cantos redondos, para um polígono suavizado.
    O tk desenha o spline por nós; repetir os cantos é o que lhes dá a curva."""
    return [
        x1 + raio, y1, x2 - raio, y1, x2, y1, x2, y1 + raio,
        x2, y2 - raio, x2, y2, x2 - raio, y2, x1 + raio, y2,
        x1, y2, x1, y2 - raio, x1, y1 + raio, x1, y1,
    ]


class Botao(tk.Canvas):
    """Um botão desenhado, porque o tk.Button é um retângulo e não há como o
    arredondar. Aqui o fundo é um polígono suavizado e o texto é um item do
    canvas — assim há cantos redondos, e o estado desligado apaga o botão
    inteiro em vez de só o texto, que num painel escuro lia-se como avariado."""

    RAIO = 10
    PAD_X, PAD_Y = 22, 11

    def __init__(self, pai, texto, comando, papel="normal", estado="normal") -> None:
        self.papel, self.comando = papel, comando
        self._texto = texto
        self._ligado = estado == "normal"
        self._sobre = False
        self.fonte = tkfont.Font(font=fonte(tema.INTERFACE_FORTE))
        super().__init__(
            pai, bg=pai["bg"], highlightthickness=0, bd=0,
            width=self._largura(texto), height=self._altura(),
        )
        self.forma = self.create_polygon(
            cantos(1, 1, self._largura(texto) - 1, self._altura() - 1, self.RAIO),
            smooth=True, splinesteps=16, fill=tema.PAINEL, outline="",
        )
        self.etiqueta = self.create_text(
            self._largura(texto) / 2, self._altura() / 2, text=texto,
            fill=tema.TEXTO, font=self.fonte,
        )
        self.bind("<Button-1>", self._carregado)
        self.bind("<Enter>", lambda _e: self._realce(True))
        self.bind("<Leave>", lambda _e: self._realce(False))
        self._pintar()

    # --- medidas ---------------------------------------------------------
    def _largura(self, texto: str) -> int:
        return self.fonte.measure(texto) + 2 * self.PAD_X

    def _altura(self) -> int:
        return self.fonte.metrics("linespace") + 2 * self.PAD_Y

    # --- estado ----------------------------------------------------------
    def estado(self, novo: str) -> None:
        self._ligado = novo == "normal"
        self._pintar()

    def por_texto(self, texto: str) -> None:
        """Mudar o texto muda a largura: um botão do tamanho do texto anterior
        fica com a palavra a sair-lhe pelos lados."""
        if texto == self._texto:
            return
        self._texto = texto
        largura = self._largura(texto)
        self.config(width=largura)
        self.coords(self.forma, cantos(1, 1, largura - 1, self._altura() - 1, self.RAIO))
        self.coords(self.etiqueta, largura / 2, self._altura() / 2)
        self.itemconfig(self.etiqueta, text=texto)
        self._pintar()

    def _carregado(self, _evento) -> None:
        if self._ligado and self.comando is not None:
            self.comando()

    def _realce(self, sobre: bool) -> None:
        self._sobre = sobre
        self._pintar()

    def _pintar(self) -> None:
        realce = self._sobre and self._ligado
        if self.papel == "principal":
            fundo = (tema.LARANJA_CLARO if realce else tema.LARANJA) if self._ligado else tema.LINHA
            frente = tema.FUNDO if self._ligado else tema.APAGADO
        elif self.papel == "fantasma":
            fundo = tema.LINHA if realce else self["bg"]
            frente = tema.TEXTO if self._ligado else tema.APAGADO
        else:
            fundo = (tema.LINHA if realce else tema.PAINEL) if self._ligado else tema.FUNDO
            frente = tema.TEXTO if self._ligado else tema.APAGADO
        self.itemconfig(self.forma, fill=fundo)
        self.itemconfig(self.etiqueta, fill=frente)
        self.config(cursor="hand2" if self._ligado else "arrow")


# --- escolhas --------------------------------------------------------------
class ListaEscolha(tk.Frame):
    """Linhas que se carregam, com uma barra ao lado da escolhida. Um radiobutton
    do tk é um círculo de cinco píxeis: neste fundo ninguém vê qual está picada.

    Cada linha é um canvas pela mesma razão que os botões: para ter os mesmos
    cantos redondos que o resto do desenho."""

    RAIO = 10

    def __init__(self, pai, opcoes: tuple[str, ...], escolhida: str = "") -> None:
        super().__init__(pai, bg=pai["bg"])
        self.valor = escolhida
        self.fonte = tkfont.Font(font=fonte(tema.INTERFACE))
        self.altura = self.fonte.metrics("linespace") + 28
        self.linhas: dict[str, tk.Canvas] = {}
        for opcao in opcoes:
            self.linhas[opcao] = self._linha(opcao)
        self._pintar()

    def _linha(self, opcao: str) -> tk.Canvas:
        tela = tk.Canvas(self, bg=self["bg"], height=self.altura, highlightthickness=0, bd=0)
        tela.pack(fill="x", pady=4)
        tela.forma = tela.create_polygon((0, 0), smooth=True, splinesteps=16, fill=tema.PAINEL, outline=tema.LINHA)
        tela.marca = tela.create_polygon((0, 0), smooth=True, splinesteps=8, fill=tema.PAINEL, outline="")
        tela.etiqueta = tela.create_text(
            24, self.altura / 2, text=opcao, anchor="w", fill=tema.TEXTO, font=self.fonte
        )
        tela.config(cursor="hand2")
        tela.bind("<Button-1>", lambda _e, o=opcao: self.escolher(o))
        tela.bind("<Configure>", lambda e, t=tela: self._redesenhar(t, e.width))
        tela.bind("<Enter>", lambda _e, o=opcao: self._realce(o, True))
        tela.bind("<Leave>", lambda _e, o=opcao: self._realce(o, False))
        tela.sobre = False
        return tela

    def _redesenhar(self, tela: tk.Canvas, largura: int) -> None:
        tela.coords(tela.forma, cantos(1, 1, largura - 2, self.altura - 2, self.RAIO))
        tela.coords(tela.marca, cantos(2, 8, 5, self.altura - 8, 2))

    def escolher(self, opcao: str) -> None:
        self.valor = opcao
        self._pintar()

    def _realce(self, opcao: str, sobre: bool) -> None:
        self.linhas[opcao].sobre = sobre
        self._pintar()

    def _pintar(self) -> None:
        for opcao, tela in self.linhas.items():
            escolhida = opcao == self.valor
            tela.itemconfig(
                tela.forma,
                outline=tema.LARANJA if escolhida else tema.LINHA,
                fill=tema.LINHA if (tela.sobre and not escolhida) else tema.PAINEL,
            )
            tela.itemconfig(tela.marca, fill=tema.LARANJA if escolhida else tema.PAINEL)
            tela.itemconfig(tela.etiqueta, fill=tema.TEXTO if escolhida or tela.sobre else tema.APAGADO)


# --- medidores -------------------------------------------------------------
class Medidor(tk.Frame):
    """A bar that fills, and turns orange before it is a problem."""

    def __init__(self, pai, largura=180, altura=4) -> None:
        super().__init__(pai, bg=tema.LINHA, width=largura, height=altura)
        self.pack_propagate(False)
        self.largura = largura
        self.cheio = tk.Frame(self, bg=tema.VERDE, width=0, height=altura)
        self.cheio.pack(side="left", fill="y")

    def por(self, fracao: float) -> None:
        fracao = max(0.0, min(1.0, fracao))
        self.cheio.config(
            width=int(self.largura * fracao),
            bg=tema.LARANJA if fracao > 0.8 else tema.VERDE,
        )


class Passos(tk.Frame):
    """Three dashes in the corner: which of the three startup screens this is."""

    def __init__(self, pai, passo: int, total: int = 3) -> None:
        super().__init__(pai, bg=pai["bg"])
        for i in range(1, total + 1):
            cor = tema.VERDE if i < passo else (tema.LARANJA if i == passo else tema.LINHA)
            tk.Frame(self, bg=cor, width=34, height=4).pack(side="left", padx=4)


# --- painéis de texto ------------------------------------------------------
class Painel(tk.Frame):
    """A read-only text panel that says what it is waiting for when it is empty."""

    def __init__(self, pai, vazio: str, fonte_=None, cor=None, fundo=None, altura=8) -> None:
        super().__init__(pai, bg=fundo or tema.PAINEL)
        self.vazio = vazio
        self.texto = tk.Text(
            self, height=altura, width=1,      # estica: quem manda é o painel, não o texto
            bg=fundo or tema.PAINEL, fg=cor or tema.TEXTO, font=fonte(fonte_ or tema.INTERFACE),
            relief="flat", bd=0, padx=20, pady=18, wrap="word", state="disabled",
            highlightthickness=0, insertbackground=tema.LARANJA, spacing1=2, spacing3=4,
        )
        self.texto.pack(fill="both", expand=True)
        self.texto.tag_configure("vazio", foreground=tema.APAGADO, justify="center")
        self.limpar()

    def limpar(self) -> None:
        self.texto.config(state="normal")
        self.texto.delete("1.0", "end")
        self.texto.insert("end", f"\n{self.vazio}\n", "vazio")
        self.texto.config(state="disabled")
        self._vazio = True

    def escrever(self, texto: str, etiqueta: str = "") -> None:
        self.texto.config(state="normal")
        if self._vazio:
            self.texto.delete("1.0", "end")
            self._vazio = False
        self.texto.insert("end", texto, etiqueta)
        self.texto.see("end")
        self.texto.config(state="disabled")


def caixa_de_texto(pai, altura=7, mono_=False) -> tk.Text:
    return tk.Text(
        pai, height=altura, width=1, bg=tema.PAINEL, fg=tema.TEXTO, insertbackground=tema.LARANJA,
        font=fonte(tema.CODIGO if mono_ else tema.INTERFACE), relief="flat", bd=0,
        padx=14, pady=10, wrap="none" if mono_ else "word", highlightthickness=0,
        spacing1=2, spacing3=4, undo=True,
    )


def entrada(pai) -> tk.Entry:
    return tk.Entry(
        pai, bg=tema.PAINEL, fg=tema.TEXTO, insertbackground=tema.LARANJA,
        font=fonte(tema.INTERFACE), relief="flat", bd=0, highlightthickness=0,
    )
