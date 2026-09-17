from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path

from gradus import course as course_mod, state as state_mod
from gradus.model import Course, Mastery, Node
from gradus.scheduler import next_node, tipo_para

CURSO = Path(__file__).resolve().parent.parent / "cursos" / "java-backend"


class TestScheduler(unittest.TestCase):
    def setUp(self):
        self.curso = course_mod.load(CURSO)
        self.st = state_mod.State()

    def test_nao_escolhe_no_com_pre_requisitos_em_falta(self):
        escolha = next_node(self.curso, self.st)
        self.assertEqual(escolha.node_id, "base-tipos")

    def test_exercicio_aberto_ganha_a_tudo(self):
        self.st.no_aberto = "base-objetos"
        self.assertEqual(next_node(self.curso, self.st).node_id, "base-objetos")

    def test_decaimento_traz_de_volta_o_que_estava_automatico(self):
        for n in ("base-tipos", "base-condicionais"):
            self.st.node(n).dominio = Mastery.ESCRITO_SOZINHO
            self.st.node(n).visto_em = "2026-09-01"
        self.st.node("base-tipos").dominio = Mastery.AUTOMATICO
        escolha = next_node(self.curso, self.st, hoje=date(2026, 10, 15))
        self.assertTrue(escolha.revisao)
        self.assertEqual(escolha.node_id, "base-tipos")

    def test_prefere_o_no_que_treina_fraquezas_ativas(self):
        for n in ("base-tipos", "base-condicionais", "base-ciclos", "base-funcoes"):
            self.st.node(n).dominio = Mastery.ESCRITO_SOZINHO
        self.st.weakness("encapsulamento-furado").ocorrencias = 3
        self.st.weakness("encapsulamento-furado").ultimas = ["2026-09-16"]
        self.assertEqual(next_node(self.curso, self.st).node_id, "base-objetos")


class TestTipoDeExercicio(unittest.TestCase):
    """Order inside a node, and never two constructions of it back to back."""

    def setUp(self):
        self.curso = course_mod.load(CURSO)
        self.st = state_mod.State()
        for n in ("base-tipos", "base-condicionais", "base-ciclos", "base-funcoes"):
            self.st.node(n).dominio = Mastery.ESCRITO_SOZINHO
        self.st.weakness("limites-ciclos").ocorrencias = 2
        self.st.weakness("limites-ciclos").ultimas = ["2026-09-16"]

    def test_um_no_novo_comeca_pela_previsao(self):
        escolha = next_node(self.curso, self.st, hoje=date(2026, 9, 17))
        self.assertEqual(escolha.node_id, "base-listas")
        self.assertEqual(escolha.tipo, "previsao")

    def test_a_ordem_e_previsao_erro_construcao(self):
        ns = self.st.node("base-listas")
        vistos = []
        for _ in range(3):
            escolha = next_node(self.curso, self.st, hoje=date(2026, 9, 17))
            vistos.append(escolha.tipo)
            ns.tipos_feitos[escolha.tipo] = "2026-09-17"
        self.assertEqual(vistos, ["previsao", "erro-plantado", "construcao"])

    def test_reescrita_espera_por_outro_dia(self):
        ns = self.st.node("base-listas")
        ns.tipos_feitos = {"previsao": "2026-09-17", "erro-plantado": "2026-09-17", "construcao": "2026-09-17"}
        node = self.curso.node("base-listas")
        self.assertNotEqual(tipo_para(node, ns, date(2026, 9, 17)), "reescrita")
        self.assertEqual(tipo_para(node, ns, date(2026, 9, 18)), "reescrita")


def _curso_de_dois_nos() -> Course:
    """Two nodes that only know how to be built: the case where massed practice
    is still possible after the types have been cycled."""
    return Course(
        nome="t", perfil="p", build="b {ficheiro}", run="r {classe}", regex_erro="^(?P<msg>.+)$",
        nodes={
            "a": Node(id="a", nome="A", objetivo="o", tipos=("construcao",)),
            "b": Node(id="b", nome="B", objetivo="o", tipos=("construcao",)),
        },
        weaknesses={},
    )


class TestIntercalar(unittest.TestCase):
    def setUp(self):
        self.curso = _curso_de_dois_nos()
        self.st = state_mod.State()
        self.st.node("a").dominio = Mastery.VISTO
        self.st.node("a").tipos_feitos = {"construcao": "2026-09-17"}
        self.st.ultimo_no, self.st.ultimo_tipo = "a", "construcao"

    def test_nao_faz_duas_construcoes_seguidas_do_mesmo_no(self):
        escolha = next_node(self.curso, self.st, hoje=date(2026, 9, 17))
        self.assertEqual(escolha.node_id, "b")

    def test_sem_alternativa_repete_mas_di_lo(self):
        del self.curso.nodes["b"]
        escolha = next_node(self.curso, self.st, hoje=date(2026, 9, 17))
        self.assertEqual(escolha.node_id, "a")
        self.assertIn("intercalar", escolha.motivo)
