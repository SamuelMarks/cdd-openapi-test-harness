"""Unit tests for `generate_dashboard.py`, `update_all_tables.py`, `update_readme_status.py`, and `update_testing_coverage.py`."""

import subprocess
from pathlib import Path
from typing import List

import pytest

from scripts import (
    generate_dashboard,
    update_all_tables,
    update_readme_status,
    update_testing_coverage,
)


def test_generate_dashboard_all_branches(tmp_path: Path) -> None:
    """Verify `analyze_compliance`, `render_dashboard`, `generate_dashboard`, and `main`."""
    missing_res = generate_dashboard.analyze_compliance(str(tmp_path / "missing.md"))
    assert all(v == "❓ Missing Docs" for v in missing_res.values())

    full_claim = tmp_path / "full.md"
    full_claim.write_text("This project is 100% compliant with the OpenAPI 3.2.0 spec.", encoding="utf-8")
    full_res = generate_dashboard.analyze_compliance(str(full_claim))
    assert all(v == "✅ Supported" for v in full_res.values())

    nl = chr(10)
    table_doc = tmp_path / "table.md"
    table_doc.write_text(
        nl.join(
            [
                "# Compliance",
                "Overview paragraph here.",
                "| Feature | Status |",
                "| --- | --- |",
                "| $self | ✅ Supported |",
                "| summary | 🚧 Partial |",
                "| server | ❌ Missing |",
                "| query | mystery |",
                "| single_col |",
            ]
        ),
        encoding="utf-8",
    )
    table_res = generate_dashboard.analyze_compliance(str(table_doc))
    assert table_res["Root (`$self`, `jsonSchemaDialect`, `webhooks`)"] == "✅ Supported"
    assert table_res["Info (`summary`, `license.identifier`)"] == "🚧 Partial"
    assert table_res["Server (`name`, `variables`)"] == "❌ Missing"

    sec_doc = tmp_path / "sections.md"
    sec_doc.write_text(
        nl.join(
            [
                "# Sections Only",
                "## Supported Features",
                "- 2020-12",
                "- prefixencoding",
                "## Pending Features",
                "- prefixencoding",
                "- parameter",
                "## Other Notes",
                " mentions response links ",
            ]
        ),
        encoding="utf-8",
    )
    sec_res = generate_dashboard.analyze_compliance(str(sec_doc))
    assert sec_res["Schema (JSON Schema 2020-12 / Dynamic Refs / `discriminator.defaultMapping`)"] == "✅ Supported"
    assert sec_res["Media Type (`itemSchema`, `prefixEncoding`, `itemEncoding`)"] == "🚧 Partial"
    assert sec_res["Parameter (`example` / `examples` / `content`)"] == "❌ Missing"
    assert sec_res["Response (`summary`, `headers`, `links`)"] == "🚧 Partial / Mentioned"
    assert sec_res["Tags (`summary`, `parent`, `kind`)"] == "❌ Unmentioned"

    (tmp_path / "cdd-c").mkdir()
    (tmp_path / "cdd-c" / "COMPLIANCE.md").write_text(table_doc.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "cdd-cpp").mkdir()
    (tmp_path / "cdd-cpp" / "COMPLIANCE.md").write_text("# Header Only", encoding="utf-8")

    out_md = tmp_path / "OUT.md"
    assert generate_dashboard.main(root_dir=str(tmp_path), output_file=str(out_md)) == 0
    assert out_md.exists()
    content = out_md.read_text(encoding="utf-8")
    assert "Overview paragraph here." in content


