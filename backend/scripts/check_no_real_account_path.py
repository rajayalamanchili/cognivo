#!/usr/bin/env python3
"""Fails if any model represents a real (non-demo) account without
`is_demo` (Constitution Principle VIII gate, spec 009 FR-001/FR-008).

Structural check, not a text grep (unlike check_no_subject_conditionals.py,
where the forbidden pattern is a literal string): parses every model
module with `ast`, finds every class inheriting from the project's
declarative `Base`, and fails if any such class's `__tablename__`
suggests a real-account concept (learner, student, instructor, teacher,
guardian, parent, account, user) but the class has no `is_demo` column
that is provably non-nullable.

Non-nullability is recognized from either an explicit `nullable=False`
keyword in a `mapped_column(...)` call, or a bare `Mapped[bool]`
annotation with no `Optional`/`| None` wrapper (SQLAlchemy 2.0's own
type-inferred non-nullability, e.g. `DemoLearnerProfile.is_demo`'s
style) -- checking only the explicit keyword would false-positive on a
model correctly relying on type inference (spec 009 /speckit-analyze
finding F4). An explicit `nullable=True` (or any non-literal `nullable=`
value we can't statically prove `False`) is treated as nullable --
fails closed, matching this project's existing gate scripts' design.

Usage: python scripts/check_no_real_account_path.py
Exit code 0 = no violations found; 1 = violations found or setup error.
"""

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = REPO_ROOT / "backend" / "src" / "models"

# Substring match, case-insensitive -- deliberately broad (a false
# positive here is cheap to fix by adding is_demo; a false negative lets
# a real-account-shaped table slip through unflagged).
_ACCOUNT_LIKE_PATTERNS = (
    "learner",
    "student",
    "instructor",
    "teacher",
    "guardian",
    "parent",
    "account",
    "user",
)


def _is_base_subclass(class_def: ast.ClassDef) -> bool:
    return any(isinstance(base, ast.Name) and base.id == "Base" for base in class_def.bases)


def _table_name(class_def: ast.ClassDef) -> str | None:
    for node in class_def.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "__tablename__"
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            return node.value.value
    return None


def _matches_account_like_pattern(table_name: str) -> bool:
    lowered = table_name.lower()
    return any(pattern in lowered for pattern in _ACCOUNT_LIKE_PATTERNS)


def _annotation_allows_null(annotation: ast.expr) -> bool:
    """True if a bare `Mapped[...]` annotation itself permits NULL
    (i.e. is `Optional[X]`/`X | None`) -- False for a plain `Mapped[X]`,
    which SQLAlchemy 2.0 infers as NOT NULL absent an explicit override.
    """
    if not (isinstance(annotation, ast.Subscript) and isinstance(annotation.value, ast.Name)):
        return True  # Not a recognizable Mapped[...] shape -- fail closed (treat as nullable).
    if annotation.value.id != "Mapped":
        return True
    inner = annotation.slice
    if isinstance(inner, ast.BinOp) and isinstance(inner.op, ast.BitOr):
        return True  # `X | None` (either operand order)
    if isinstance(inner, ast.Subscript) and isinstance(inner.value, ast.Name) and inner.value.id == "Optional":
        return True
    return False


def _explicit_nullable_keyword(call: ast.Call) -> bool | None:
    """The literal value of an explicit `nullable=` keyword in a
    `mapped_column(...)` call, or None if absent or not a literal we
    can statically trust."""
    for keyword in call.keywords:
        if keyword.arg == "nullable":
            if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, bool):
                return keyword.value.value
            return False  # non-literal nullable= value -- fail closed, can't prove False
    return None


def _is_demo_column_non_nullable(class_def: ast.ClassDef) -> bool:
    # Only recognizes SQLAlchemy 2.0's annotated-attribute style
    # (`is_demo: Mapped[bool] = mapped_column(...)`, an ast.AnnAssign) --
    # every model in this codebase already uses this style. A legacy
    # `is_demo = Column(...)` (ast.Assign, no annotation) would be
    # invisible here and reported as "no is_demo column at all", which
    # fails in the safe direction (a false violation, not a false
    # negative) rather than silently letting a real gap through.
    for node in class_def.body:
        if not (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "is_demo"
        ):
            continue
        explicit = (
            _explicit_nullable_keyword(node.value)
            if isinstance(node.value, ast.Call)
            else None
        )
        if explicit is not None:
            return not explicit
        return not _annotation_allows_null(node.annotation)
    return False  # no is_demo column at all


def find_violations(models_dir: Path = MODELS_DIR) -> list[str]:
    violations = []
    for py_file in sorted(models_dir.rglob("*.py")):
        if "__pycache__" in py_file.parts:
            continue
        tree = ast.parse(py_file.read_text(), filename=str(py_file))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or not _is_base_subclass(node):
                continue
            table_name = _table_name(node)
            if not table_name or not _matches_account_like_pattern(table_name):
                continue
            if not _is_demo_column_non_nullable(node):
                display_path = py_file.relative_to(REPO_ROOT) if py_file.is_relative_to(REPO_ROOT) else py_file
                violations.append(
                    f"{display_path}: class {node.name!r} "
                    f"(table {table_name!r}) has no non-nullable is_demo column"
                )
    return violations


def main() -> int:
    violations = find_violations()
    if violations:
        print(
            "Constitution Principle VIII VIOLATION: an account-shaped model "
            "has no non-nullable is_demo column:"
        )
        for violation in violations:
            print(f"  {violation}")
        return 1

    print("OK: every account-shaped model under backend/src/models/ carries a non-nullable is_demo column")
    return 0


if __name__ == "__main__":
    sys.exit(main())
