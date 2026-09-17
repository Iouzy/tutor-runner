"""Real python3 runs of a throwaway course — no model anywhere near the answers."""
from __future__ import annotations

import unittest
from datetime import date

from gradus import simulator
from gradus.model import Course, Mastery, Node
from gradus.state import State

CURSO = Course(
    nome="t", perfil="p", build="python3 -m py_compile {ficheiro}", run="python3 {ficheiro}",
    regex_erro=r"(?P<msg>\w+Error: .+)$",
    nodes={"a": Node(id="a", nome="A", objetivo="o")}, weaknesses={}, extensao=".py",
)

CODIGO = """total = 0
for i in range(1, 5):
    if i < 3:
        total = total + i
print(total)
"""


class TestGerar(unittest.TestCase):
    def test_as_perguntas_saem_do_ficheiro_dele_e_a_resposta_sai_da_maquina(self):
        previsoes = simulator.gerar(CURSO, "meu.py", CODIGO, quantas=3, semente=7)
        self.assertGreaterEqual(len(previsoes), 2)
        for p in previsoes:
            self.assertNotEqual(p.codigo, CODIGO)
            self.assertTrue(p.saida_certa.strip())
            self.assertIn("meu.py", p.pergunta)

    def test_cada_previsao_tem_uma_saida_diferente_da_original(self):
        previsoes = simulator.gerar(CURSO, "meu.py", CODIGO, quantas=3, semente=7)
        saidas = [p.saida_certa for p in previsoes]
        self.assertNotIn("3", [s for s in saidas if s == "3"])   # 3 é a saída original
        self.assertEqual(len(saidas), len(set(saidas)))

    def test_codigo_que_nem_corre_nao_gera_nada(self):
        self.assertEqual(simulator.gerar(CURSO, "mau.py", "def f(\n", semente=1), [])

    def test_a_resposta_compara_se_sem_ligar_a_espacos(self):
        p = simulator.Previsao(pergunta="?", codigo="", saida_certa="6", mudanca="x")
        self.assertTrue(simulator.acertou(p, " 6 \n"))
        self.assertFalse(simulator.acertou(p, "7"))


class TestStreak(unittest.TestCase):
    def setUp(self):
        self.st = State()
        self.st.node("a").dominio = Mastery.ESCRITO_SOZINHO

    def _dez(self, dia: date) -> str | None:
        promo = None
        for _ in range(10):
            promo = simulator.registar(self.st, "a", True, dia)
        return promo

    def test_dez_no_mesmo_dia_nao_chegam(self):
        self.assertIsNone(self._dez(date(2026, 9, 17)))
        self.assertEqual(self.st.node("a").dominio, Mastery.ESCRITO_SOZINHO)

    def test_dez_que_atravessam_uma_noite_promovem(self):
        for _ in range(4):
            simulator.registar(self.st, "a", True, date(2026, 9, 17))
        promo = None
        for _ in range(6):
            promo = simulator.registar(self.st, "a", True, date(2026, 9, 18))
        self.assertIn("automático", promo)
        self.assertEqual(self.st.node("a").dominio, Mastery.AUTOMATICO)

    def test_uma_errada_põe_a_conta_a_zero(self):
        for _ in range(9):
            simulator.registar(self.st, "a", True, date(2026, 9, 17))
        simulator.registar(self.st, "a", False, date(2026, 9, 17))
        self.assertEqual(self.st.node("a").previsoes_seguidas, 0)
        self.assertEqual(simulator.em_falta(self.st, "a"), 10)

    def test_prever_nao_substitui_ter_escrito(self):
        self.st.node("a").dominio = Mastery.ESCRITO_COM_AJUDA
        for _ in range(4):
            simulator.registar(self.st, "a", True, date(2026, 9, 17))
        for _ in range(6):
            promo = simulator.registar(self.st, "a", True, date(2026, 9, 18))
        self.assertIsNone(promo)
        self.assertEqual(self.st.node("a").dominio, Mastery.ESCRITO_COM_AJUDA)
