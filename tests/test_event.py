from __future__ import annotations

import unittest

from gradus.event import EventError, Judgement, Passage

FRAQUEZAS = {"limites-ciclos", "buffer-scanner"}


def passagem(**kw) -> Passage:
    base = dict(id="p01", dia="2026-09-17", no="f1-arrays", exercicio="A.java", resultado="passou")
    base.update(kw)
    return Passage(**base)


class TestEvent(unittest.TestCase):
    def test_corte_sem_motivo_e_rejeitado(self):
        with self.assertRaises(EventError):
            passagem(resultado="cortado").validate(FRAQUEZAS)

    def test_fraqueza_inventada_e_rejeitada(self):
        p = passagem(juizos=[Judgement(fraqueza="preguica")])
        with self.assertRaises(EventError):
            p.validate(FRAQUEZAS)

    def test_contagens_incoerentes_sao_rejeitadas(self):
        with self.assertRaises(EventError):
            passagem(msgs_antes_do_1o_codigo=9, msgs_total=4).validate(FRAQUEZAS)

    def test_passagem_valida_passa(self):
        passagem(
            msgs_antes_do_1o_codigo=4, msgs_total=12,
            juizos=[Judgement(fraqueza="limites-ciclos", tipo_duvida="conceito")],
        ).validate(FRAQUEZAS)
