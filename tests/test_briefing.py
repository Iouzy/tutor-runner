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

    def test_quando_nao_cabe_larga_o_perfil_primeiro_e_di_lo(self):
        curto = course_mod.load(CURSO)
        object.__setattr__(curto, "teto_briefing_bytes", 900)
        bf = briefing_mod.build(
            curto, self.st, curto.node("base-listas"), telemetria=Path("/nao/existe")
        )
        self.assertEqual(bf.descartados, ["perfil"])
        self.assertNotIn(curto.perfil, bf.texto)
        self.assertIn("largado: perfil", bf.relatorio())
        self.assertLessEqual(bf.bytes, 900)

    def test_se_nem_o_no_cabe_rebenta(self):
        curto = course_mod.load(CURSO)
        object.__setattr__(curto, "teto_briefing_bytes", 50)
        with self.assertRaises(CourseError):
            briefing_mod.build(
                curto, self.st, curto.node("base-listas"), telemetria=Path("/nao/existe")
            )

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


class TestTipoNoBriefing(unittest.TestCase):
    def setUp(self):
        self.curso = course_mod.load(CURSO)
        self.st = state_mod.State()

    def test_a_sessao_e_instruida_para_o_tipo_pedido(self):
        bf = briefing_mod.build(
            self.curso, self.st, self.curso.node("base-listas"),
            telemetria=Path("/nao/existe"), tipo="previsao",
        )
        self.assertIn("previsão", bf.texto)
        self.assertIn("ANTES de correr", bf.texto)
        self.assertNotIn("escreve do zero", bf.texto)

    def test_a_ancora_do_tipo_vai_com_os_valores_de_controlo(self):
        bf = briefing_mod.build(
            self.curso, self.st, self.curso.node("base-listas"),
            telemetria=Path("/nao/existe"), tipo="erro-plantado",
        )
        self.assertIn("MaiorQuebrado.java", bf.texto)
        self.assertIn("-3", bf.texto)                      # the control value
        self.assertLessEqual(bf.bytes, self.curso.teto_briefing_bytes)

    def test_sem_ancora_do_tipo_nao_inventa_uma(self):
        bf = briefing_mod.build(
            self.curso, self.st, self.curso.node("base-listas"),
            telemetria=Path("/nao/existe"), tipo="previsao",
        )
        self.assertNotIn("Âncora", bf.texto)
