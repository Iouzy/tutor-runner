from __future__ import annotations

import tempfile
from contextlib import contextmanager
import unittest
from pathlib import Path

from gradus import course as course_mod
from gradus.model import CourseError

RAIZ = Path(__file__).resolve().parent.parent
CURSO = RAIZ / "cursos" / "java-backend"


class TestCourse(unittest.TestCase):
    def test_o_curso_de_referencia_carrega(self):
        c = course_mod.load(CURSO)
        self.assertIn("base-listas", c.nodes)
        self.assertIn("buffer-scanner", c.weaknesses)

    def test_python_carrega_o_mesmo_grafo(self):
        java = course_mod.load(CURSO)
        py = course_mod.load(RAIZ / "cursos" / "python")
        # The whole claim of the project: the fundamentals graph is not Java's.
        self.assertEqual(set(java.nodes), set(py.nodes))
        self.assertNotEqual(java.build, py.build)
        self.assertIn("range(a, b) não inclui b", py.node("base-ciclos").armadilhas)
        self.assertIn("o intervalo inclui os extremos?", java.node("base-ciclos").armadilhas)

    def test_fraqueza_transversal_vale_nos_dois_cursos(self):
        for nome in ("java-backend", "python"):
            self.assertIn("limites-ciclos", course_mod.load(RAIZ / "cursos" / nome).weaknesses)

    def test_ancora_sem_valores_de_controlo_e_recusada(self):
        with self._curso_temporario(
            '[no.base-ciclos]\n[[no.base-ciclos.ancora]]\n'
            'tipo = "construcao"\nenunciado = "soma os pares"\n'
        ) as dest:
            with self.assertRaises(CourseError) as ctx:
                course_mod.load(dest, raiz=RAIZ)
            self.assertIn("valores de controlo", str(ctx.exception))

    def test_afinar_um_no_que_nao_existe_falha(self):
        with self._curso_temporario('[no.base-fantasma]\narmadilhas = ["x"]\n') as dest:
            with self.assertRaises(CourseError) as ctx:
                course_mod.load(dest, raiz=RAIZ)
            self.assertIn("o grafo base não tem", str(ctx.exception))

    @contextmanager
    def _curso_temporario(self, extra: str):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d)
            base = (CURSO / "curso.toml").read_text(encoding="utf-8").split("[no.base-tipos]")[0]
            (dest / "curso.toml").write_text(base + extra, encoding="utf-8")
            yield dest
