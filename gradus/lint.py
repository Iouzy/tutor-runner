"""gradus lint — says what will break before a study session finds out.

`course.load` already refuses a course that cannot be loaded at all. This goes
further and asks the question a new course really needs answered: on the worst
day this course can have, does it still work? Nothing here runs a command or
touches the machine — that is `gradus doctor`'s job.
"""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import Path

from . import briefing as briefing_mod
from .model import Course, CourseError, Node
from .state import State

ERRO, AVISO = "erro", "aviso"


@dataclass(frozen=True)
class Finding:
    nivel: str
    onde: str
    problema: str
    conserto: str


def _comandos(course: Course) -> list[Finding]:
    achados = []
    if "{ficheiro}" not in course.build:
        achados.append(Finding(
            ERRO, "curso.toml", "build não usa {ficheiro}",
            "escreve build = \"javac -d out {ficheiro}\" — sem o campo compila-se sempre o mesmo nada",
        ))
    if "{classe}" not in course.run and "{ficheiro}" not in course.run:
        achados.append(Finding(
            ERRO, "curso.toml", "run não usa {classe} nem {ficheiro}",
            "põe um dos dois em run = \"...\", senão o programa do aluno nunca é o que corre",
        ))
    for campo, valor in (("build", course.build), ("run", course.run)):
        try:
            shlex.split(valor.format(ficheiro="x" + course.extensao, classe="x"))
        except ValueError as exc:
            achados.append(Finding(
                ERRO, "curso.toml", f"{campo} não é um comando que se consiga partir ({exc})",
                "fecha as aspas; o comando é partido com shlex, não corrido por uma shell",
            ))
        except (KeyError, IndexError):
            achados.append(Finding(
                ERRO, "curso.toml", f"{campo} tem um campo que não é {{ficheiro}} nem {{classe}}",
                "só existem esses dois — corrige o nome do campo",
            ))
    return achados


def _regex(course: Course) -> list[Finding]:
    grupos = set(re.compile(course.regex_erro).groupindex)
    achados = []
    if "msg" not in grupos:
        achados.append(Finding(
            ERRO, "curso.toml", "regex_erro não apanha o grupo (?P<msg>...)",
            "sem ele a telemetria guarda a primeira linha do stderr em vez da mensagem do compilador",
        ))
    for opcional in ("ficheiro", "linha"):
        if opcional not in grupos:
            achados.append(Finding(
                AVISO, "curso.toml", f"regex_erro não apanha (?P<{opcional}>...)",
                "dá jeito para apontar o erro ao sítio; sem ele perde-se essa coluna",
            ))
    return achados


def _extensao(course: Course) -> list[Finding]:
    if not course.extensao:
        return [Finding(
            AVISO, "curso.toml", "extensao em falta",
            "põe extensao = \".py\" — o doctor precisa dela para escrever um ficheiro partido de propósito",
        )]
    if not course.extensao.startswith("."):
        return [Finding(
            ERRO, "curso.toml", f"extensao '{course.extensao}' não começa por ponto",
            f"escreve extensao = \".{course.extensao}\"",
        )]
    return []


def _ancoras(course: Course, node: Node) -> list[Finding]:
    achados = []
    vistos: set[str] = set()
    for a in node.ancoras:
        onde = f"{node.id}/{a.ficheiro or a.tipo}"
        if node.tipos and a.tipo not in node.tipos:
            achados.append(Finding(
                AVISO, onde, f"âncora de tipo '{a.tipo}', que o nó não pede",
                f"acrescenta '{a.tipo}' aos tipos do nó, senão o escalonador nunca a escolhe",
            ))
        if a.tipo in vistos:
            achados.append(Finding(
                AVISO, onde, f"segunda âncora de tipo '{a.tipo}' no mesmo nó",
                "o briefing só leva a primeira; parte o nó em dois ou muda o tipo desta",
            ))
        vistos.add(a.tipo)
        if course.extensao and a.ficheiro and not a.ficheiro.endswith(course.extensao):
            achados.append(Finding(
                ERRO, onde, f"o ficheiro da âncora não acaba em '{course.extensao}'",
                "é de outra linguagem — o build do curso não lhe pega",
            ))
        for c in a.controlo:
            if "entrada" not in c or "saida" not in c:
                achados.append(Finding(
                    ERRO, onde, "valor de controlo sem 'entrada' ou sem 'saida'",
                    "escreve { entrada = \"...\", saida = \"...\" } — quem verifica é o valor, não um modelo",
                ))
                break
    return achados


