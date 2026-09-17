"""estado.json — the pointer. Generated and written by the program, never by a model."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from .model import Mastery


@dataclass
class NodeState:
    dominio: Mastery = Mastery.POR_TOCAR
    visto_em: str | None = None       # last day this node was worked
    previsoes_seguidas: int = 0        # the simulator's streak; 10 promotes
    tipos_feitos: dict[str, str] = field(default_factory=dict)   # exercise type -> last day


@dataclass
class WeaknessState:
    ocorrencias: int = 0
    ultimas: list[str] = field(default_factory=list)   # dates, newest last
    resolvida_em: str | None = None

    @property
    def ativa(self) -> bool:
        return self.resolvida_em is None


@dataclass
class State:
    nos: dict[str, NodeState] = field(default_factory=dict)
    fraquezas: dict[str, WeaknessState] = field(default_factory=dict)
    exercicio_aberto: str | None = None     # the durable unit: survives a session cut
    no_aberto: str | None = None
    tipo_aberto: str | None = None
    ultimo_no: str | None = None            # the pair the interleaving rule looks at
    ultimo_tipo: str | None = None
    passagens: int = 0

    def node(self, node_id: str) -> NodeState:
        return self.nos.setdefault(node_id, NodeState())

    def weakness(self, w_id: str) -> WeaknessState:
        return self.fraquezas.setdefault(w_id, WeaknessState())

    def fraquezas_ativas(self, limite: int = 3) -> list[str]:
        """The few that earn a slot in the briefing — most recent evidence first."""
        vivas = [(w_id, w) for w_id, w in self.fraquezas.items() if w.ativa and w.ocorrencias]
        vivas.sort(key=lambda kv: (kv[1].ultimas[-1] if kv[1].ultimas else "", kv[1].ocorrencias), reverse=True)
        return [w_id for w_id, _ in vivas[:limite]]


def load(path: Path) -> State:
    if not path.exists():
        return State()
    raw = json.loads(path.read_text(encoding="utf-8"))
    return State(
        nos={
            k: NodeState(
                dominio=Mastery(v["dominio"]),
                visto_em=v.get("visto_em"),
                previsoes_seguidas=v.get("previsoes_seguidas", 0),
                tipos_feitos=dict(v.get("tipos_feitos", {})),
            )
            for k, v in raw.get("nos", {}).items()
        },
        fraquezas={
            k: WeaknessState(
                ocorrencias=v.get("ocorrencias", 0),
                ultimas=v.get("ultimas", []),
                resolvida_em=v.get("resolvida_em"),
            )
            for k, v in raw.get("fraquezas", {}).items()
        },
        exercicio_aberto=raw.get("exercicio_aberto"),
        no_aberto=raw.get("no_aberto"),
        tipo_aberto=raw.get("tipo_aberto"),
        ultimo_no=raw.get("ultimo_no"),
        ultimo_tipo=raw.get("ultimo_tipo"),
        passagens=raw.get("passagens", 0),
    )


def save(path: Path, state: State) -> None:
    payload = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "nos": {
            k: {
                "dominio": int(v.dominio),
                "visto_em": v.visto_em,
                "previsoes_seguidas": v.previsoes_seguidas,
                "tipos_feitos": dict(sorted(v.tipos_feitos.items())),
            }
            for k, v in sorted(state.nos.items())
        },
        "fraquezas": {
            k: {"ocorrencias": v.ocorrencias, "ultimas": v.ultimas, "resolvida_em": v.resolvida_em}
            for k, v in sorted(state.fraquezas.items())
        },
        "exercicio_aberto": state.exercicio_aberto,
        "no_aberto": state.no_aberto,
        "tipo_aberto": state.tipo_aberto,
        "ultimo_no": state.ultimo_no,
        "ultimo_tipo": state.ultimo_tipo,
        "passagens": state.passagens,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def hoje() -> str:
    return date.today().isoformat()
