from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

from wc_forecaster.bracket import BRACKET_METHODS


def load_draw_script() -> Any:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "draw_knockout_bracket.py"
    spec = importlib.util.spec_from_file_location("draw_knockout_bracket", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return cast(ModuleType, module)


def test_main_renders_every_method_for_all(monkeypatch) -> None:
    draw_knockout_bracket = load_draw_script()
    rendered = []

    def fake_render_method(run_dir: Path, flags_dir: Path, bracket_method: str) -> None:
        rendered.append((run_dir, flags_dir, bracket_method))

    monkeypatch.setattr(
        "sys.argv",
        [
            "draw_knockout_bracket.py",
            "--run-dir",
            "outputs/test-run",
            "--bracket-method",
            "all",
            "--flags-dir",
            "outputs/test-flags",
        ],
    )
    monkeypatch.setattr(draw_knockout_bracket, "render_method", fake_render_method)

    draw_knockout_bracket.main()

    assert [method for _run_dir, _flags_dir, method in rendered] == BRACKET_METHODS
    assert {run_dir for run_dir, _flags_dir, _method in rendered} == {Path("outputs/test-run")}
    assert {flags_dir for _run_dir, flags_dir, _method in rendered} == {Path("outputs/test-flags")}
