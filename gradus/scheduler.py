"""What to study next. A function over the graph, not a call to a model."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .model import Course, Mastery, Node
from .state import NodeState, State

PRONTO = Mastery.ESCRITO_SOZINHO   # a prerequisite counts as met from here up

# He postpones: 11 messages before the first line of code, measured. Prediction and
# planted error cost two minutes to start, so they go first and lower the wall;
# construction only then. Rewriting your own code needs a night of forgetting in
# between, so it sits last and has a gate of its own.
ORDEM_TIPOS = ("previsao", "erro-plantado", "construcao", "explicar", "reescrita")


@dataclass(frozen=True)
class Choice:
    node_id: str
    motivo: str
    revisao: bool = False
    tipo: str = "construcao"


def _dias_desde(iso: str | None, hoje: date) -> int:
    if not iso:
        return 10**6
    return (hoje - date.fromisoformat(iso)).days


def _disponiveis(node: Node) -> list[str]:
    tipos = [t for t in ORDEM_TIPOS if t in node.tipos]
    return tipos or ["construcao"]


def _elegivel(tipo: str, ns: NodeState, hoje: date) -> bool:
    """A rewrite of code written an hour ago is copying, not rewriting."""
    if tipo != "reescrita":
        return True
    construcao = ns.tipos_feitos.get("construcao")
    return bool(construcao) and construcao < hoje.isoformat()


def tipo_para(node: Node, ns: NodeState, hoje: date) -> str | None:
    """The next kind of exercise for this node, or None if it has nothing for today."""
    disponiveis = _disponiveis(node)

    por_fazer = [t for t in disponiveis if t not in ns.tipos_feitos and _elegivel(t, ns, hoje)]
    if por_fazer:
        return por_fazer[0]

    repetiveis = [t for t in disponiveis if _elegivel(t, ns, hoje)]
    if not repetiveis:
        return None
    # All done once: repeat the one left longest. A type seen today is the worst
    # possible use of the next passage.
    repetiveis.sort(key=lambda t: (ns.tipos_feitos.get(t, ""), ORDEM_TIPOS.index(t)))
    return repetiveis[0]


def _em_bloco(state: State, node_id: str, tipo: str) -> bool:
    """Block practice: two constructions of the same node back to back teaches the
    shape of the session, not the node."""
    return tipo == "construcao" and state.ultimo_no == node_id and state.ultimo_tipo == "construcao"


def next_node(course: Course, state: State, hoje: date | None = None) -> Choice | None:
    """An open exercise wins; then decayed revision; then the best new node."""
    hoje = hoje or date.today()

    if state.no_aberto:
        node = course.node(state.no_aberto)
        tipo = state.tipo_aberto or tipo_para(node, state.node(node.id), hoje) or "construcao"
        return Choice(state.no_aberto, "exercício aberto de uma passagem anterior", tipo=tipo)

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
        node = course.node(n_id)
        tipo = tipo_para(node, state.node(n_id), hoje) or "previsao"
        return Choice(n_id, f"revisão: automático há {dias} dias", revisao=True, tipo=tipo)

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

    adiado: tuple[int, str, str] | None = None
    for treina, _, node_id in candidatos:
        node = course.node(node_id)
        tipo = tipo_para(node, state.node(node_id), hoje)
        if tipo is None:
            continue
        if _em_bloco(state, node_id, tipo):
            adiado = adiado or (treina, node_id, tipo)
            continue
        return Choice(node_id, _motivo(course, node_id, treina, ativas, tipo), tipo=tipo)

    if adiado is None:      # only nodes whose types are all spent today
        treina, _, node_id = candidatos[0]
        adiado = (treina, node_id, "construcao")
    treina, node_id, tipo = adiado
    motivo = _motivo(course, node_id, treina, ativas, tipo)
    return Choice(node_id, f"{motivo}; sem nada com que intercalar", tipo=tipo)


def _motivo(course: Course, node_id: str, treina: int, ativas: set[str], tipo: str) -> str:
    if treina:
        alvos = ", ".join(sorted(ativas.intersection(course.node(node_id).treina)))
        return f"pré-requisitos cumpridos; treina {alvos}"
    return "pré-requisitos cumpridos; próximo por ordem do grafo"
