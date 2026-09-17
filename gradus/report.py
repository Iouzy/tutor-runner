"""ESTADO.md and HISTORICO.md are GENERATED. A model never writes them.

Model-written state files re-summarise themselves until nothing survives; generated
from the graph and the ledger, drift is impossible.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .event import Passage
from .model import Course, Mastery
from .state import State


def estado_md(course: Course, state: State, proximo: str | None) -> str:
    por_nivel: dict[Mastery, list[str]] = defaultdict(list)
    for node_id, node in course.nodes.items():
        por_nivel[state.node(node_id).dominio].append(node.nome)

    linhas = [
        f"# Estado — {course.nome}",
        "",
        "<!-- GERADO por `gradus estado`. Não editar à mão: a próxima geração apaga. -->",
        "",
        "## Domínio",
    ]
    for nivel in reversed(Mastery):
        nomes = sorted(por_nivel.get(nivel, []))
        if nomes:
            linhas.append(f"- **{nivel.label}** — {', '.join(nomes)}")

    linhas += ["", "## Próximo passo", f"- {proximo or 'nada elegível — o grafo acabou ou está bloqueado'}", "", "## Fraquezas ativas"]
    ativas = state.fraquezas_ativas(limite=99)
    if not ativas:
        linhas.append("- nenhuma com evidência recente")
    for w_id in ativas:
        w = state.weakness(w_id)
        linhas.append(f"- {course.weaknesses[w_id].nome} — {w.ocorrencias} ocorrência(s), última {w.ultimas[-1]}")
    return "\n".join(linhas) + "\n"


def historico_md(course: Course, passagens: list[Passage]) -> str:
    fraquezas = list(course.weaknesses)
    cab = ["Dia", "Passagens", "Exercícios passados", "Compilações", "Versões", "Adiamento", "KB/exercício"]
    cab += [course.weaknesses[f].nome for f in fraquezas]

    por_dia: dict[str, list[Passage]] = defaultdict(list)
    for p in passagens:
        por_dia[p.dia].append(p)

    linhas = [
        "# Histórico",
        "",
        "<!-- GERADO por `gradus historico` a partir de eventos/. Não editar à mão. -->",
        "",
        "| " + " | ".join(cab) + " |",
        "|" + "---|" * len(cab),
    ]
    for dia in sorted(por_dia):
        ps = por_dia[dia]
        passados = [p for p in ps if p.resultado == "passou"]
        kb = sum(p.kb_contexto for p in ps)
        kb_por_ex = f"{kb / len(passados):.1f}" if passados else "-"
        antes = sum(p.msgs_antes_do_1o_codigo for p in ps)
        total = sum(p.msgs_total for p in ps)
        conta: dict[str, int] = defaultdict(int)
        for p in ps:
            for j in p.juizos:
                if j.fraqueza:
                    conta[j.fraqueza] += 1
        celulas = [
            dia,
            str(len(ps)),
            str(len(passados)),
            str(sum(p.compilacoes for p in ps)),
            str(sum(p.versoes_ate_correr for p in ps)),
            f"{antes}/{total}" if total else "-",
            kb_por_ex,
        ]
        celulas += [str(conta.get(f, 0)) or "-" for f in fraquezas]
        linhas.append("| " + " | ".join(celulas) + " |")
    return "\n".join(linhas) + "\n"
