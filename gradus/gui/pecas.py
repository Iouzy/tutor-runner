"""The parts the screens are built from.

Raw tkinter widgets on a dark background look like raw tkinter widgets on a dark
background: a radiobutton is a tiny circle, a Frame has no edge, and an empty
panel is a hole. Everything here exists so the screens read as one surface —
cards with an edge, rows that light up when chosen, and panels that say what
they are waiting for instead of showing nothing.
"""
from __future__ import annotations

import tkinter as tk

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
def cartao(pai, cor=None, borda=None) -> tk.Frame:
    """A panel with an edge. Without the edge everything floats on the same dark."""
    return tk.Frame(
        pai, bg=cor or tema.PAINEL, highlightbackground=borda or tema.LINHA,
        highlightcolor=borda or tema.LINHA, highlightthickness=1, bd=0,
    )


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
class Botao(tk.Button):
    """tkinter only greys the text of a disabled button, which on a dark panel
    reads as 'broken', not as 'not yet'. This greys the whole thing."""

    def __init__(self, pai, texto, comando, papel="normal", estado="normal") -> None:
        self.papel = papel
        super().__init__(
            pai, text=texto, command=comando, font=fonte(tema.INTERFACE_FORTE),
            relief="flat", bd=0, padx=22, pady=11, highlightthickness=0,
            activeforeground=tema.FUNDO if papel == "principal" else tema.TEXTO,
            activebackground=tema.LARANJA_CLARO if papel == "principal" else tema.LINHA,
        )
        self.estado(estado)

    def estado(self, novo: str) -> None:
        ligado = novo == "normal"
        if self.papel == "principal":
            fundo = tema.LARANJA if ligado else tema.LINHA
            frente = tema.FUNDO if ligado else tema.APAGADO
        elif self.papel == "fantasma":
            fundo = self.master["bg"]
            frente = tema.TEXTO if ligado else tema.APAGADO
        else:
            fundo = tema.PAINEL if ligado else tema.FUNDO
            frente = tema.TEXTO if ligado else tema.APAGADO
        self.config(
            state=novo, bg=fundo, fg=frente, disabledforeground=frente,
            cursor="hand2" if ligado else "arrow",
        )


# --- escolhas --------------------------------------------------------------
class ListaEscolha(tk.Frame):
    """Rows you click, with a bar down the chosen one. A tk radiobutton is a
    five-pixel circle: on this background nobody sees which one is picked."""

    def __init__(self, pai, opcoes: tuple[str, ...], escolhida: str = "") -> None:
        super().__init__(pai, bg=pai["bg"])
        self.valor = escolhida
        self.linhas: dict[str, tuple[tk.Frame, tk.Frame, tk.Label]] = {}
        for opcao in opcoes:
            self._linha(opcao)
        self._pintar()

    def _linha(self, opcao: str) -> None:
        fora = tk.Frame(self, bg=tema.PAINEL, highlightbackground=tema.LINHA, highlightthickness=1)
        fora.pack(fill="x", pady=4)
        marca = tk.Frame(fora, bg=tema.PAINEL, width=3)
        marca.pack(side="left", fill="y")
        etiqueta = tk.Label(
            fora, text=opcao, bg=tema.PAINEL, fg=tema.TEXTO, font=fonte(tema.INTERFACE),
            anchor="w", padx=18, pady=14,
        )
        etiqueta.pack(side="left", fill="x", expand=True)
        for alvo in (fora, etiqueta):
            alvo.bind("<Button-1>", lambda _e, o=opcao: self.escolher(o))
            alvo.config(cursor="hand2")
        self.linhas[opcao] = (fora, marca, etiqueta)

    def escolher(self, opcao: str) -> None:
        self.valor = opcao
        self._pintar()

    def _pintar(self) -> None:
        for opcao, (fora, marca, etiqueta) in self.linhas.items():
            escolhida = opcao == self.valor
            fora.config(highlightbackground=tema.LARANJA if escolhida else tema.LINHA)
            marca.config(bg=tema.LARANJA if escolhida else tema.PAINEL)
            etiqueta.config(fg=tema.TEXTO if escolhida else tema.APAGADO)


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
        padx=18, pady=14, wrap="none" if mono_ else "word",
        highlightbackground=tema.LINHA, highlightcolor=tema.LARANJA, highlightthickness=1,
        spacing1=2, spacing3=4, undo=True,
    )


def entrada(pai) -> tk.Entry:
    return tk.Entry(
        pai, bg=tema.FUNDO, fg=tema.TEXTO, insertbackground=tema.LARANJA,
        font=fonte(tema.INTERFACE), relief="flat", bd=0,
        highlightbackground=tema.LINHA, highlightcolor=tema.LARANJA, highlightthickness=1,
    )
