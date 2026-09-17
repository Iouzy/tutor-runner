"""O ciclo inteiro do ecrã principal, sem tkinter e sem modelo nenhum."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gradus import config as config_mod, course as course_mod, state as state_mod
from gradus.briefing import TETO_PERFIL
from gradus.fake import ConversaSeca
from gradus.gui import controller
from gradus.model import CourseError, Mastery

RAIZ = Path(__file__).resolve().parent.parent


class TestPerfil(unittest.TestCase):
    def test_as_respostas_viram_instrucoes_para_quem_ensina(self):
        md = controller.perfil_md({
            "parou": "desisti nos arrays",
            "encrava": "Leio mais sobre o assunto",
            "percebe": "Com uma analogia",
            "erro": "Uma pista de cada vez",
            "tempo": "45 minutos",
            "objetivo": "organizar os meus turnos",
        })
        self.assertIn("desisti nos arrays", md)
        self.assertIn("analogias", md)
        self.assertIn("empurra-o a correr o programa", md)
        self.assertIn("nunca a linha corrigida", md)
        self.assertIn("Português de Portugal", md)

    def test_um_perfil_gordo_e_cortado_ate_caber(self):
        md = controller.perfil_md({p.id: "palavra " * 400 for p in controller.PERGUNTAS})
        self.assertLessEqual(len(md.encode("utf-8")), TETO_PERFIL)

    def test_perguntas_saltadas_nao_deixam_buracos(self):
        md = controller.perfil_md({"parou": "", "encrava": "", "percebe": "", "erro": "", "tempo": "", "objetivo": ""})
        self.assertNotIn("«»", md)
        self.assertIn("Nunca lhe dês código feito", md)


class TestEscolhaDeCurso(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        (self.raiz / "cursos" / "python").mkdir(parents=True)
        (self.raiz / "cursos" / "python" / "curso.toml").write_text(
            'nome = "Python do zero"\nlinguagem = "python"\nextensao = ".py"\n', encoding="utf-8"
        )

    def test_o_programa_e_que_escreve_a_escolha(self):
        controller.escolher_curso(self.raiz, "cursos/python")
        cfg = config_mod.load(self.raiz)
        self.assertEqual(cfg.curso, "cursos/python")
        self.assertTrue(cfg.criado_em)

    def test_um_curso_que_nao_existe_e_recusado(self):
        with self.assertRaises(CourseError):
            controller.escolher_curso(self.raiz, "cursos/cobol")

    def test_os_cartoes_saem_do_proprio_curso(self):
        cartoes = config_mod.disponiveis(self.raiz)
        self.assertEqual(cartoes[0].nome, "Python do zero")
        self.assertEqual(cartoes[0].extensao, ".py")


class TestNomeDeFicheiro(unittest.TestCase):
    def setUp(self):
        self.java = course_mod.load(RAIZ / "cursos" / "java-backend")
        self.python = course_mod.load(RAIZ / "cursos" / "python")

    def _abertura(self, curso, node_id, tipo):
        from gradus.loop import Abertura
        from gradus.scheduler import Choice

        return Abertura(
            choice=Choice(node_id, "motivo", tipo=tipo), node=curso.node(node_id), briefing=None
        )

    def test_java_usa_o_nome_da_classe(self):
        nome = controller.nome_de_ficheiro(self.java, self._abertura(self.java, "base-ciclos", "construcao"))
        self.assertEqual(nome, "BaseCiclos.java")

    def test_python_usa_minusculas(self):
        nome = controller.nome_de_ficheiro(self.python, self._abertura(self.python, "base-ciclos", "construcao"))
        self.assertEqual(nome, "base_ciclos.py")

    def test_havendo_ancora_do_tipo_o_ficheiro_e_o_dela(self):
        nome = controller.nome_de_ficheiro(
            self.java, self._abertura(self.java, "base-listas", "erro-plantado")
        )
        self.assertEqual(nome, "MaiorQuebrado.java")

    def test_o_esqueleto_nao_tem_codigo_nenhum(self):
        esq = controller.esqueleto(self.java, self._abertura(self.java, "base-ciclos", "construcao"))
        self.assertTrue(all(not l.strip() or l.startswith("//") for l in esq.splitlines()))


class TestEstudo(unittest.TestCase):
    """Um exercício do princípio ao fim, como o ecrã principal o faz."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.curso_dir = RAIZ / "cursos" / "python"
        self.curso = course_mod.load(self.curso_dir)
        self.estudo = controller.Estudo(
            self.curso, self.curso_dir, self.work,
            dialogo=lambda ab, ex: ConversaSeca(ab.briefing.texto, ab.node.id, ex, self.curso.teto_contexto_kb),
            dia="2026-09-17",
        )

    def test_um_exercicio_inteiro(self):
        abertura = self.estudo.comecar()
        self.assertIsNotNone(abertura)
        self.assertTrue(self.estudo.caminho_exercicio().exists())
        self.estudo.primeira_fala()
        self.estudo.enviar("acho que dá 3")

        self.estudo.caminho_exercicio().write_text("print(3)\n", encoding="utf-8")
        attempt, _ = self.estudo.compilar()
        self.assertTrue(attempt.ok)
        self.assertIn("3", attempt.saida)

        relatorio = self.estudo.terminar(passou=True)
        self.assertEqual(relatorio.passage.resultado, "passou")
        self.assertEqual(relatorio.passage.compilacoes, 1)
        self.assertTrue((self.work / "ESTADO.md").exists())
        self.assertTrue(list((self.work / "eventos").glob("*.json")))

        st = state_mod.load(self.work / "estado.json")
        self.assertGreaterEqual(st.node(abertura.node.id).dominio, Mastery.VISTO)

    def test_um_erro_fica_na_telemetria_sem_ninguem_se_lembrar(self):
        self.estudo.comecar()
        self.estudo.primeira_fala()
        self.estudo.caminho_exercicio().write_text("def f(\n", encoding="utf-8")
        attempt, _ = self.estudo.compilar()
        self.assertFalse(attempt.compilou)
        linhas = (self.work / "telemetria" / "compilacoes.jsonl").read_text(encoding="utf-8")
        self.assertIn("SyntaxError", linhas)

    def test_um_corte_deixa_o_exercicio_aberto_e_a_seguir_retoma_o(self):
        self.estudo.comecar()
        self.estudo.primeira_fala()
        primeiro = self.estudo.exercicio
        self.estudo.terminar(passou=False)

        st = state_mod.load(self.work / "estado.json")
        self.assertEqual(st.exercicio_aberto, primeiro)

        abertura = self.estudo.comecar()
        self.assertEqual(self.estudo.exercicio, primeiro)
        self.assertIn("aberto", abertura.choice.motivo)

    def test_o_rodape_mostra_o_que_a_sessao_esta_a_custar(self):
        self.estudo.comecar()
        self.estudo.primeira_fala()
        r = self.estudo.rodape()
        self.assertIn("B  [", r.briefing)
        self.assertGreater(r.kb, 0)
        self.assertEqual(r.teto_kb, self.curso.teto_contexto_kb)
        self.assertLess(r.cheio, 1.0)

    def test_sem_sessao_a_decorrer_recusa_compilar(self):
        with self.assertRaises(CourseError):
            self.estudo.compilar()


