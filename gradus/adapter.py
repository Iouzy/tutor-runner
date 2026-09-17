"""The real cold session: `claude -p`, one exercise, then dead.

Two rules are enforced here because here is where they cost money:

- the model runs with `--restricted`, so it has no Bash and no editor. Whoever
  compiles is the program, and the telemetry stays a measurement instead of a
  story the model tells about itself.
- `ANTHROPIC_API_KEY` must be absent, or every session is billed to the API
  instead of coming out of the subscription.
"""
from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# Onde o Claude Code costuma ficar quando não está no PATH da shell que abriu o
# gradus — um instalador que escreve no .zshrc não serve de nada a um subprocesso.
CAMINHOS_PROVAVEIS = (
    "~/.claude/local/claude",
    "~/.local/bin/claude",
    "/usr/local/bin/claude",
    "/opt/homebrew/bin/claude",
    "~/.npm-global/bin/claude",
    "~/.volta/bin/claude",
    "~/.bun/bin/claude",
)


def encontrar(nome: str = "claude") -> str | None:
    """O PATH primeiro, depois os sítios do costume. `GRADUS_CLAUDE` ganha a tudo,
    para quem o tem noutro sítio não ter de editar código nenhum."""
    posto = os.environ.get("GRADUS_CLAUDE")
    if posto:
        return posto if Path(posto).expanduser().exists() else None
    achado = shutil.which(nome)
    if achado:
        return achado
    for caminho in CAMINHOS_PROVAVEIS:
        alvo = Path(caminho).expanduser()
        if alvo.exists():
            return str(alvo)
    return None


class ClaudeError(Exception):
    """Raised with the fix in the message, never just the symptom."""


@dataclass(frozen=True)
class Resposta:
    texto: str
    sessao: str | None
    tokens_entrada: int = 0
    tokens_saida: int = 0
    custo_usd: float = 0.0
    bruto: str = ""             # the raw stdout, kept for the archive


@dataclass
class Claude:
    comando: list[str] = field(default_factory=lambda: ["claude"])
    modelo: str | None = None
    timeout: int = 600
    extra: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.comando, str):
            self.comando = shlex.split(self.comando)

    # --- the two calls a conversation needs -------------------------------
    def arrancar(self, sistema: str, mensagem: str) -> Resposta:
        return self._correr(["--system-prompt", sistema], mensagem)

    def continuar(self, sessao: str, mensagem: str) -> Resposta:
        if not sessao:
            raise ClaudeError(
                "não há id de sessão para retomar — a primeira resposta veio sem ele; "
                "corre `gradus doctor` e confirma a versão do claude"
            )
        return self._correr(["--resume", sessao], mensagem)

    # --- the process ------------------------------------------------------
    def _correr(self, args: list[str], mensagem: str) -> Resposta:
        if os.environ.get("ANTHROPIC_API_KEY"):
            raise ClaudeError(
                "a ANTHROPIC_API_KEY está posta — assim cada sessão é paga à API em vez "
                "de sair da subscrição; faz `unset ANTHROPIC_API_KEY` e abre outro terminal"
            )
        binario = encontrar(self.comando[0]) if len(self.comando) == 1 else self.comando[0]
        if binario is None:
            raise ClaudeError(
                f"não encontrei o '{self.comando[0]}' — instala o Claude Code, ou, se já o "
                f"tens, diz onde está: export GRADUS_CLAUDE=$(command -v claude)"
            )
        self.comando[0] = binario
        cmd = [
            *self.comando, "-p", "--output-format", "json",
            # No Bash, no file edits: the model teaches, the program measures.
            "--restricted", "--permission-prompts", "none",
            *(["--model", self.modelo] if self.modelo else []),
            *self.extra, *args, mensagem,
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout)
        except subprocess.TimeoutExpired:
            raise ClaudeError(
                f"a sessão passou {self.timeout}s sem responder — corta e recomeça; "
                f"o exercício fica guardado e a próxima passagem retoma-o"
            ) from None
        if proc.returncode != 0:
            primeira = (proc.stderr.strip().splitlines() or ["sem mensagem"])[0]
            raise ClaudeError(f"o claude devolveu erro: {primeira}")
        return _ler(proc.stdout)


def _ler(saida: str) -> Resposta:
    """The CLI's own JSON. The usage numbers are measured by the CLI, not declared
    by the model, which is why they are allowed anywhere near the ledger."""
    try:
        dados = json.loads(saida)
    except json.JSONDecodeError:
        raise ClaudeError(
            "o claude não devolveu JSON — esta versão mudou o --output-format; "
            "atualiza o Claude Code ou fixa a versão"
        ) from None
    if isinstance(dados, list):                 # some versions wrap it in a list
        dados = next((d for d in reversed(dados) if isinstance(d, dict) and "result" in d), {})
    if dados.get("is_error"):
        raise ClaudeError(f"o claude devolveu erro: {dados.get('result', 'sem mensagem')}")
    texto = dados.get("result") or dados.get("text") or ""
    if not texto:
        raise ClaudeError("o claude respondeu sem texto — repete a mensagem")
    uso = dados.get("usage") or {}
    return Resposta(
        texto=texto,
        sessao=dados.get("session_id"),
        tokens_entrada=int(uso.get("input_tokens", 0) or 0),
        tokens_saida=int(uso.get("output_tokens", 0) or 0),
        custo_usd=float(dados.get("total_cost_usd", 0.0) or 0.0),
        bruto=saida,
    )
