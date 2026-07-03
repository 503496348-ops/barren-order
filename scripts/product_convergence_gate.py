#!/usr/bin/env python3
"""Product convergence gate.

Checks whether a product is more than a pile of fused modules: docs, code,
tests, entrypoints, domain mappings and declared smoke paths must agree.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

EXCLUDED_DIRS = {".git", "node_modules", "__pycache__", ".pytest_cache", "venv", ".venv", "dist", "build"}
BRAND_PATTERNS = (
    "融合自", "融合来源", "adapted from", "forked from", "原作者", "合并自",
    "CrewAI", "Dify", "ComfyUI", "outlines", "gpt_academic", "diffusers", "transformers", "obsidian-livesync",
)
BRAND_REGEXES = tuple(re.compile(r"(?<![A-Za-z0-9_])" + re.escape(p) + r"(?![A-Za-z0-9_])", re.I) for p in BRAND_PATTERNS)
CODE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs"}
DOC_SUFFIXES = {".py", ".md", ".yaml", ".yml", ".json", ".toml", ".cfg", ".txt", ".sh"}
CROSSCUT_RE = re.compile(r"(^|[_-])(generic|orchestration|bridge|workflow|control[_-]?plane|runtime)([_-]|$)", re.I)
TEST_PARTS = {"tests", "test", "__pycache__"}


def iter_files(root: Path, suffixes: set[str] | None = None):
    for path in root.rglob("*"):
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if path.is_file() and (suffixes is None or path.suffix in suffixes):
            yield path


def load_manifest(root: Path) -> dict[str, Any]:
    path = root / "product_convergence.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"entrypoints": [], "smoke_targets": [], "known_external_reference_files": [], "domain_mappings": {}}


def rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root))


def first_party_init_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("__init__.py") if not any(part in EXCLUDED_DIRS for part in p.parts)]


def text_contains_reference(path: Path, module_stem: str, file_name: str) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    return module_stem in text or file_name in text


def audit(root: Path) -> dict[str, Any]:
    manifest = load_manifest(root)
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    skill = root / "SKILL.md"
    readme = root / "README.md"
    code_files = list(iter_files(root, CODE_SUFFIXES))
    tests = list((root / "tests").rglob("test_*.py")) if (root / "tests").exists() else []

    if not readme.exists():
        issues.append({"rule": "DOC_001", "message": "README.md missing"})
    if not skill.exists():
        issues.append({"rule": "SKILL_001", "message": "SKILL.md missing"})
    else:
        text = skill.read_text(encoding="utf-8", errors="ignore")
        if not text.startswith("---"):
            issues.append({"rule": "SKILL_002", "message": "SKILL.md frontmatter missing"})
        if "triggers:" not in text:
            issues.append({"rule": "SKILL_003", "message": "SKILL.md triggers missing"})
    if len(code_files) < 1:
        issues.append({"rule": "CODE_001", "message": "no source code files found"})
    if not tests:
        warnings.append({"rule": "TEST_001", "message": "no pytest test files found"})

    entrypoints = list(manifest.get("entrypoints", []) or [])
    smoke_targets = list(manifest.get("smoke_targets", []) or [])
    if not entrypoints:
        issues.append({"rule": "ENTRY_000", "message": "no product entrypoints declared"})
    for p in entrypoints:
        if not (root / p).exists():
            issues.append({"rule": "ENTRY_001", "message": f"declared entrypoint missing: {p}"})
    if not smoke_targets:
        warnings.append({"rule": "SMOKE_002", "message": "no smoke targets declared"})
    for p in smoke_targets:
        if not (root / p).exists():
            issues.append({"rule": "SMOKE_001", "message": f"declared smoke target missing: {p}"})

    allowed = set(manifest.get("known_external_reference_files", []))
    external_hits = []
    for path in iter_files(root, DOC_SUFFIXES):
        if path.name in {"product_convergence_gate.py", "product_convergence.json"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(rx.search(text) for rx in BRAND_REGEXES):
            r = rel(path, root)
            if r not in allowed:
                external_hits.append(r)
    for r in sorted(external_hits)[:50]:
        warnings.append({"rule": "BRAND_001", "message": f"unreviewed external/fusion reference: {r}"})

    mappings = manifest.get("domain_mappings", {}) or {}
    refs = [root / p for p in entrypoints + smoke_targets if (root / p).exists() and (root / p).is_file()]
    refs.extend(first_party_init_files(root))
    mapped_hits = 0
    suspicious = []
    for path in code_files:
        r = rel(path, root)
        if path.name == "product_convergence_gate.py" or any(part in TEST_PARTS for part in path.parts):
            continue
        if CROSSCUT_RE.search(path.stem):
            suspicious.append(r)
            if r not in mappings:
                issues.append({"rule": "DOMAIN_001", "message": f"cross-cutting module lacks domain mapping: {r}"})
                continue
            mapped_hits += 1
            if not text_contains_reference(path, path.stem, path.name) and len(path.read_text(encoding="utf-8", errors="ignore")) < 40:
                issues.append({"rule": "DOMAIN_002", "message": f"mapped module is empty or trivial: {r}"})
            if not any(text_contains_reference(ref, path.stem, path.name) for ref in refs) and r not in smoke_targets and r not in entrypoints:
                issues.append({"rule": "ENTRY_002", "message": f"mapped cross-cutting module is not referenced by entrypoints/smoke/__init__: {r}"})

    doc_text = ""
    for p in (readme, skill):
        if p.exists():
            doc_text += p.read_text(encoding="utf-8", errors="ignore") + "\n"
    if "product_convergence_gate.py" not in doc_text and "产品收敛门禁" not in doc_text:
        warnings.append({"rule": "DOC_002", "message": "convergence gate command not documented"})

    return {
        "repo": root.name,
        "ok": not issues,
        "issues": issues,
        "warnings": warnings,
        "metrics": {
            "code_files": len(code_files),
            "test_files": len(tests),
            "entrypoints": len(entrypoints),
            "smoke_targets": len(smoke_targets),
            "domain_mappings": len(mappings),
            "crosscutting_modules": len(suspicious),
            "mapped_crosscutting_modules": mapped_hits,
            "unreviewed_external_refs": len(external_hits),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run product convergence gate")
    parser.add_argument("--json", action="store_true", help="print JSON")
    args = parser.parse_args()
    result = audit(Path.cwd())
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        status = "PASS" if result["ok"] else "FAIL"
        print(f"{status}: {result['repo']}")
        for issue in result["issues"]:
            print(f"ERROR {issue['rule']}: {issue['message']}")
        for warning in result["warnings"]:
            print(f"WARN {warning['rule']}: {warning['message']}")
        print(json.dumps(result["metrics"], ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
