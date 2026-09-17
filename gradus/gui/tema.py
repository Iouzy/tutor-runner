"""One place for the colours and the type. The screens hold no hex codes."""
from __future__ import annotations

FUNDO = "#121C1A"
PAINEL = "#172321"
TEXTO = "#F0EDE4"
APAGADO = "#94A49E"
LARANJA = "#D9784F"
VERDE = "#6FBBA8"
LINHA = "#2A3835"

TITULO = ("Space Grotesk", 20, "bold")
TITULO_GRANDE = ("Space Grotesk", 30, "bold")
INTERFACE = ("IBM Plex Sans", 12)
INTERFACE_FORTE = ("IBM Plex Sans", 12, "bold")
PEQUENO = ("IBM Plex Sans", 10)
CODIGO = ("JetBrains Mono", 12)
CODIGO_PEQUENO = ("JetBrains Mono", 10)

# tkinter cai numa fonte qualquer se a família não existir; estas são as
# alternativas por ordem, para a janela não ficar com a fonte por omissão do X.
ALTERNATIVAS = {
    "Space Grotesk": ("Space Grotesk", "DejaVu Sans", "Helvetica"),
    "IBM Plex Sans": ("IBM Plex Sans", "DejaVu Sans", "Helvetica"),
    "JetBrains Mono": ("JetBrains Mono", "DejaVu Sans Mono", "Courier"),
}


def familia_disponivel(pedida: str, existentes: set[str]) -> str:
    for nome in ALTERNATIVAS.get(pedida, (pedida,)):
        if nome in existentes:
            return nome
    return pedida
