"""Markdown + YAML-frontmatter prompt loader.

Each prompt file has the shape:

    ---
    callsign: contador
    model: moonshot/kimi-k2.6
    strategy: rewoo
    locale: es
    breakpoints: [0, 1, 2, 3]      # message indices that end a cache section
    ---
    [BREAKPOINT 1: identity]
    ...

    [BREAKPOINT 2: roster]
    ...

The loader returns the rendered body (Jinja2-templated) plus the parsed
metadata so BaseInvestigator can wire the cache breakpoints and pick the
right model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, StrictUndefined, Template, UndefinedError

_PROMPTS_DIR = Path(__file__).resolve().parent

_FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(?P<meta>.*?)\n---\s*\n(?P<body>.*)\Z",
    re.DOTALL,
)


class PromptError(ValueError):
    pass


@dataclass
class LoadedPrompt:
    name: str
    body: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def callsign(self) -> str:
        return str(self.metadata.get("callsign", self.name))

    @property
    def model(self) -> str | None:
        v = self.metadata.get("model")
        return str(v) if v else None

    @property
    def strategy(self) -> str | None:
        v = self.metadata.get("strategy")
        return str(v) if v else None

    @property
    def breakpoints(self) -> list[int]:
        bps = self.metadata.get("breakpoints") or []
        return [int(x) for x in bps]

    @property
    def allowed_tools(self) -> list[str]:
        tools = self.metadata.get("allowed_tools") or []
        return [str(t) for t in tools]


class PromptLoader:
    """Resolves prompt names to files and renders them with Jinja2."""

    def __init__(
        self,
        prompts_dir: Path | str | None = None,
        *,
        strict: bool = True,
    ) -> None:
        self.prompts_dir = Path(prompts_dir) if prompts_dir else _PROMPTS_DIR
        self.env = Environment(
            autoescape=False,
            undefined=StrictUndefined if strict else None,
            keep_trailing_newline=True,
        )

    def _resolve_path(self, name: str, locale: str | None) -> Path:
        # try locale-specific first, then default
        candidates: list[Path] = []
        base = name if name.endswith(".md") else f"{name}_system.md"
        if locale:
            candidates.append(self.prompts_dir / locale / base)
        candidates.append(self.prompts_dir / base)
        for c in candidates:
            if c.is_file():
                return c
        raise PromptError(
            f"prompt '{name}' not found (looked in {[str(c) for c in candidates]})"
        )

    def load(
        self,
        name: str,
        variables: dict[str, Any] | None = None,
        locale: str | None = None,
    ) -> LoadedPrompt:
        path = self._resolve_path(name, locale)
        raw = path.read_text(encoding="utf-8")
        meta, body = _split_frontmatter(raw)
        if locale and "locale" not in meta:
            meta["locale"] = locale
        try:
            template: Template = self.env.from_string(body)
            rendered = template.render(**(variables or {}))
        except UndefinedError as exc:
            raise PromptError(f"missing variable in prompt '{name}': {exc}") from exc
        return LoadedPrompt(name=name, body=rendered, metadata=meta)


def _split_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    m = _FRONTMATTER_RE.match(raw)
    if not m:
        return {}, raw
    meta_raw = m.group("meta")
    body = m.group("body")
    try:
        meta = yaml.safe_load(meta_raw) or {}
    except yaml.YAMLError as exc:
        raise PromptError(f"invalid YAML frontmatter: {exc}") from exc
    if not isinstance(meta, dict):
        raise PromptError("frontmatter must be a YAML mapping")
    return meta, body


_DEFAULT_LOADER = PromptLoader()


def load_prompt(
    name: str,
    variables: dict[str, Any] | None = None,
    locale: str | None = None,
) -> LoadedPrompt:
    """Module-level convenience wrapper around the default loader."""
    return _DEFAULT_LOADER.load(name, variables=variables, locale=locale)
