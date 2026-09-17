from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

from gradus.adapter import Claude
from gradus.conversation import Conversa
from gradus.model import Course, Node, Weakness
from gradus.workspace import Attempt

STUB = [sys.executable, str(Path(__file__).resolve().parent / "stub_claude.py")]

CURSO = Course(
    nome="t", perfil="p", build="b {ficheiro}", run="r {classe}", regex_erro="^(?P<msg>.+)$",
    nodes={"base-listas": Node(id="base-listas", nome="Listas", objetivo="o")},
    weaknesses={"limites-ciclos": Weakness(id="limites-ciclos", nome="limites", descricao="d")},
    extensao=".java", teto_bilhete_bytes=400, teto_contexto_kb=15.0,
)


def conversa() -> Conversa:
    return Conversa(
        course=CURSO, claude=Claude(comando=list(STUB)), node_id="base-listas",
        tipo="construcao", briefing="## EXERCÍCIO: Listas", exercicio="MediaArray.java",
    )


class TestConversa(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {}, clear=False)
        self.env.start()
        os.environ.pop("ANTHROPIC_API_KEY", None)
        self.addCleanup(self.env.stop)

    def test_um_exercicio_do_principio_ao_fim(self):
        c = conversa()
        c.abrir()
        c.dizer("acho que dá 14")
        c.tentativa(Attempt("javac MediaArray.java", False, False, "", "cannot find symbol: soma"), "int x;")
        c.tentativa(Attempt("java MediaArray", True, True, "14\n", None), "int x = 0;")
        raw = c.fechar(passou=True)

        self.assertTrue(raw.passou)
        self.assertEqual(len(raw.compilacoes), 2)
        self.assertTrue(raw.ja_registadas)          # o workspace já as escreveu
        self.assertGreater(raw.kb_contexto, 0)
        self.assertGreater(raw.tokens, 0)
        self.assertGreater(raw.custo_usd, 0)

    def test_o_codigo_dele_entra_no_transcript_para_a_contagem(self):
        from gradus.telemetry import count_messages

        c = conversa()
        c.abrir()
        c.dizer("primeiro explica-me outra vez")
        c.dizer("e o for?")
        c.tentativa(Attempt("javac x", True, True, "", None), "int x = 0;")
        antes, total = count_messages(c.transcript)
        self.assertEqual(antes, 6)                  # briefing + duas voltas inteiras antes de escrever
        self.assertLess(antes, total)

    def test_uma_fraqueza_inventada_pelo_modelo_e_deitada_fora(self):
        c = conversa()
        c.abrir()
        juizos, duvidas = c.pedir_juizos()
        self.assertEqual(juizos[0].fraqueza, "limites-ciclos")
        self.assertIsNone(juizos[1].fraqueza)       # 'inventada-por-mim' não existe
        self.assertIsNone(juizos[1].tipo_duvida)    # 'preguiça' também não
        self.assertEqual(duvidas, ["length é campo ou método?"])

    def test_o_bilhete_e_encolhido_ate_caber(self):
        c = conversa()
        c.abrir()
        bilhete = c.pedir_bilhete()
        self.assertIsNotNone(bilhete)
        self.assertLessEqual(len(bilhete.to_json().encode("utf-8")), CURSO.teto_bilhete_bytes)
        self.assertIn("acumulador", bilhete.onde_ficou)

    def test_o_corte_dispara_pelo_teto_de_contexto(self):
        c = conversa()
        c.abrir()
        self.assertFalse(c.deve_cortar())
        c.transcript.append({"papel": "gradus", "texto": "x" * 16000})
        self.assertTrue(c.deve_cortar())