def _tipos(node: Node) -> list[Finding]:
    achados = []
    if not node.tipos:
        achados.append(Finding(
            AVISO, node.id, "o nó não declara tipos de exercício",
            "cai sempre em construção; põe tipos = [\"previsao\", \"erro-plantado\", \"construcao\"]",
        ))
    elif "reescrita" in node.tipos and "construcao" not in node.tipos:
        achados.append(Finding(
            ERRO, node.id, "pede reescrita sem pedir construção",
            "a reescrita só abre no dia seguinte a uma construção — sem ela nunca sai",
        ))
    return achados


def _fraquezas(course: Course) -> list[Finding]:
    treinadas = {f for node in course.nodes.values() for f in node.treina}
    return [
        Finding(
            AVISO, "fraquezas", f"'{w}' não é treinada por nenhum nó",
            "acrescenta-a ao treina de um nó, senão o escalonador nunca a persegue",
        )
        for w in sorted(set(course.weaknesses) - treinadas)
    ]


def _estado_cheio(course: Course) -> State:
    """The worst day: every weakness with recent evidence, so the slot is full."""
    st = State()
    for w in course.weaknesses:
        st.weakness(w).ocorrencias = 1
        st.weakness(w).ultimas = ["2026-01-01"]
    return st


def _encher(bf: briefing_mod.Briefing, course: Course) -> int:
    """The worst day this course can have: every optional slot at its ceiling."""
    for slot in bf.slots:
        if slot.nome == "erros":
            slot.texto = "e" * briefing_mod.TETO_ERROS
    teto_bilhete = course.teto_bilhete_bytes + briefing_mod.MARGEM_BILHETE
    bf.slots.append(briefing_mod.Slot("bilhete", "b" * teto_bilhete, teto=teto_bilhete))
    return bf.bytes


def _orcamento(course: Course) -> list[Finding]:
    """It fits today; the question is whether it still fits on the day he needs it."""
    st = _estado_cheio(course)
    achados: list[Finding] = []
    pior: tuple[int, str, list[str]] = (0, "", [])
    for node in course.nodes.values():
        for tipo in node.tipos or ("construcao",):
            try:
                bf = briefing_mod.build(course, st, node, telemetria=Path("/sem/telemetria"), tipo=tipo)
            except CourseError as exc:
                partes = str(exc).split(" — ")
                achados.append(Finding(ERRO, f"{node.id}/{tipo}", partes[0], partes[-1]))
                continue
            bruto = _encher(bf, course)
            bf.cortar()
            onde = f"{node.id}/{tipo}"
            if bf.bytes > course.teto_briefing_bytes:
                achados.append(Finding(
                    ERRO, onde,
                    f"nem largando tudo o briefing cabe: {bf.bytes} B contra {course.teto_briefing_bytes} B",
                    "encurta o nó — objetivo, armadilhas ou enunciado da âncora",
                ))
            elif (len(bf.descartados), bruto) > (len(pior[2]), pior[0]):
                pior = (bruto, onde, list(bf.descartados))
    if pior[2]:
        achados.append(Finding(
            AVISO, pior[1],
            f"no pior dia o briefing pede {pior[0]} B (teto {course.teto_briefing_bytes}) "
            f"e larga: {', '.join(pior[2])}",
            f"é de propósito e vai dito no relatório; se {pior[2][0]} faz falta nesse dia, "
            f"encurta-o ou sobe teto_briefing_bytes para {pior[0]}",
        ))
    return achados


def check(course: Course) -> list[Finding]:
    achados = _comandos(course) + _regex(course) + _extensao(course) + _fraquezas(course)
    for node in sorted(course.nodes.values(), key=lambda n: n.id):
        achados += _tipos(node) + _ancoras(course, node)
    achados += _orcamento(course)
    return sorted(achados, key=lambda f: (f.nivel != ERRO, f.onde))
