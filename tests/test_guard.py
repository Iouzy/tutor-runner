"""The guard that keeps the whole context economy honest."""
from __future__ import annotations

import unittest

from gradus.archive import leitura_permitida
from gradus.briefing import FONTES_PERMITIDAS


class TestArchiveGuard(unittest.TestCase):
    def test_arquivo_nunca_alimenta_um_briefing(self):
        # If this ever passes, a session can read the archive and every byte
        # saved by cold sessions is given back.
        self.assertFalse(leitura_permitida("arquivo/2026-09-17/p01.jsonl", FONTES_PERMITIDAS))
        self.assertFalse(any(p.startswith("arquivo") for p in FONTES_PERMITIDAS))

    def test_fontes_legitimas_passam(self):
        for caminho in ("perfil.md", "grafo.toml", "telemetria/compilacoes.jsonl"):
            self.assertTrue(leitura_permitida(caminho, FONTES_PERMITIDAS), caminho)
