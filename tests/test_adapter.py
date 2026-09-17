from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

from gradus.adapter import Claude, ClaudeError, _ler

STUB = [sys.executable, str(Path(__file__).resolve().parent / "stub_claude.py")]


def claude() -> Claude:
    return Claude(comando=list(STUB))


class TestAdapter(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {}, clear=False)
        self.env.start()
        os.environ.pop("ANTHROPIC_API_KEY", None)
        self.addCleanup(self.env.stop)

    def test_arranca_e_traz_o_id_da_sessao(self):
        r = claude().arrancar("sistema", "olá")
        self.assertTrue(r.texto)
        self.assertEqual(r.sessao, "sessao-1")
        self.assertEqual(r.tokens_entrada + r.tokens_saida, 160)

    def test_continua_a_mesma_sessao(self):
        self.assertEqual(claude().continuar("sessao-9", "e agora?").sessao, "sessao-9")

    def test_sem_id_de_sessao_recusa(self):
        with self.assertRaises(ClaudeError):
            claude().continuar("", "e agora?")

    def test_a_chave_da_api_posta_trava_tudo(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-xyz"}):
            with self.assertRaises(ClaudeError) as ctx:
                claude().arrancar("s", "m")
        self.assertIn("subscrição", str(ctx.exception))

    def test_binario_que_nao_existe(self):
        with self.assertRaises(ClaudeError):
            Claude(comando=["claude-que-nao-existe"]).arrancar("s", "m")

    def test_saida_que_nao_e_json(self):
        with self.assertRaises(ClaudeError):
            _ler("isto não é json")

    def test_erro_declarado_pelo_cli(self):
        with self.assertRaises(ClaudeError):
            _ler('{"is_error": true, "result": "rate limited"}')

    def test_o_modelo_corre_sempre_sem_ferramentas(self):
        """O stub recusa se faltar --restricted: quem compila é o programa."""
        c = claude()
        c.extra = ()
        self.assertTrue(c.arrancar("s", "m").texto)
