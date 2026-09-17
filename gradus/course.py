"""Loads a course: its graph, its build commands, its weakness vocabulary."""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

from .model import Course, CourseError, Node, Weakness


def load(course_dir: Path) -> Course:
    curso_path = course_dir / "curso.toml"
    grafo_path = course_dir / "grafo.toml"
    perfil_path = course_dir / "perfil.md"

    for p in (curso_path, grafo_path, perfil_path):
        if not p.exists():
            raise CourseError(f"falta {p.name} em {course_dir} — cria-o a partir de cursos/_exemplo/")

    curso = tomllib.loads(curso_path.read_text(encoding="utf-8"))
    grafo = tomllib.loads(grafo_path.read_text(encoding="utf-8"))

    for chave in ("nome", "build", "run", "regex_erro"):
        if chave not in curso:
            raise CourseError(f"curso.toml não define '{chave}' — acrescenta a linha {chave} = \"...\"")

    try:
        re.compile(curso["regex_erro"])
    except re.error as exc:
        raise CourseError(f"regex_erro não compila ({exc}) — corrige a expressão em curso.toml") from None

    weaknesses = {
        w["id"]: Weakness(id=w["id"], nome=w["nome"], descricao=w.get("descricao", ""))
        for w in curso.get("fraqueza", [])
    }

    nodes: dict[str, Node] = {}
    for raw in grafo.get("no", []):
        node = Node(
            id=raw["id"],
            nome=raw["nome"],
            objetivo=raw["objetivo"],
            depende_de=tuple(raw.get("depende_de", [])),
            armadilhas=tuple(raw.get("armadilhas", [])),
            treina=tuple(raw.get("treina", [])),
        )
        if node.id in nodes:
            raise CourseError(f"o nó '{node.id}' está duas vezes em grafo.toml — dá outro id a um deles")
        nodes[node.id] = node

    _check_graph(nodes, weaknesses)

    return Course(
        nome=curso["nome"],
        perfil=perfil_path.read_text(encoding="utf-8").strip(),
        build=curso["build"],
        run=curso["run"],
        regex_erro=curso["regex_erro"],
        nodes=nodes,
        weaknesses=weaknesses,
        teto_briefing_bytes=curso.get("teto_briefing_bytes", 2048),
        teto_bilhete_bytes=curso.get("teto_bilhete_bytes", 400),
        teto_contexto_kb=curso.get("teto_contexto_kb", 15.0),
        decaimento_dias=curso.get("decaimento_dias", 21),
    )


def _check_graph(nodes: dict[str, Node], weaknesses: dict[str, Weakness]) -> None:
    """A broken graph must fail at load, not halfway through a study session."""
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
                    f"o nó '{node.id}' treina a fraqueza '{fraqueza}', que curso.toml não declara — "
                    f"acrescenta um bloco [[fraqueza]] com esse id"
                )

    # Cycles: a learner would be stuck with no eligible node and no reason why.
    visiting: set[str] = set()
    done: set[str] = set()

    def walk(node_id: str, trail: list[str]) -> None:
        if node_id in done:
            return
        if node_id in visiting:
            ciclo = " -> ".join(trail + [node_id])
            raise CourseError(f"ciclo de pré-requisitos em grafo.toml: {ciclo} — corta uma das dependências")
        visiting.add(node_id)
        for dep in nodes[node_id].depende_de:
            walk(dep, trail + [node_id])
        visiting.discard(node_id)
        done.add(node_id)

    for node_id in nodes:
        walk(node_id, [])
