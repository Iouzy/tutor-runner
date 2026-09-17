"""The cycle: build a briefing, run one cold session, cut, measure, record, repeat."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Protocol

from . import archive, briefing as briefing_mod, event, report, state as state_mod, telemetry
from .event import Judgement, Passage
from .model import Course, Handoff, Mastery
from .scheduler import Choice, next_node


@dataclass
class RawRun:
    """What a session hands back: raw material only. The runner does the counting."""

    transcript: list[dict]
    terminal: str
    compilacoes: list[telemetry.Compilation]
    exercicio: str
    passou: bool
    kb_contexto: float
    duracao_min: int
    handoff: Handoff | None = None
    juizos: list[Judgement] = field(default_factory=list)
    duvidas_novas: list[str] = field(default_factory=list)


class Session(Protocol):
    def run(self, texto_briefing: str, node_id: str, retoma: Handoff | None) -> RawRun: ...


@dataclass
class PassageReport:
    choice: Choice
    briefing: briefing_mod.Briefing
    passage: Passage
    compilacoes: list[telemetry.Compilation] = field(default_factory=list)
    handoff: Handoff | None = None
    promocao: str | None = None


class Runner:
    """Stateless between passages by design: everything it needs is on disk."""

    def __init__(self, course: Course, course_dir: Path, workdir: Path) -> None:
        self.course = course
        self.course_dir = course_dir
        self.workdir = workdir
        self.telemetria = workdir / "telemetria"
        self.eventos = workdir / "eventos"
        self.arquivo = workdir / "arquivo"
        self.estado_path = workdir / "estado.json"

    # --- one passage -----------------------------------------------------
    def passage(self, session: Session, dia: str, handoff: Handoff | None = None) -> PassageReport | None:
        st = state_mod.load(self.estado_path)
        choice = next_node(self.course, st, date.fromisoformat(dia))
        if choice is None:
            return None
        node = self.course.node(choice.node_id)

        bf = briefing_mod.build(
            self.course, st, node,
            telemetria=self.telemetria, handoff=handoff, revisao=choice.revisao,
        )

        raw = session.run(bf.texto, node.id, handoff)

        for comp in raw.compilacoes:
            telemetry.record(self.telemetria, comp)

        st.passagens += 1
        pid = f"p{st.passagens:02d}"

        # Measured here, from the raw run — never asked of the model.
        antes, total = telemetry.count_messages(raw.transcript)
        versoes = len(raw.compilacoes)
        ok_index = next((i for i, c in enumerate(raw.compilacoes) if c.ok), None)
        versoes_ate_correr = (ok_index + 1) if ok_index is not None else versoes

        passage = Passage(
            id=pid,
            dia=dia,
            no=node.id,
            exercicio=raw.exercicio,
            resultado="passou" if raw.passou else "cortado",
            duracao_min=raw.duracao_min,
            compilacoes=len(raw.compilacoes),
            versoes_ate_correr=versoes_ate_correr,
            msgs_antes_do_1o_codigo=antes,
            msgs_total=total,
            kb_contexto=raw.kb_contexto,
            briefing_bytes=bf.bytes,
            motivo_corte="" if raw.passou else self._motivo(raw),
            juizos=raw.juizos,
            duvidas_novas=raw.duvidas_novas,
        )
        passage.validate(set(self.course.weaknesses))
        event.write(self.eventos / f"{dia}-{pid}.json", passage)
        archive.store(self.arquivo, dia, passage, raw.transcript, raw.terminal)

        promocao = self._update_state(st, passage, node.id, dia, raw)
        state_mod.save(self.estado_path, st)
        return PassageReport(
            choice=choice,
            briefing=bf,
            passage=passage,
            compilacoes=raw.compilacoes,
            handoff=raw.handoff if not raw.passou else None,
            promocao=promocao,
        )

    def _motivo(self, raw: RawRun) -> str:
        if raw.kb_contexto >= self.course.teto_contexto_kb:
            return f"contexto {raw.kb_contexto:.1f} KB ≥ teto {self.course.teto_contexto_kb:.0f} KB"
        return "fim de exercício sem passar"

    def _update_state(self, st, passage: Passage, node_id: str, dia: str, raw: RawRun) -> str | None:
        ns = st.node(node_id)
        ns.visto_em = dia
        antes = ns.dominio
        if raw.passou:
            ns.dominio = Mastery(min(int(Mastery.ESCRITO_SOZINHO), int(ns.dominio) + 1))
            st.exercicio_aberto = None
            st.no_aberto = None
        else:
            if ns.dominio < Mastery.VISTO:
                ns.dominio = Mastery.VISTO
            st.exercicio_aberto = raw.exercicio
            st.no_aberto = node_id

        for j in passage.juizos:
            if not j.fraqueza:
                continue
            w = st.weakness(j.fraqueza)
            w.ocorrencias += 1
            w.ultimas.append(dia)
            w.ultimas = w.ultimas[-10:]

        if ns.dominio != antes:
            return f"{node_id}: {antes.label} → {ns.dominio.label}"
        return None

    # --- generated files -------------------------------------------------
    def regenerate(self) -> None:
        st = state_mod.load(self.estado_path)
        escolha = next_node(self.course, st)
        proximo = None
        if escolha:
            proximo = f"{self.course.node(escolha.node_id).nome} ({escolha.motivo})"
        (self.workdir / "ESTADO.md").write_text(report.estado_md(self.course, st, proximo), encoding="utf-8")
        passagens = event.read_all(self.eventos) if self.eventos.exists() else []
        (self.workdir / "HISTORICO.md").write_text(report.historico_md(self.course, passagens), encoding="utf-8")
