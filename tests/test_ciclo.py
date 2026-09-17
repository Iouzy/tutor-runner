"""The whole day, in both courses, with no model and no network."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gradus import briefing as briefing_mod, course as course_mod, report, state as state_mod
from gradus.fake import DIA_TIPO, ScriptedSession
from gradus.loop import Runner

RAIZ = Path(__file__).resolve().parent.parent
CURSOS = ("java-backend", "python")


class TestCicloEmQualquerCurso(unittest.TestCase):
    def test_um_dia_inteiro_corre_nos_dois_cursos(self):
        for nome in CURSOS:
            with self.subTest(curso=nome), tempfile.TemporaryDirectory() as d:
                curso_dir = RAIZ / "cursos" / nome
                curso = course_mod.load(curso_dir)
                work = Path(d)
                runner = Runner(curso, curso_dir, work)
                sessao = ScriptedSession(DIA_TIPO, fraquezas=set(curso.weaknesses))
                handoff = None
                for _ in DIA_TIPO:
                    rel = runner.passage(sessao, "2026-09-17", handoff)
                    self.assertIsNotNone(rel, nome)
                    handoff = None if rel.passage.resultado == "passou" else rel.handoff
                runner.regenerate()
                self.assertTrue((work / "ESTADO.md").exists())
                self.assertTrue((work / "HISTORICO.md").exists())


class TestFraquezaDeOutraLinguagem(unittest.TestCase):
    """The profile crosses languages; a Java-only weakness must not cross with it."""

    def setUp(self):
        self.curso = course_mod.load(RAIZ / "cursos" / "python")
        self.st = state_mod.State()
        self.st.weakness("buffer-scanner").ocorrencias = 2      # só existe em Java
        self.st.weakness("buffer-scanner").ultimas = ["2026-09-16"]

    def test_nao_rebenta_nem_entra_no_briefing(self):
        bf = briefing_mod.build(
            self.curso, self.st, self.curso.node("base-listas"), telemetria=Path("/nao/existe")
        )
        self.assertNotIn("Scanner", bf.texto)

    def test_nao_rebenta_no_estado_md(self):
        md = report.estado_md(self.curso, self.st, proximo=None)
        self.assertNotIn("Scanner", md)
