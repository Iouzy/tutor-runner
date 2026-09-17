from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from . import course as course_mod, state as state_mod
from .fake import DIA_TIPO, ScriptedSession
from .loop import Runner
from .model import NOMES_TIPO, CourseError, Mastery
from .scheduler import next_node

RAIZ = Path(__file__).resolve().parent.parent
DIM, BOLD, RESET = "\033[2m", "\033[1m", "\033[0m"
LARANJA, VERDE, VERM = "\033[38;5;173m", "\033[38;5;72m", "\033[38;5;131m"


def _course(args):
    return course_mod.load(Path(args.curso)), Path(args.curso)


def _work(args) -> Path:
    """One ledger per course. What you know in Java is not what you know in Python —
    only the profile and the transversal weaknesses cross over."""
    if args.trabalho:
        return Path(args.trabalho)
    return RAIZ / "trabalho" / Path(args.curso).name


def _semear(runner: Runner) -> None:
    """Where the real repo is today: fundamentals solid, arrays untouched."""
    st = state_mod.State()
    for n in ("base-tipos", "base-condicionais", "base-ciclos", "base-funcoes"):
        st.node(n).dominio = Mastery.ESCRITO_SOZINHO
        st.node(n).visto_em = "2026-09-10"
    for n in ("base-escolha", "base-entrada"):
        st.node(n).dominio = Mastery.ESCRITO_COM_AJUDA
        st.node(n).visto_em = "2026-09-16"
    for w, dias in (("limites-ciclos", ["2026-09-12", "2026-09-16"]), ("buffer-scanner", ["2026-09-16"])):
        if w not in runner.course.weaknesses:    # buffer-scanner só existe em Java
            continue
        st.weakness(w).ocorrencias = len(dias)
        st.weakness(w).ultimas = dias
    state_mod.save(runner.estado_path, st)


def cmd_demo(args) -> int:
    curso, curso_dir = _course(args)
    work = _work(args)
    if work.exists() and args.limpar:
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)

    runner = Runner(curso, curso_dir, work)
    if not runner.estado_path.exists():
        _semear(runner)

    print(f"\n{BOLD}gradus{RESET} · curso {curso.nome} · teto de briefing {curso.teto_briefing_bytes} B")
    print(f"{DIM}sessão de estudo de 2026-09-17 — cinco passagens, cada uma uma sessão fria{RESET}\n")

    sessao = ScriptedSession(DIA_TIPO, fraquezas=set(curso.weaknesses))
    dia = "2026-09-17"
    handoff = None
    acumulado = 0.0

    for _ in range(len(DIA_TIPO)):
        rel = runner.passage(sessao, dia, handoff)
        if rel is None:
            print("nada elegível no grafo.")
            break
        p, bf = rel.passage, rel.briefing
        rev = " (revisão)" if rel.choice.revisao else ""
        ret = f" {LARANJA}retoma{RESET}" if handoff else ""
        tipo = NOMES_TIPO.get(p.tipo, p.tipo)
        print(f"{BOLD}▸ {p.id}{RESET}  {p.no}  {VERDE}{tipo}{RESET}{rev}{ret}  {DIM}— {rel.choice.motivo}{RESET}")
        print(f"   briefing  {BOLD}{bf.relatorio()}{RESET}")
        for c in rel.compilacoes:
            marca = f"{VERDE}ok{RESET}" if c.ok else f"{VERM}{c.erro}{RESET}"
            print(f"   {DIM}javac{RESET} {c.t}  {c.ficheiro}  {marca}")
        acumulado += p.kb_contexto
        if p.resultado == "passou":
            print(f"   {VERDE}✓ passou{RESET}  {p.kb_contexto:.1f} KB · adiamento {p.racio_adiamento}", end="")
            print(f"  {DIM}·{RESET} {LARANJA}{rel.promocao}{RESET}" if rel.promocao else "")
            handoff = None
        else:
            print(f"   {LARANJA}✂ corte{RESET}  {p.motivo_corte}")
            handoff = rel.handoff
            if handoff:
                n = len(handoff.to_json().encode())
                cor = VERDE if n <= curso.teto_bilhete_bytes else VERM
                print(f"   bilhete   {cor}{n} B{RESET} {DIM}(teto {curso.teto_bilhete_bytes}){RESET}")
        print()

    runner.regenerate()
    passados = len(list((work / "eventos").glob("*.json")))
    from .event import read_all

    ps = read_all(work / "eventos")
    ok = [x for x in ps if x.resultado == "passou"]
    print(f"{BOLD}Custo{RESET}")
    print(f"  gradus          {acumulado:.1f} KB no dia · {acumulado / max(len(ok), 1):.1f} KB por exercício passado")
    kbs = [x.kb_contexto for x in ps]
    unica = sum(sum(kbs[: i + 1]) for i in range(len(kbs)))
    print(f"  {DIM}sessão única    {unica:.1f} KB no dia · cada exercício relê tudo o que veio antes{RESET}")
    print(f"  {DIM}                (contrafactual com o mesmo trabalho feito; não é uma medição){RESET}")
    print(f"\n{BOLD}Gerados{RESET} {DIM}(nenhum escrito por um modelo){RESET}")
    for f in ("ESTADO.md", "HISTORICO.md", "estado.json"):
        print(f"  {work / f}")
    print(f"  {work / 'arquivo' / dia}  {DIM}— {passados} transcrições cruas, nunca relidas{RESET}\n")
    return 0


