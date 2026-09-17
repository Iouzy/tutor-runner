"""What makes it safe to write a new course: the lint has to catch it, not a session."""
from __future__ import annotations

import unittest
from pathlib import Path

from gradus import course as course_mod, lint
from gradus.model import Anchor, Course, Node

CURSO = Path(__file__).resolve().parent.parent / "cursos" / "java-backend"
CONTROLO = ({"entrada": "1", "saida": "2"},)


def curso(**kw) -> Course:
    base = dict(
        nome="t", perfil="perfil curto", build="b {ficheiro}", run="r {classe}",
        regex_erro=r"^(?P<ficheiro>.+):(?P<linha>\d+): (?P<msg>.+)$",
        nodes={"a": Node(id="a", nome="A", objetivo="o", tipos=("construcao",))},
        weaknesses={}, extensao=".x", teto_briefing_bytes=4096,
    )
    base.update(kw)
    return Course(**base)


def problemas(achados, nivel) -> list[str]:
    return [f.problema for f in achados if f.nivel == nivel]


class TestLint(unittest.TestCase):
    def test_um_curso_sao_nao_tem_queixas(self):
        self.assertEqual(lint.check(curso()), [])

    def test_build_sem_ficheiro(self):
        achados = lint.check(curso(build="javac -d out"))
        self.assertTrue(any("build" in p for p in problemas(achados, lint.ERRO)))

    def test_run_sem_campo_nenhum(self):
        achados = lint.check(curso(run="java -cp out"))
        self.assertTrue(any("run" in p for p in problemas(achados, lint.ERRO)))

    def test_regex_sem_grupo_msg(self):
        achados = lint.check(curso(regex_erro="^(?P<ficheiro>.+): erro$"))
        self.assertTrue(any("msg" in p for p in problemas(achados, lint.ERRO)))

    def test_extensao_sem_ponto(self):
        achados = lint.check(curso(extensao="py"))
        self.assertTrue(any("extensao" in p for p in problemas(achados, lint.ERRO)))

    def test_reescrita_sem_construcao_nunca_sai(self):
        no = Node(id="a", nome="A", objetivo="o", tipos=("previsao", "reescrita"))
        achados = lint.check(curso(nodes={"a": no}))
        self.assertTrue(any("reescrita" in p for p in problemas(achados, lint.ERRO)))

    def test_ancora_de_outra_linguagem(self):
        no = Node(
            id="a", nome="A", objetivo="o", tipos=("construcao",),
            ancoras=(Anchor(tipo="construcao", enunciado="e", ficheiro="A.java", controlo=CONTROLO),),
        )
        achados = lint.check(curso(nodes={"a": no}))
        self.assertTrue(any(".x" in p for p in problemas(achados, lint.ERRO)))

    def test_ancora_de_tipo_que_o_no_nao_pede(self):
        no = Node(
            id="a", nome="A", objetivo="o", tipos=("construcao",),
            ancoras=(Anchor(tipo="explicar", enunciado="e", ficheiro="a.x", controlo=CONTROLO),),
        )
        achados = lint.check(curso(nodes={"a": no}))
        self.assertTrue(any("explicar" in p for p in problemas(achados, lint.AVISO)))

    def test_controlo_sem_saida(self):
        no = Node(
            id="a", nome="A", objetivo="o", tipos=("construcao",),
            ancoras=(Anchor(tipo="construcao", enunciado="e", ficheiro="a.x", controlo=({"entrada": "1"},)),),
        )
        achados = lint.check(curso(nodes={"a": no}))
        self.assertTrue(any("controlo" in p for p in problemas(achados, lint.ERRO)))

    def test_fraqueza_que_ninguem_treina(self):
        from gradus.model import Weakness

        achados = lint.check(curso(weaknesses={"w": Weakness(id="w", nome="W", descricao="d")}))
        self.assertTrue(any("'w'" in p for p in problemas(achados, lint.AVISO)))

    def test_orcamento_do_pior_dia(self):
        """The check that matters: it fits today, and dies on the day he needs it."""
        self.assertEqual(problemas(lint.check(curso(teto_briefing_bytes=400)), lint.ERRO)[0][:10], "no pior ca")
        self.assertEqual(problemas(lint.check(curso(teto_briefing_bytes=4096)), lint.ERRO), [])

    def test_no_curso_de_java_so_o_orcamento_e_que_se_queixa(self):
        java = course_mod.load(CURSO)
        self.assertEqual(lint._comandos(java) + lint._regex(java) + lint._extensao(java), [])
        for node in java.nodes.values():
            self.assertEqual(lint._ancoras(java, node), [], node.id)
