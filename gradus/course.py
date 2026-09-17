"""Loads a course.

Three things are merged, and the split is the point: the generic graph of
programming fundamentals (`base/`), the learner who carries their own profile and
weaknesses between languages (`aluno/`), and the language itself (`cursos/<x>/`),
which is six lines plus whatever traps and anchors it wants to lay on top.
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

from .model import TIPOS_EXERCICIO, Anchor, Course, CourseError, Node, Verification, Weakness


def _toml(path: Path) -> dict:
    if not path.exists():
        raise CourseError(f"falta {path} — cria-o, ou corrige quem lhe chama")
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _weaknesses(blocos: list[dict]) -> dict[str, Weakness]:
    return {
        w["id"]: Weakness(id=w["id"], nome=w["nome"], descricao=w.get("descricao", ""))
        for w in blocos
    }


def _node(raw: dict) -> Node:
    return Node(
        id=raw["id"],
        nome=raw["nome"],
        objetivo=raw["objetivo"],
        depende_de=tuple(raw.get("depende_de", [])),
        armadilhas=tuple(raw.get("armadilhas", [])),
        treina=tuple(raw.get("treina", [])),
        tipos=tuple(raw.get("tipos", [])),
        ancoras=tuple(_anchor(a, raw["id"]) for a in raw.get("ancora", [])),
    )


def _anchor(raw: dict, node_id: str) -> Anchor:
    if not raw.get("controlo"):
        raise CourseError(
            f"a âncora '{raw.get('enunciado', '?')[:40]}…' do nó '{node_id}' não tem valores de "
            f"controlo — acrescenta controlo = [ {{ entrada = \"…\", saida = \"…\" }} ], "
            f"senão quem decide se está certo é um modelo"
        )
    if raw.get("tipo") not in TIPOS_EXERCICIO:
        raise CourseError(
            f"a âncora do nó '{node_id}' tem tipo '{raw.get('tipo')}' — "
            f"usa um de {', '.join(TIPOS_EXERCICIO)}"
        )
    return Anchor(
        tipo=raw["tipo"],
        enunciado=raw["enunciado"],
        ficheiro=raw.get("ficheiro", ""),
        controlo=tuple(raw["controlo"]),
    )


def _verificacao(raw: dict | None) -> Verification | None:
    if not raw:
        return None
    for chave in ("ficheiro", "codigo"):
        if chave not in raw:
            raise CourseError(
                f"[verificacao] não define '{chave}' — sem ele o doctor não consegue "
                f"partir um ficheiro de propósito, e o regex_erro nunca é posto à prova"
            )
    return Verification(
        ficheiro=raw["ficheiro"], codigo=raw["codigo"], espera=raw.get("espera", "")
    )


def _overlay(base: Node, over: dict, node_id: str) -> Node:
    """The language lays traps and anchors on a generic node; it never rewrites it."""
    return Node(
        id=base.id,
        nome=over.get("nome", base.nome),
        objetivo=over.get("objetivo", base.objetivo),
        depende_de=base.depende_de,
        armadilhas=tuple(over.get("armadilhas", base.armadilhas)),
        treina=tuple(dict.fromkeys(base.treina + tuple(over.get("treina", ())))),
        tipos=tuple(over.get("tipos", base.tipos)),
        ancoras=base.ancoras + tuple(_anchor(a, node_id) for a in over.get("ancora", [])),
    )


def load(course_dir: Path, *, raiz: Path | None = None) -> Course:
    course_dir = Path(course_dir)
    raiz = raiz or course_dir.parent.parent

    curso = _toml(course_dir / "curso.toml")
    for chave in ("nome", "build", "run", "regex_erro"):
        if chave not in curso:
            raise CourseError(f"curso.toml não define '{chave}' — acrescenta a linha {chave} = \"...\"")

    try:
        re.compile(curso["regex_erro"])
    except re.error as exc:
        raise CourseError(f"regex_erro não compila ({exc}) — corrige a expressão em curso.toml") from None

    aluno = raiz / "aluno"
    perfil_path = aluno / "perfil.md"
    if not perfil_path.exists():
        raise CourseError(f"falta {perfil_path} — é o perfil do aluno, e vale para todos os cursos")

    weaknesses = _weaknesses(_toml(aluno / "fraquezas.toml").get("fraqueza", []))
    weaknesses.update(_weaknesses(curso.get("fraqueza", [])))

    nodes: dict[str, Node] = {}
    if "base" in curso:
        for raw in _toml(raiz / "base" / f"{curso['base']}.toml").get("no", []):
            nodes[raw["id"]] = _node(raw)

    for node_id, over in (curso.get("no") or {}).items():
        if node_id not in nodes:
            raise CourseError(
                f"curso.toml afina o nó '{node_id}', que o grafo base não tem — "
                f"corrige o id, ou declara o nó inteiro com [[no]]"
            )
        nodes[node_id] = _overlay(nodes[node_id], over, node_id)

    for raw in curso.get("no_proprio", []):     # nodes only this course has
        nodes[raw["id"]] = _node(raw)

    _check_graph(nodes, weaknesses)

    return Course(
        nome=curso["nome"],
        perfil=perfil_path.read_text(encoding="utf-8").strip(),
        build=curso["build"],
        run=curso["run"],
        regex_erro=curso["regex_erro"],
        nodes=nodes,
        weaknesses=weaknesses,
        linguagem=curso.get("linguagem", ""),
        extensao=curso.get("extensao", ""),
        estilo_ficheiro=curso.get("estilo_ficheiro", "snake"),
        teto_briefing_bytes=curso.get("teto_briefing_bytes", 2048),
        teto_bilhete_bytes=curso.get("teto_bilhete_bytes", 400),
        teto_contexto_kb=curso.get("teto_contexto_kb", 15.0),
        decaimento_dias=curso.get("decaimento_dias", 21),
        verificacao=_verificacao(curso.get("verificacao")),
    )


def _check_graph(nodes: dict[str, Node], weaknesses: dict[str, Weakness]) -> None:
    """A broken graph must fail at load, not halfway through a study session."""
    if not nodes:
        raise CourseError("o curso não tem nós — põe base = \"fundamentos\" em curso.toml")

    for node in nodes.values():
        for dep in node.depende_de:
            if dep not in nodes:
                raise CourseError(
                    f"o nó '{node.id}' depende de '{dep}', que não existe — "
                    f"corrige depende_de ou acrescenta o nó"
                )
        for fraqueza in node.treina:
            if fraqueza not in weaknesses:
                raise CourseError(
                    f"o nó '{node.id}' treina a fraqueza '{fraqueza}', que ninguém declara — "
                    f"acrescenta um [[fraqueza]] em aluno/fraquezas.toml ou em curso.toml"
                )
        for tipo in node.tipos:
            if tipo not in TIPOS_EXERCICIO:
                raise CourseError(
                    f"o nó '{node.id}' pede o tipo de exercício '{tipo}' — "
                    f"usa um de {', '.join(TIPOS_EXERCICIO)}"
                )

    visiting: set[str] = set()
    done: set[str] = set()

    def walk(node_id: str, trail: list[str]) -> None:
        if node_id in done:
            return
        if node_id in visiting:
            raise CourseError(
                f"ciclo de pré-requisitos: {' -> '.join(trail + [node_id])} — corta uma das dependências"
            )
        visiting.add(node_id)
        for dep in nodes[node_id].depende_de:
            walk(dep, trail + [node_id])
        visiting.discard(node_id)
        done.add(node_id)

    for node_id in nodes:
        walk(node_id, [])
