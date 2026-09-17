"""A stand-in for the `claude` binary: same flags, canned answers, no network.

It exists so the adapter and the conversation are exercised by the tests without
ever spending a session — nothing in tests/ may need credentials or a real claude.
"""
from __future__ import annotations

import json
import sys


def main() -> int:
    args = sys.argv[1:]
    mensagem = args[-1] if args else ""
    sessao = args[args.index("--resume") + 1] if "--resume" in args else "sessao-1"

    if "--restricted" not in args:
        print("o gradus tem de correr o modelo com --restricted", file=sys.stderr)
        return 2

    if mensagem.startswith("Acabou."):
        resultado = json.dumps({
            "juizos": [
                {"fraqueza": "limites-ciclos", "tipo_duvida": "conceito", "resolvido_na_passagem": False},
                {"fraqueza": "inventada-por-mim", "tipo_duvida": "preguiça"},
            ],
            "duvidas_novas": ["length é campo ou método?"],
        })
    elif mensagem.startswith("Foi preciso cortar"):
        resultado = "Claro, aqui vai:\n" + json.dumps({
            "onde_ficou": "tem o for escrito, falta o acumulador",
            "ultimo_erro": "cannot find symbol: soma",
            "ja_explicado": ["for-each", "âmbito do bloco", "x" * 300],
            "nao_repetir": "analogia da prateleira",
        })
    elif mensagem.startswith("compilador:"):
        resultado = "O erro está na linha do acumulador. O que é que ele vale antes do ciclo?"
    else:
        resultado = "Olha para o array e diz-me o que achas que sai antes de correres."

    print(json.dumps({
        "type": "result",
        "result": resultado,
        "session_id": sessao,
        "usage": {"input_tokens": 120, "output_tokens": 40},
        "total_cost_usd": 0.0123,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
