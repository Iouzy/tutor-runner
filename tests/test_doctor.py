"""The doctor's own tests run the real build of a throwaway course — python3 only,
no credentials, no network, no `claude`."""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest import mock

from gradus import doctor
from gradus.model import Course, Node, Verification

PARTIDO = "def soma(a, b)\n    return a + b\n"


def curso(**kw) -> Course:
    base = dict(
        nome="t", perfil="p", build="python3 -m py_compile {ficheiro}", run="python3 {ficheiro}",
        regex_erro=r"(?P<msg>\w+(?:Error|Exception): .+)$",
        nodes={"a": Node(id="a", nome="A", objetivo="o")}, weaknesses={}, extensao=".py",
        verificacao=Verification(ficheiro="partido.py", codigo=PARTIDO, espera="SyntaxError"),
    )
    base.update(kw)
    return Course(**base)


class TestFicheiroPartido(unittest.TestCase):
    def test_o_regex_apanha_mesmo_o_erro(self):
        c = doctor._ficheiro_partido(curso())
        self.assertTrue(c.ok, c.detalhe)
        self.assertIn("SyntaxError", c.detalhe)

    def test_regex_que_nunca_apanha_e_apanhado_aqui(self):
        c = doctor._ficheiro_partido(curso(regex_erro="^(?P<msg>NUNCA ACONTECE)$"))
        self.assertFalse(c.ok)
        self.assertIn("linha crua", c.detalhe)

    def test_um_ficheiro_que_afinal_compila_nao_prova_nada(self):
        v = Verification(ficheiro="bom.py", codigo="x = 1\n")
        c = doctor._ficheiro_partido(curso(verificacao=v))
        self.assertFalse(c.ok)
        self.assertIn("compilou", c.detalhe)

    def test_apanhar_a_linha_errada_e_falha(self):
        v = Verification(ficheiro="partido.py", codigo=PARTIDO, espera="NameError")
        c = doctor._ficheiro_partido(curso(verificacao=v))
        self.assertFalse(c.ok)
        self.assertIn("esperava", c.detalhe)

    def test_sem_verificacao_o_doctor_diz_que_nao_pode_garantir_nada(self):
        c = doctor._ficheiro_partido(curso(verificacao=None))
        self.assertFalse(c.ok)
        self.assertIn("[verificacao]", c.conserto)


class TestMaquina(unittest.TestCase):
    def test_binario_que_nao_existe(self):
        c = doctor._binario("build", "compilador-que-nao-existe {ficheiro}", ".py")
        self.assertFalse(c.ok)
        self.assertIn("PATH", c.detalhe)

    def test_a_chave_da_api_posta_e_um_erro(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-seja-o-que-for"}):
            c = doctor._api_key()
        self.assertFalse(c.ok)
        self.assertIn("subscrição", c.conserto)

    def test_sem_chave_esta_bem(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertTrue(doctor._api_key().ok)

    def test_escrita_numa_pasta_que_nao_se_pode_criar(self):
        c = doctor._escrita(Path("/proc/nao-da-para-escrever-aqui"))
        self.assertFalse(c.ok)
