from __future__ import annotations

import unittest

from gradus.archive import redact
from gradus.telemetry import count_messages


class TestMeasurement(unittest.TestCase):
    def test_conta_mensagens_ate_ao_primeiro_codigo(self):
        t = [
            {"papel": "gradus", "texto": "briefing"},
            {"papel": "aluno", "texto": "em que pasta fica?"},
            {"papel": "gradus", "texto": "04-reforco"},
            {"papel": "aluno", "texto": "```java\nint i;\n```"},
        ]
        self.assertEqual(count_messages(t), (3, 4))

    def test_sem_codigo_o_racio_e_tudo(self):
        t = [{"papel": "aluno", "texto": "mais uma pergunta"}] * 5
        self.assertEqual(count_messages(t), (5, 5))


class TestRedaction(unittest.TestCase):
    def test_segredos_saem_antes_de_tocar_no_disco(self):
        for segredo in ("ghp_abcdefghijklmnopqrstuvwxyz01", "sk-abcdefghijklmnopqrst", "token=abcdefghijklmnop"):
            self.assertNotIn(segredo, redact(f"correu com {segredo} dentro"))
