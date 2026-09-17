from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path

from gradus import course as course_mod, state as state_mod
from gradus.model import Mastery
from gradus.scheduler import next_node

CURSO = Path(__file__).resolve().parent.parent / "cursos" / "java-backend"


class TestScheduler(unittest.TestCase):
    def setUp(self):
        self.curso = course_mod.load(CURSO)
        self.st = state_mod.State()

    def test_nao_escolhe_no_com_pre_requisitos_em_falta(self):
        escolha = next_node(self.curso, self.st)
        self.assertEqual(escolha.node_id, "f1-tipos")

    def test_exercicio_aberto_ganha_a_tudo(self):
        self.st.no_aberto = "f1-classes"
        self.assertEqual(next_node(self.curso, self.st).node_id, "f1-classes")

    def test_decaimento_traz_de_volta_o_que_estava_automatico(self):
        for n in ("f1-tipos", "f1-if"):
            self.st.node(n).dominio = Mastery.ESCRITO_SOZINHO
            self.st.node(n).visto_em = "2026-09-01"
        self.st.node("f1-tipos").dominio = Mastery.AUTOMATICO
        escolha = next_node(self.curso, self.st, hoje=date(2026, 10, 15))
        self.assertTrue(escolha.revisao)
        self.assertEqual(escolha.node_id, "f1-tipos")

    def test_prefere_o_no_que_treina_fraquezas_ativas(self):
        for n in ("f1-tipos", "f1-if", "f1-ciclos", "f1-metodos"):
            self.st.node(n).dominio = Mastery.ESCRITO_SOZINHO
        self.st.weakness("encapsulamento-furado").ocorrencias = 3
        self.st.weakness("encapsulamento-furado").ultimas = ["2026-09-16"]
        self.assertEqual(next_node(self.curso, self.st).node_id, "f1-classes")