def test_update_all_tables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `update_all_tables.main` handles success and non-zero return codes."""
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0))
    assert update_all_tables.main(root_dir=str(tmp_path)) == 0

    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 2))
    assert update_all_tables.main(root_dir=str(tmp_path)) == 2

    calls = [0]

    def fail_second(cmd: List[str], **kw: object) -> subprocess.CompletedProcess[str]:
        """Pass first subprocess call, fail second."""
        calls[0] += 1
        return subprocess.CompletedProcess(cmd, 0 if calls[0] == 1 else 3)

    monkeypatch.setattr(subprocess, "run", fail_second)
    assert update_all_tables.main(root_dir=str(tmp_path)) == 3


def test_update_readme_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `update_readme_status.run_test` and `main` across all branches."""
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0))
    assert update_readme_status.run_test("cdd-ts", "only-test", root_dir=str(tmp_path)) == "✅ Passed"

    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1))
    assert update_readme_status.run_test("cdd-ts", "", root_dir=str(tmp_path)) == "❌ Failed"

    def raise_timeout(cmd: List[str], **kw: object) -> subprocess.CompletedProcess[str]:
        """Raise TimeoutExpired."""
        raise subprocess.TimeoutExpired(cmd, 300)

    monkeypatch.setattr(subprocess, "run", raise_timeout)
    assert update_readme_status.run_test("cdd-ts") == "❌ Timeout"

    def raise_err(cmd: List[str], **kw: object) -> subprocess.CompletedProcess[str]:
        """Raise OSError."""
        raise OSError("err")

    monkeypatch.setattr(subprocess, "run", raise_err)
    assert update_readme_status.run_test("cdd-ts") == "❌ Error"

    assert update_readme_status.main(root_dir=str(tmp_path)) == 1

    readme = tmp_path / "README.md"
    readme.write_text("# No Table Here", encoding="utf-8")
    assert update_readme_status.main(root_dir=str(tmp_path)) == 1

    nl = chr(10)
    table_lines = [
        "# Title",
        "| Repository | Target Language | Role | Test Status | Roundtrip Status |",
        "|---|---|---|---|---|",
        "| `cdd-ts` | TypeScript | Client | ❌ Failed | ❌ Failed |",
        "| short | row |",
        "",
        "Footer",
    ]
    readme.write_text(nl.join(table_lines) + nl, encoding="utf-8")

    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0))
    monkeypatch.setattr(
        update_readme_status,
        "run_test",
        lambda repo, mode="", root_dir=None: "❌ Failed" if mode == "" else "✅ Passed",
    )
    assert update_readme_status.main(root_dir=str(tmp_path)) == 0
    assert "✅ Passed (WASM ❌)" in readme.read_text(encoding="utf-8")

    assert update_readme_status.main(root_dir=str(tmp_path)) == 0

    readme_eof = nl.join(table_lines[:4]) + nl
    readme.write_text(readme_eof, encoding="utf-8")
    monkeypatch.setattr(update_readme_status, "run_test", lambda repo, mode="", root_dir=None: "✅ Passed")
    assert update_readme_status.main(root_dir=str(tmp_path)) == 0

    monkeypatch.setattr(update_readme_status, "run_test", lambda repo, mode="", root_dir=None: "❌ Failed")
    assert update_readme_status.main(root_dir=str(tmp_path)) == 0


def test_update_testing_coverage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `update_testing_coverage` helper functions and `main` across all branches."""
    assert update_testing_coverage._determine_native_status(str(tmp_path), "cdd-ts") == "❌ No"
    (tmp_path / "cdd-ts").mkdir()
    assert update_testing_coverage._determine_native_status(str(tmp_path), "cdd-ts") == "✅ Yes"
    (tmp_path / "unknown-repo").mkdir()
    assert update_testing_coverage._determine_native_status(str(tmp_path), "unknown-repo") == "❌ No"

    assert update_testing_coverage._determine_wasm_status(str(tmp_path), "cdd-ts") == "❌ No"
    (tmp_path / "cdd-ts" / "WASM.md").write_text("WASM is not supported here.", encoding="utf-8")
    assert update_testing_coverage._determine_wasm_status(str(tmp_path), "cdd-ts") == "❌ No"

    (tmp_path / "cdd-ts" / "WASM.md").write_text("Nothing mentioned.", encoding="utf-8")
    assert update_testing_coverage._determine_wasm_status(str(tmp_path), "cdd-ts") == "❌ No"

    (tmp_path / "cdd-ts" / "WASM.md").write_text("Supported via wasm target.", encoding="utf-8")
    assert update_testing_coverage._determine_wasm_status(str(tmp_path), "cdd-ts") == "✅ Yes"

    (tmp_path / "unknown-repo" / "WASM.md").write_text("Supported via wasm.", encoding="utf-8")
    assert update_testing_coverage._determine_wasm_status(str(tmp_path), "unknown-repo") == "✅ Yes"

    assert update_testing_coverage.main(root_dir=str(tmp_path)) == 1

    readme = tmp_path / "README.md"
    readme.write_text("# No Coverage Table", encoding="utf-8")
    assert update_testing_coverage.main(root_dir=str(tmp_path)) == 1

    nl = chr(10)
    cov_lines = [
        "# Coverage",
        "| Repository | Native Build/Tests | WASM Build/Tests |",
        "|---|---|---|",
        "| `cdd-ts` | ❌ No | ❌ No |",
        "| short |",
        "",
        "End",
    ]
    readme.write_text(nl.join(cov_lines) + nl, encoding="utf-8")
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0))
    assert update_testing_coverage.main(root_dir=str(tmp_path)) == 0
    assert "| `cdd-ts` | ✅ Yes | ✅ Yes |" in readme.read_text(encoding="utf-8")

    assert update_testing_coverage.main(root_dir=str(tmp_path)) == 0

    readme.write_text(nl.join(cov_lines[:4]) + nl, encoding="utf-8")
    assert update_testing_coverage.main(root_dir=str(tmp_path)) == 0
