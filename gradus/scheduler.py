"""What to study next. A function over the graph, not a call to a model."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .model import Course, Mastery
from .state import State

PRONTO = Mastery.ESCRITO_SOZINHO   # a prerequisite counts as met from here up


@dataclass(frozen=True)
class Choice:
    node_id: str
    motivo: str
    revisao: bool = False


def _dias_desde(iso: str | None, hoje: date) -> int:
    if not iso:
        return 10**6
    return (hoje - date.fromisoformat(iso)).days


def next_node(course: Course, state: State, hoje: date | None = None) -> Choice | None:
    """An open exercise wins; then decayed revision; then the best new node."""
    hoje = hoje or date.today()

    if state.no_aberto:
        return Choice(state.no_aberto, "exercício aberto de uma passagem anterior")

    # Spaced repetition: something mastered long enough ago is worth more than
    # new ground, because forgetting is the failure mode this project is named for.
    vencidos = [
        (n_id, _dias_desde(st.visto_em, hoje))
        for n_id, st in state.nos.items()
        if st.dominio >= Mastery.AUTOMATICO and _dias_desde(st.visto_em, hoje) >= course.decaimento_dias
    ]
    if vencidos:
        vencidos.sort(key=lambda kv: kv[1], reverse=True)
        n_id, dias = vencidos[0]
        return Choice(n_id, f"revisão: automático há {dias} dias", revisao=True)

    ativas = set(state.fraquezas_ativas(limite=6))
    candidatos = []
    for node in course.nodes.values():
        st = state.node(node.id)
        if st.dominio >= PRONTO:
            continue
        if not all(state.node(dep).dominio >= PRONTO for dep in node.depende_de):
            continue
        treina = len(ativas.intersection(node.treina))
        # Finishing a started node beats opening another front.
        candidatos.append((treina, int(st.dominio), node.id))

    if not candidatos:
        return None

    candidatos.sort(key=lambda t: (-t[0], -t[1], t[2]))
    treina, _, node_id = candidatos[0]
    node = course.node(node_id)
    if treina:
        alvos = ", ".join(sorted(ativas.intersection(node.treina)))
        motivo = f"pré-requisitos cumpridos; treina {alvos}"
    else:
        motivo = "pré-requisitos cumpridos; próximo por ordem do grafo"
    return Choice(node_id, motivo)
