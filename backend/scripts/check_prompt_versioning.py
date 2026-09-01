#!/usr/bin/env python3
"""Fails if engine source has an unversioned LLM prompt, or a versioned
prompt whose content changed with no matching version bump (spec 014,
FR-001/FR-002/FR-003/FR-008).

Detects at the actual usage site -- an `LlmAgent(instruction=...)` call
-- rather than a naming convention, mirroring
`check_no_subject_conditionals.py`'s "check where it's used, not how
it's declared" philosophy:

1. `find_violations`: an `instruction=` argument that is a bare string/
   f-string literal is a violation (FR-001 -- nothing "discoverable and
   versioned" was ever built for it). An `instruction=` argument that
   *references* something (a `Name` or a `Name`-rooted `Call`, e.g.
   `build_instruction(...)`) is fine at the call site, but the file
   containing that call must then define at least one module-level
   constant whose name contains "VERSION" (FR-002) -- this is a
   file-level check, not full data-flow tracing back through helper
   functions, matching this project's existing real prompts: every one
   of them keeps its content and its version constant in the same file
   as the `LlmAgent(...)` call, even where (Grading Agent) the prompt
   *template* itself lives in a separate module.
2. `find_version_bump_violations`: a prompt's content (any module-level
   assignment whose target name contains "INSTRUCTION") changed between
   two source versions of a file, but no assignment whose target name
   contains "VERSION" also changed -- pure text-of-AST-node comparison,
   no git dependency, so a diff touching the file for unrelated reasons
   (a comment fix elsewhere) never requires a version bump.

Usage: python scripts/check_prompt_versioning.py <src_dir> [--base-ref REF]
Exit code 0 = no violations; 1 = violations found.
"""

import argparse
import ast
import subprocess
import sys
from pathlib import Path


def _iter_py_files(src_dir: Path):
    for py_file in sorted(src_dir.rglob("*.py")):
        if "__pycache__" in py_file.parts:
            continue
        yield py_file


def _is_llm_agent_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == "LlmAgent"
    if isinstance(func, ast.Attribute):
        return func.attr == "LlmAgent"
    return False


def _get_kwarg(call: ast.Call, name: str) -> ast.expr | None:
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _is_bare_literal(node: ast.expr) -> bool:
    return isinstance(node, (ast.Constant, ast.JoinedStr))


def _module_level_names_containing(tree: ast.Module, substring: str) -> list[ast.Assign]:
    matches = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and substring in target.id.upper():
                    matches.append(node)
    return matches


def find_violations(src_dir: Path) -> list[str]:
    violations = []
    for py_file in _iter_py_files(src_dir):
        source = py_file.read_text()
        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue

        has_llm_agent_call = False
        literal_violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _is_llm_agent_call(node):
                has_llm_agent_call = True
                instruction_arg = _get_kwarg(node, "instruction")
                if instruction_arg is not None and _is_bare_literal(instruction_arg):
                    literal_violations.append(
                        f"{py_file}:{instruction_arg.lineno}: LlmAgent instruction is a "
                        "bare inline string literal, not a versioned artifact (FR-001)"
                    )

        if literal_violations:
            violations.extend(literal_violations)
        elif has_llm_agent_call and not _module_level_names_containing(tree, "VERSION"):
            violations.append(
                f"{py_file}: defines an LlmAgent instruction with no paired "
                "*VERSION* constant anywhere in this file (FR-002)"
            )
    return violations


def _source_segment(source: str, node: ast.AST) -> str:
    return ast.get_source_segment(source, node) or ""


def find_version_bump_violations(
    old_source: str, new_source: str, *, filename: str = "<file>"
) -> list[str]:
    try:
        old_tree = ast.parse(old_source)
    except SyntaxError:
        old_tree = None
    new_tree = ast.parse(new_source)

    new_instruction_nodes = _module_level_names_containing(new_tree, "INSTRUCTION")
    if not new_instruction_nodes:
        return []

    old_instruction_text = (
        "".join(
            _source_segment(old_source, n)
            for n in _module_level_names_containing(old_tree, "INSTRUCTION")
        )
        if old_tree is not None
        else ""
    )
    new_instruction_text = "".join(_source_segment(new_source, n) for n in new_instruction_nodes)

    if old_instruction_text == new_instruction_text:
        return []

    old_version_text = (
        "".join(
            _source_segment(old_source, n)
            for n in _module_level_names_containing(old_tree, "VERSION")
        )
        if old_tree is not None
        else ""
    )
    new_version_text = "".join(
        _source_segment(new_source, n) for n in _module_level_names_containing(new_tree, "VERSION")
    )

    if old_version_text == new_version_text:
        return [
            f"{filename}: prompt content changed but its paired VERSION constant "
            "did not (FR-008)"
        ]
    return []


def _git_show(base_ref: str, path: Path) -> str:
    result = subprocess.run(
        ["git", "show", f"{base_ref}:{path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("src_dir", type=Path)
    parser.add_argument(
        "--base-ref", default=None, help="Git ref to diff against for version-bump enforcement."
    )
    args = parser.parse_args()

    violations = find_violations(args.src_dir)

    if args.base_ref:
        for py_file in _iter_py_files(args.src_dir):
            old_source = _git_show(args.base_ref, py_file)
            if not old_source:
                continue  # new file -- nothing to bump-check against
            violations.extend(
                find_version_bump_violations(
                    old_source, py_file.read_text(), filename=str(py_file)
                )
            )

    if violations:
        print("PROMPT VERSIONING VIOLATION(S):")
        for violation in violations:
            print(f"  {violation}")
        return 1

    print(f"OK: no prompt-versioning violations found in {args.src_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
