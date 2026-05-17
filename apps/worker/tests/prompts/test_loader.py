from pathlib import Path

import pytest

from src.prompts.loader import PromptError, PromptLoader, load_prompt


def test_load_default_prompt_sabueso():
    p = load_prompt("sabueso", variables={"country": "pe", "locale": "es"})
    assert p.callsign == "sabueso"
    assert p.model == "anthropic/claude-sonnet-4.6"
    assert p.strategy == "rewoo"
    assert len(p.breakpoints) == 4
    assert "Sabueso" in p.body
    assert "país pe" in p.body.lower() or "país: pe" in p.body.lower()


def test_load_all_eight_placeholders():
    expected = [
        "sabueso",
        "buscador",
        "tasadora",
        "contador",
        "letrado",
        "detective",
        "periodista",
        "jueza_moa",
    ]
    for name in expected:
        p = load_prompt(
            name, variables={"country": "pe", "locale": "es", "task": "demo"}
        )
        assert p.callsign
        assert p.breakpoints == [0, 1, 2, 3]


def test_jinja_renders_variables(tmp_path: Path):
    (tmp_path / "demo_system.md").write_text(
        "---\ncallsign: demo\nbreakpoints: [0]\n---\nHola {{ name }}!\n",
        encoding="utf-8",
    )
    loader = PromptLoader(tmp_path)
    p = loader.load("demo", variables={"name": "mundo"})
    assert "Hola mundo!" in p.body


def test_missing_variable_raises(tmp_path: Path):
    (tmp_path / "demo_system.md").write_text(
        "---\ncallsign: demo\n---\n{{ required_var }}\n",
        encoding="utf-8",
    )
    loader = PromptLoader(tmp_path)
    with pytest.raises(PromptError):
        loader.load("demo", variables={})


def test_missing_file_raises():
    with pytest.raises(PromptError):
        load_prompt("nonexistent_agent")


def test_bad_frontmatter_raises(tmp_path: Path):
    # invalid YAML: unbalanced bracket
    (tmp_path / "bad_system.md").write_text(
        "---\nfoo: [unclosed\n---\nbody\n",
        encoding="utf-8",
    )
    loader = PromptLoader(tmp_path)
    with pytest.raises(PromptError):
        loader.load("bad")


def test_frontmatter_not_mapping_raises(tmp_path: Path):
    # valid YAML but not a mapping
    (tmp_path / "weird_system.md").write_text(
        "---\n- just a list\n- of strings\n---\nbody\n",
        encoding="utf-8",
    )
    loader = PromptLoader(tmp_path)
    with pytest.raises(PromptError):
        loader.load("weird")


def test_no_frontmatter_returns_empty_meta(tmp_path: Path):
    (tmp_path / "plain_system.md").write_text("just a body\n", encoding="utf-8")
    loader = PromptLoader(tmp_path)
    p = loader.load("plain")
    assert p.metadata == {}
    assert p.body.strip() == "just a body"


def test_locale_path_preferred(tmp_path: Path):
    (tmp_path / "demo_system.md").write_text(
        "---\ncallsign: demo\n---\nDEFAULT\n", encoding="utf-8"
    )
    (tmp_path / "en").mkdir()
    (tmp_path / "en" / "demo_system.md").write_text(
        "---\ncallsign: demo\n---\nENGLISH\n", encoding="utf-8"
    )
    loader = PromptLoader(tmp_path)
    assert "ENGLISH" in loader.load("demo", locale="en").body
    assert "DEFAULT" in loader.load("demo", locale="es").body  # fallback
