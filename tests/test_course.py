from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gradus import course as course_mod
from gradus.model import CourseError

CURSO = Path(__file__).resolve().parent.parent / "cursos" / "java-backend"


class TestCourse(unittest.TestCase):
    def test_o_curso_de_referencia_carrega(self):
        c = course_mod.load(CURSO)
        self.assertIn("f1-arrays", c.nodes)
        self.assertIn("buffer-scanner", c.weaknesses)

    def test_dependencia_inexistente_falha_com_o_conserto_na_mensagem(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d)
            for f in ("curso.toml", "perfil.md"):
                (dest / f).write_text((CURSO / f).read_text(encoding="utf-8"), encoding="utf-8")
            (dest / "grafo.toml").write_text(
                '[[no]]\nid = "a"\nnome = "A"\nobjetivo = "x"\ndepende_de = ["fantasma"]\n', encoding="utf-8"
            )
            with self.assertRaises(CourseError) as ctx:
                course_mod.load(dest)
            self.assertIn("corrige depende_de", str(ctx.exception))

    def test_ciclo_de_pre_requisitos_falha(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d)
            for f in ("curso.toml", "perfil.md"):
                (dest / f).write_text((CURSO / f).read_text(encoding="utf-8"), encoding="utf-8")
            (dest / "grafo.toml").write_text(
                '[[no]]\nid = "a"\nnome = "A"\nobjetivo = "x"\ndepende_de = ["b"]\n'
                '[[no]]\nid = "b"\nnome = "B"\nobjetivo = "y"\ndepende_de = ["a"]\n', encoding="utf-8"
            )
            with self.assertRaises(CourseError) as ctx:
                course_mod.load(dest)
            self.assertIn("ciclo", str(ctx.exception))
