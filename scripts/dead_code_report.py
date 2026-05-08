#!/usr/bin/env python3
"""Generate a dead/stale code report using layered static and runtime signals.

The report combines:
- Python static analysis (vulture + pyflakes)
- Frontend static analysis (eslint unused-variable rules)
- Runtime coverage hotspots (backend + frontend coverage files when available)
- Lightweight local dependency graph orphan detection (Python + frontend source)

This script is advisory by default and exits 0 unless a fatal tooling error occurs.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"
ETL_DIR = ROOT / "etl"
SCRIPTS_DIR = ROOT / "scripts"
FRONTEND_DIR = ROOT / "frontend"
FRONTEND_SRC = FRONTEND_DIR / "src"
FRONTEND_TESTS = FRONTEND_DIR / "tests"

DEFAULT_JS_ALIAS_PREFIXES = {
    "@": FRONTEND_SRC,
    "@components": FRONTEND_SRC / "components",
    "@api": FRONTEND_SRC / "api",
    "@context": FRONTEND_SRC / "context",
    "@hooks": FRONTEND_SRC / "hooks",
    "@utils": FRONTEND_SRC / "utils",
}

NON_SOURCE_IMPORT_SUFFIXES = (
    ".css",
    ".scss",
    ".sass",
    ".less",
    ".svg",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".json",
)

PY_EXCLUDE_FRAGMENTS = (
    "__pycache__",
    ".venv",
    "backend/alembic",
    "db/migrations",
    "backend/tests",
    "etl/test",
)

JS_IMPORT_RE = re.compile(
    r"(?:"
    r"import\s+(?:[\s\S]*?\s+from\s+)?"
    r"|import\s*\("
    r"|export\s+(?:[\s\S]*?\s+from\s+)"
    r")\s*['\"]([^'\"\n]+)['\"]",
    re.MULTILINE,
)


def _load_js_alias_prefixes() -> dict[str, Path]:
    alias_map: dict[str, Path] = dict(DEFAULT_JS_ALIAS_PREFIXES)
    for config_name in ("tsconfig.typecheck.json", "tsconfig.json"):
        config_path = FRONTEND_DIR / config_name
        if not config_path.exists():
            continue
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        compiler_options = payload.get("compilerOptions", {})
        if not isinstance(compiler_options, dict):
            continue

        paths = compiler_options.get("paths", {})
        if not isinstance(paths, dict):
            continue

        base_url = compiler_options.get("baseUrl", ".")
        base_dir = (FRONTEND_DIR / str(base_url)).resolve()

        for alias_pattern, targets in paths.items():
            if not isinstance(alias_pattern, str) or not isinstance(targets, list) or not targets:
                continue
            first_target = targets[0]
            if not isinstance(first_target, str):
                continue

            alias = alias_pattern.rstrip("/*")
            target = first_target.rstrip("/*")
            if not alias:
                continue
            alias_map[alias] = (base_dir / target).resolve()

    return alias_map


JS_ALIAS_PREFIXES = _load_js_alias_prefixes()


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


def _run_command(cmd: list[str], cwd: Path | None = None) -> CommandResult:
    proc = subprocess.run(
        cmd,
        cwd=cwd or ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return CommandResult(
        returncode=proc.returncode,
        stdout=(proc.stdout or "").strip(),
        stderr=(proc.stderr or "").strip(),
    )


def _is_py_target(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    if not rel.endswith(".py"):
        return False
    return not any(fragment in rel for fragment in PY_EXCLUDE_FRAGMENTS)


def _find_python_files() -> list[Path]:
    roots = [BACKEND_DIR, ETL_DIR, SCRIPTS_DIR]
    files: list[Path] = []
    for base in roots:
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if _is_py_target(path):
                files.append(path)
    return sorted(files)


def _find_js_files() -> list[Path]:
    if not FRONTEND_SRC.exists():
        return []
    files: list[Path] = []
    for ext in ("*.js", "*.jsx", "*.ts", "*.tsx"):
        files.extend(FRONTEND_SRC.rglob(ext))
    return sorted(set(files))


def run_vulture() -> dict:
    targets = [str(BACKEND_DIR), str(ETL_DIR), str(SCRIPTS_DIR)]
    cmd = [
        sys.executable,
        "-m",
        "vulture",
        *targets,
        "--min-confidence",
        "80",
        "--exclude",
        "backend/alembic/*.py,backend/tests/*.py,etl/test*.py,db/migrations/*.py",
    ]
    result = _run_command(cmd)

    findings = [line for line in result.stdout.splitlines() if line.strip()]
    error_text = result.stderr.strip()

    # vulture returns 3 when items are found; treat as expected for reporting.
    if result.returncode in (0, 3):
        return {
            "status": "ok",
            "returncode": result.returncode,
            "findings": findings,
            "errors": [],
        }

    return {
        "status": "error",
        "returncode": result.returncode,
        "findings": findings,
        "errors": [error_text] if error_text else ["vulture failed"],
    }


def run_pyflakes(py_files: list[Path]) -> dict:
    if not py_files:
        return {"status": "ok", "returncode": 0, "findings": [], "errors": []}

    cmd = [sys.executable, "-m", "pyflakes", *[str(path) for path in py_files]]
    result = _run_command(cmd)

    findings = [line for line in (result.stdout + "\n" + result.stderr).splitlines() if line.strip()]

    # pyflakes exits non-zero when findings exist.
    if result.returncode in (0, 1):
        return {
            "status": "ok",
            "returncode": result.returncode,
            "findings": findings,
            "errors": [],
        }

    return {
        "status": "error",
        "returncode": result.returncode,
        "findings": findings,
        "errors": ["pyflakes execution error"],
    }


def run_eslint_unused() -> dict:
    if not FRONTEND_SRC.exists():
        return {"status": "ok", "returncode": 0, "findings": [], "errors": []}

    cmd = [
        "npx",
        "eslint",
        "src",
        "--ext",
        ".js,.jsx,.ts,.tsx",
        "--format",
        "json",
    ]
    result = _run_command(cmd, cwd=FRONTEND_DIR)

    combined_output = result.stdout.strip() or result.stderr.strip()
    if not combined_output:
        return {"status": "ok", "returncode": result.returncode, "findings": [], "errors": []}

    try:
        parsed = json.loads(combined_output)
    except json.JSONDecodeError:
        # eslint can emit plain text if execution fails before formatter setup.
        return {
            "status": "error",
            "returncode": result.returncode,
            "findings": [],
            "errors": [combined_output],
        }

    findings: list[str] = []
    for file_report in parsed:
        file_path = file_report.get("filePath", "")
        rel_file = _to_rel(file_path)
        for message in file_report.get("messages", []):
            rule_id = (message.get("ruleId") or "").strip()
            if rule_id not in {"no-unused-vars", "no-unused-private-class-members"}:
                continue
            line = message.get("line", 0)
            text = message.get("message", "unused code signal")
            findings.append(f"{rel_file}:{line}: {rule_id}: {text}")

    if result.returncode in (0, 1):
        return {
            "status": "ok",
            "returncode": result.returncode,
            "findings": findings,
            "errors": [],
        }

    return {
        "status": "error",
        "returncode": result.returncode,
        "findings": findings,
        "errors": [combined_output],
    }


def _to_rel(path: str) -> str:
    p = Path(path)
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except Exception:
        return p.as_posix()


def parse_backend_coverage(coverage_xml: Path | None) -> dict:
    if not coverage_xml or not coverage_xml.exists():
        return {"status": "missing", "zero_coverage_files": []}

    try:
        root = ET.parse(coverage_xml).getroot()
    except (ET.ParseError, OSError) as exc:
        return {
            "status": "error",
            "zero_coverage_files": [],
            "errors": [f"Failed to parse backend coverage XML: {exc}"],
        }

    zero_files: list[str] = []

    for class_node in root.findall(".//class"):
        filename = class_node.attrib.get("filename", "")
        line_rate = class_node.attrib.get("line-rate", "0")
        try:
            rate = float(line_rate)
        except ValueError:
            rate = 0.0
        if rate == 0.0 and filename:
            zero_files.append(filename)

    return {
        "status": "ok",
        "zero_coverage_files": sorted(set(zero_files)),
    }


def parse_frontend_coverage(coverage_json: Path | None) -> dict:
    if not coverage_json or not coverage_json.exists():
        return {"status": "missing", "zero_coverage_files": []}

    try:
        payload = json.loads(coverage_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "status": "error",
            "zero_coverage_files": [],
            "errors": [f"Failed to parse frontend coverage JSON: {exc}"],
        }

    zero_files: list[str] = []

    for path, file_data in payload.items():
        statements = file_data.get("s", {})
        if not statements:
            continue
        total_hits = sum(int(value) for value in statements.values())
        if total_hits == 0:
            zero_files.append(_to_rel(path))

    return {
        "status": "ok",
        "zero_coverage_files": sorted(set(zero_files)),
    }


def _module_name_for_python(path: Path) -> str:
    rel = path.relative_to(ROOT).with_suffix("")
    return ".".join(rel.parts)


def build_python_dependency_graph(py_files: list[Path]) -> dict:
    module_to_file = {_module_name_for_python(path): path for path in py_files}
    inbound = {module: 0 for module in module_to_file}

    for source_path in py_files:
        module_name = _module_name_for_python(source_path)
        try:
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue

        edges: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target = alias.name
                    edges.update(_resolve_python_import(target, module_to_file))
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level > 0:
                    base = _resolve_relative_module(module_name, base, node.level)
                if base:
                    edges.update(_resolve_python_import(base, module_to_file))

        for target in edges:
            inbound[target] = inbound.get(target, 0) + 1

    entrypoint_prefixes = {
        "backend.main",
        "backend.manage",
        "backend.scripts",
        "scripts.",
        "etl.",
        "backend.tests.",
    }

    orphan_candidates = []
    for module, count in sorted(inbound.items()):
        if count != 0:
            continue
        if module.endswith(".__init__"):
            continue
        if any(module == prefix or module.startswith(prefix) for prefix in entrypoint_prefixes):
            continue
        if ".tests." in module:
            continue
        if not module.startswith(("backend.", "etl.", "scripts.")):
            continue
        orphan_candidates.append(module_to_file[module].relative_to(ROOT).as_posix())

    return {
        "status": "ok",
        "orphan_modules": orphan_candidates,
    }


def _resolve_relative_module(current_module: str, base_module: str, level: int) -> str:
    parts = current_module.split(".")
    if len(parts) < level:
        return base_module
    prefix = parts[:-level]
    if base_module:
        return ".".join(prefix + base_module.split("."))
    return ".".join(prefix)


def _resolve_python_import(import_name: str, known_modules: dict[str, Path]) -> set[str]:
    matches = set()
    if import_name in known_modules:
        matches.add(import_name)

    prefix = import_name + "."
    for module in known_modules:
        if module.startswith(prefix):
            matches.add(module)

    return matches


def _module_name_for_js(path: Path) -> str:
    return path.relative_to(FRONTEND_SRC).with_suffix("").as_posix()


def _find_js_reference_files(js_files: list[Path]) -> list[Path]:
    # Source files plus test files can legitimately reference modules.
    references = set(js_files)
    if FRONTEND_TESTS.exists():
        for ext in ("*.js", "*.jsx", "*.ts", "*.tsx"):
            references.update(FRONTEND_TESTS.rglob(ext))
    return sorted(references)


def build_js_dependency_graph(js_files: list[Path]) -> dict:
    module_to_file = {_module_name_for_js(path): path for path in js_files}
    inbound = {module: 0 for module in module_to_file}
    reference_files = _find_js_reference_files(js_files)

    for source_path in reference_files:
        text = source_path.read_text(encoding="utf-8")
        imports = JS_IMPORT_RE.findall(text)

        targets: set[str] = set()
        for raw in imports:
            resolved = _resolve_js_import(source_path, raw, module_to_file)
            if resolved:
                targets.add(resolved)

        for target in targets:
            inbound[target] = inbound.get(target, 0) + 1

    orphan_candidates = []
    for module, count in sorted(inbound.items()):
        if count != 0:
            continue
        if module.startswith("pages/"):
            continue
        if module.endswith("/index"):
            continue
        if module in {"main", "App"}:
            continue
        orphan_candidates.append(module_to_file[module].relative_to(ROOT).as_posix())

    return {
        "status": "ok",
        "orphan_modules": orphan_candidates,
    }


def _resolve_js_import(source_path: Path, raw_import: str, known_modules: dict[str, Path]) -> str | None:
    if raw_import.endswith(NON_SOURCE_IMPORT_SUFFIXES):
        return None

    if raw_import.startswith("."):
        base = (source_path.parent / raw_import).resolve()
        return _resolve_js_candidate_base(base, known_modules)

    alias_resolved = _resolve_alias_import(raw_import)
    if alias_resolved is not None:
        return _resolve_js_candidate_base(alias_resolved, known_modules)

    return None


def _resolve_alias_import(raw_import: str) -> Path | None:
    for alias, alias_path in JS_ALIAS_PREFIXES.items():
        if raw_import == alias:
            return alias_path
        if raw_import.startswith(alias + "/"):
            return alias_path / raw_import[len(alias) + 1 :]

    return None


def _resolve_js_candidate_base(base: Path, known_modules: dict[str, Path]) -> str | None:
    candidates = [base]

    for ext in (".js", ".jsx", ".ts", ".tsx"):
        candidates.append(Path(str(base) + ext))

    for ext in (".js", ".jsx", ".ts", ".tsx"):
        candidates.append(base / f"index{ext}")

    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            rel = candidate.relative_to(FRONTEND_SRC).with_suffix("").as_posix()
            if rel in known_modules:
                return rel
        except ValueError:
            continue

    return None


def summarize_report(report: dict) -> str:
    static_signals = report["static_analysis"]
    coverage = report["coverage"]
    graph = report["dependency_graph"]

    lines = [
        "# Dead/Stale Code Report",
        "",
        "This report is advisory. Findings require manual validation before removal.",
        "",
        "## Static Analysis",
        f"- Vulture findings: {len(static_signals['python_vulture']['findings'])}",
        f"- Pyflakes findings: {len(static_signals['python_pyflakes']['findings'])}",
        f"- ESLint unused findings: {len(static_signals['frontend_unused']['findings'])}",
        "",
        "## Coverage Hotspots",
        f"- Backend files with zero coverage: {len(coverage['backend']['zero_coverage_files'])}",
        f"- Frontend files with zero coverage: {len(coverage['frontend']['zero_coverage_files'])}",
        "",
        "## Orphan Candidates (Dependency Graph)",
        f"- Python orphan module candidates: {len(graph['python']['orphan_modules'])}",
        f"- Frontend orphan module candidates: {len(graph['frontend']['orphan_modules'])}",
        "",
        "## Top Candidate Files",
    ]

    top_candidates = []
    top_candidates.extend(coverage["backend"]["zero_coverage_files"][:10])
    top_candidates.extend(coverage["frontend"]["zero_coverage_files"][:10])
    top_candidates.extend(graph["python"]["orphan_modules"][:10])
    top_candidates.extend(graph["frontend"]["orphan_modules"][:10])

    if top_candidates:
        for item in top_candidates[:20]:
            lines.append(f"- {item}")
    else:
        lines.append("- No high-confidence candidates found.")

    lines.extend(
        [
            "",
            "## Safe Prune Reminder",
            "- Confirm no dynamic imports, reflection, or router registration paths depend on the candidate.",
            "- Confirm Docker/systemd/Nginx/runtime scripts do not reference the candidate.",
            "- Remove in small PRs with targeted regression tests.",
        ]
    )

    return "\n".join(lines) + "\n"


def _resolve_optional_path(path_str: str | None) -> Path | None:
    if not path_str:
        return None
    path = Path(path_str)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    return path


def _write_output(path: Path | None, text: str) -> None:
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate dead/stale code detection report")
    parser.add_argument("--backend-coverage", help="Path to backend coverage XML")
    parser.add_argument("--frontend-coverage", help="Path to frontend coverage-final.json")
    parser.add_argument("--output-json", help="Where to write JSON report")
    parser.add_argument("--output-md", help="Where to write Markdown report")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str]) -> int:
    args = parse_args(argv)

    py_files = _find_python_files()
    js_files = _find_js_files()

    backend_cov = _resolve_optional_path(args.backend_coverage)
    frontend_cov = _resolve_optional_path(args.frontend_coverage)

    report = {
        "meta": {
            "repo_root": ROOT.as_posix(),
            "python_files_analyzed": len(py_files),
            "frontend_files_analyzed": len(js_files),
        },
        "static_analysis": {
            "python_vulture": run_vulture(),
            "python_pyflakes": run_pyflakes(py_files),
            "frontend_unused": run_eslint_unused(),
        },
        "coverage": {
            "backend": parse_backend_coverage(backend_cov),
            "frontend": parse_frontend_coverage(frontend_cov),
        },
        "dependency_graph": {
            "python": build_python_dependency_graph(py_files),
            "frontend": build_js_dependency_graph(js_files),
        },
    }

    markdown = summarize_report(report)
    serialized = json.dumps(report, indent=2)

    output_json = _resolve_optional_path(args.output_json) if args.output_json else None
    output_md = _resolve_optional_path(args.output_md) if args.output_md else None

    _write_output(output_json, serialized + "\n")
    _write_output(output_md, markdown)

    print(markdown)

    tool_errors = []
    for tool_name, payload in report["static_analysis"].items():
        if payload.get("status") == "error":
            tool_errors.append((tool_name, payload.get("errors") or []))

    if tool_errors:
        print("Tooling errors detected while building report:", file=sys.stderr)
        for tool_name, errors in tool_errors:
            print(f"- {tool_name}: {errors}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
