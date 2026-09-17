from __future__ import annotations

import unittest
from pathlib import Path

from gradus import briefing as briefing_mod, course as course_mod, state as state_mod
from gradus.model import CourseError, Handoff, Mastery

CURSO = Path(__file__).resolve().parent.parent / "cursos" / "java-backend"


class TestBriefing(unittest.TestCase):
    def setUp(self):
        self.curso = course_mod.load(CURSO)
        self.st = state_mod.State()

    def test_cabe_no_orcamento(self):
        bf = briefing_mod.build(
            self.curso, self.st, self.curso.node("base-listas"), telemetria=Path("/nao/existe")
        )
        self.assertLessEqual(bf.bytes, self.curso.teto_briefing_bytes)

    def test_bilhete_acima_do_teto_falha_alto(self):
        gordo = Handoff(onde_ficou="x" * 2000, ultimo_erro="", ja_explicado=[], nao_repetir="")
        with self.assertRaises(CourseError):
            briefing_mod.build(
                self.curso, self.st, self.curso.node("base-listas"),
                telemetria=Path("/nao/existe"), handoff=gordo,
            )

    def test_briefing_nao_traz_historico(self):
        self.st.node("base-ciclos").dominio = Mastery.AUTOMATICO
        bf = briefing_mod.build(
            self.curso, self.st, self.curso.node("base-listas"), telemetria=Path("/nao/existe")
        )
        self.assertNotIn("HISTORICO", bf.texto)
        self.assertNotIn("passagem", bf.texto.lower())
