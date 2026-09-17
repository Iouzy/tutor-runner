"""Uses the real python3 build of a throwaway course — no credentials, no network."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gradus.model import Course, CourseError, Node
from gradus.workspace import Workspace

CURSO = Course(
    nome="t", perfil="p", build="python3 -m py_compile {ficheiro}", run="python3 {ficheiro}",
    regex_erro=r"(?P<msg>\w+(?:Error|Exception): .+)$",
    nodes={"a": Node(id="a", nome="A", objetivo="o")}, weaknesses={}, extensao=".py",
)


class TestWorkspace(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.ws = Workspace(CURSO, self.work)

    def _linhas(self) -> list[dict]:
        f = self.work / "telemetria" / "compilacoes.jsonl"
        return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]

    def test_um_programa_que_corre(self):
        self.ws.criar("ola.py", "print('olá')\n")
        t = self.ws.tentar("a", "ola.py")
        self.assertTrue(t.ok)
        self.assertIn("olá", t.saida)
        self.assertEqual(self._linhas()[-1]["erro"], None)

    def test_erro_de_sintaxe_e_apanhado_na_compilacao(self):
        self.ws.criar("mau.py", "def soma(a, b)\n    return a + b\n")
        t = self.ws.tentar("a", "mau.py")
        self.assertFalse(t.compilou)
        self.assertIn("SyntaxError", t.erro)
        self.assertIn("SyntaxError", self._linhas()[-1]["erro"])

    def test_erro_so_a_correr_conta_na_mesma(self):
        """Em Python o sinal está quase todo no run: compila e rebenta à mesma."""
        self.ws.criar("rebenta.py", "x = int('não é número')\n")
        t = self.ws.tentar("a", "rebenta.py")
        self.assertTrue(t.compilou)
        self.assertFalse(t.correu)
        self.assertIn("ValueError", t.erro)
        self.assertIn("ValueError", self._linhas()[-1]["erro"])

    def test_cada_tentativa_deixa_uma_linha_sozinha(self):
        self.ws.criar("ola.py", "print('olá')\n")
        for _ in range(3):
            self.ws.tentar("a", "ola.py")
        self.assertEqual(len(self._linhas()), 3)

    def test_nunca_escreve_por_cima_do_trabalho_dele(self):
        self.ws.criar("meu.py", "print(1)\n")
        self.ws.criar("meu.py", "esqueleto novo")
        self.assertEqual(self.ws.caminho("meu.py").read_text(encoding="utf-8"), "print(1)\n")

    def test_recusa_sair_da_pasta_dos_exercicios(self):
        with self.assertRaises(CourseError):
            self.ws.caminho("../../etc/passwd")

    def test_recusa_ficheiro_de_outra_linguagem(self):
        with self.assertRaises(CourseError):
            self.ws.caminho("A.java")
