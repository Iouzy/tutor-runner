"""One place for the colours and the type. The screens hold no hex codes."""
from __future__ import annotations

FUNDO = "#121C1A"
PAINEL = "#172321"
TEXTO = "#F0EDE4"
APAGADO = "#94A49E"
LARANJA = "#D9784F"
LARANJA_CLARO = "#E68C66"
VERDE = "#6FBBA8"
LINHA = "#2A3835"

# Em pontos, não em píxeis: o tkinter escala isto com o DPI do ecrã.
TITULO_GRANDE = ("Space Grotesk", 24, "bold")
TITULO = ("Space Grotesk", 15, "bold")
TITULO_PEQUENO = ("Space Grotesk", 12, "bold")
INTERFACE = ("IBM Plex Sans", 11)
INTERFACE_FORTE = ("IBM Plex Sans", 11, "bold")
PEQUENO = ("IBM Plex Sans", 9)
ROTULO = ("IBM Plex Sans", 8, "bold")
CODIGO = ("JetBrains Mono", 11)
CODIGO_PEQUENO = ("JetBrains Mono", 9)

# O tkinter cai numa fonte qualquer se a família não existir. Estas são as
# alternativas por ordem, para a janela não ficar com a fonte por omissão do X.
ALTERNATIVAS = {
    "Space Grotesk": ("Space Grotesk", "Inter", "DejaVu Sans", "Helvetica"),
    "IBM Plex Sans": ("IBM Plex Sans", "Inter", "DejaVu Sans", "Helvetica"),
    "JetBrains Mono": ("JetBrains Mono", "IBM Plex Mono", "DejaVu Sans Mono", "Courier"),
}

PACOTES = {
    "Space Grotesk": "fonts-space-grotesk",
    "IBM Plex Sans": "fonts-ibm-plex",
    "JetBrains Mono": "fonts-jetbrains-mono",
}


def familia_disponivel(pedida: str, existentes: set[str]) -> str:
    for nome in ALTERNATIVAS.get(pedida, (pedida,)):
        if nome in existentes:
            return nome
    return pedida


def em_falta(existentes: set[str]) -> list[str]:
    return [pedida for pedida in ALTERNATIVAS if pedida not in existentes]