def cmd_proximo(args) -> int:
    curso, _ = _course(args)
    st = state_mod.load(_work(args) / "estado.json")
    escolha = next_node(curso, st)
    if not escolha:
        print("nada elegível.")
        return 1
    tipo = NOMES_TIPO.get(escolha.tipo, escolha.tipo)
    print(f"{curso.node(escolha.node_id).nome}  {VERDE}{tipo}{RESET}  {DIM}— {escolha.motivo}{RESET}")
    return 0


def cmd_briefing(args) -> int:
    from . import briefing as briefing_mod

    curso, _ = _course(args)
    work = _work(args)
    st = state_mod.load(work / "estado.json")
    escolha = next_node(curso, st)
    if not escolha:
        print("nada elegível.")
        return 1
    bf = briefing_mod.build(
        curso, st, curso.node(escolha.node_id),
        telemetria=work / "telemetria", revisao=escolha.revisao, tipo=escolha.tipo,
    )
    print(bf.texto)
    print(f"\n{DIM}--- {bf.relatorio()} · teto {curso.teto_briefing_bytes} B ---{RESET}")
    return 0


def cmd_lint(args) -> int:
    """Says what will break before a study session finds out. Touches nothing."""
    from . import lint as lint_mod

    try:
        curso, _ = _course(args)
    except CourseError as exc:
        print(f"{VERM}erro{RESET}  curso.toml  {exc}")
        return 1

    achados = lint_mod.check(curso)
    print(f"\n{BOLD}gradus lint{RESET} · curso {curso.nome}\n")
    for f in achados:
        cor = VERM if f.nivel == lint_mod.ERRO else LARANJA
        print(f"{cor}{f.nivel:6}{RESET}{BOLD}{f.onde}{RESET}  {f.problema}")
        print(f"       {DIM}→ {f.conserto}{RESET}")
    erros = sum(1 for f in achados if f.nivel == lint_mod.ERRO)
    avisos = len(achados) - erros
    if not achados:
        print(f"{VERDE}sem nada a apontar.{RESET}")
    print(f"\n{erros} erro(s) · {avisos} aviso(s)\n")
    return 1 if erros else 0


def cmd_doctor(args) -> int:
    """The only command that touches the machine. Every queixa traz o comando."""
    from . import doctor as doctor_mod

    curso, _ = _course(args)
    print(f"\n{BOLD}gradus doctor{RESET} · curso {curso.nome}\n")
    checks = doctor_mod.run(curso, _work(args))
    for c in checks:
        if c.ok:
            marca = f"{VERDE}✓{RESET}"
        else:
            marca = f"{VERM}✗{RESET}" if c.nivel == doctor_mod.ERRO else f"{LARANJA}!{RESET}"
        print(f" {marca} {BOLD}{c.nome:18}{RESET}{c.detalhe}")
        if c.conserto:
            print(f"   {DIM}→ {c.conserto}{RESET}")
    falhas = [c for c in checks if not c.ok and c.nivel == doctor_mod.ERRO]
    print(f"\n{len(falhas)} por resolver de {len(checks)} verificações\n")
    return 1 if falhas else 0


def cmd_regenerar(args) -> int:
    curso, curso_dir = _course(args)
    work = _work(args)
    runner = Runner(curso, curso_dir, work)
    runner.regenerate()
    alvo = "ESTADO.md" if args.cmd == "estado" else "HISTORICO.md"
    print((work / alvo).read_text(encoding="utf-8"))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gradus", description="ensina gastando o mínimo de contexto")
    ap.add_argument("--curso", default=str(RAIZ / "cursos" / "java-backend"))
    ap.add_argument("--trabalho", default=None, help="por omissão, trabalho/<curso>/")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("demo", help="corre um dia de estudo inteiro, sem modelo e sem rede")
    d.add_argument("--limpar", action="store_true", help="apaga o trabalho anterior primeiro")
    d.set_defaults(func=cmd_demo)
    sub.add_parser("proximo", help="que exercício vem a seguir, e porquê").set_defaults(func=cmd_proximo)
    sub.add_parser("briefing", help="imprime o contexto exato que a próxima sessão recebe").set_defaults(func=cmd_briefing)
    sub.add_parser("lint", help="o que rebenta neste curso antes de o usar").set_defaults(func=cmd_lint)
    sub.add_parser("doctor", help="a máquina aguenta este curso? com o comando do conserto").set_defaults(func=cmd_doctor)
    sub.add_parser("estado", help="regenera e mostra ESTADO.md").set_defaults(func=cmd_regenerar)
    sub.add_parser("historico", help="regenera e mostra HISTORICO.md").set_defaults(func=cmd_regenerar)

    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except CourseError as exc:
        print(f"{VERM}erro de curso:{RESET} {exc}", file=sys.stderr)
        return 2
