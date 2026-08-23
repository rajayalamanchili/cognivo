"""Unit tests for scripts/check_no_real_account_path.py (spec 009
FR-001/FR-008, Constitution Principle VIII's gate).

Wires the check into the regular pytest suite the same way
tests/unit/test_no_subject_conditionals.py already does for
check_no_subject_conditionals.py -- importing the function directly so
it runs as part of the existing `pytest` CI step, no separate workflow
step needed.
"""

from pathlib import Path

from scripts.check_no_real_account_path import find_violations


def test_no_real_account_shaped_model_exists_today():
    """T001: the current backend/src/models/ has zero violations --
    only DemoLearnerProfile matches an account-like table name pattern
    ('demo_learner_profiles' contains 'learner'), and it already
    carries is_demo non-nullable (Milestone 1)."""
    assert find_violations() == []


def test_account_shaped_model_without_is_demo_is_flagged(tmp_path: Path):
    """T002: a synthetic model with an account-like table name and no
    is_demo column is flagged as a violation."""
    (tmp_path / "fixture_violation.py").write_text(
        """
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base import Base


class Student(Base):
    __tablename__ = "students"

    student_id: Mapped[int] = mapped_column(primary_key=True)
"""
    )

    violations = find_violations(models_dir=tmp_path)

    assert len(violations) == 1
    assert "Student" in violations[0]
    assert "students" in violations[0]


def test_account_shaped_model_with_is_demo_passes(tmp_path: Path):
    """T003: the same fixture from T002, now with a non-nullable
    is_demo column, passes -- confirms is_demo presence, not the table
    name alone, is the actual discriminating condition."""
    (tmp_path / "fixture_compliant.py").write_text(
        """
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base import Base


class Student(Base):
    __tablename__ = "students"

    student_id: Mapped[int] = mapped_column(primary_key=True)
    is_demo: Mapped[bool] = mapped_column(nullable=False)
"""
    )

    assert find_violations(models_dir=tmp_path) == []