class TestSimulacao(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.curso = course_mod.load(RAIZ / "cursos" / "python")
        from gradus.workspace import Workspace

        Workspace(self.curso, self.work).criar(
            "meu.py",
            "total = 0\nfor i in range(1, 5):\n    if i < 3:\n        total = total + i\nprint(total)\n",
        )
        self.sim = controller.Simulacao(self.curso, self.work, "base-listas", "meu.py", dia="2026-09-18")
        st = state_mod.State()
        st.node("base-listas").dominio = Mastery.ESCRITO_SOZINHO
        state_mod.save(self.work / "estado.json", st)

    def test_a_pergunta_sai_do_ficheiro_e_a_correcao_da_maquina(self):
        previsao = self.sim.proxima()
        self.assertIsNotNone(previsao)
        certo = self.sim.responder(previsao.saida_certa)
        self.assertTrue(certo.certo)
        self.assertEqual(certo.seguidas, 1)
        self.assertEqual(certo.em_falta, 9)

    def test_errar_põe_a_conta_a_zero_e_diz_a_certa(self):
        previsao = self.sim.proxima()
        r = self.sim.responder("seja o que for menos isso")
        self.assertFalse(r.certo)
        self.assertEqual(r.certa, previsao.saida_certa)
        self.assertEqual(r.seguidas, 0)

    def test_responder_sem_pergunta_na_mesa(self):
        with self.assertRaises(CourseError):
            self.sim.responder("3")
