"""free text question type

Revision ID: 407938ba90fc
Revises: a7b77bd7fea5
Create Date: 2026-08-19 06:09:17.567474

Adds `free_text` to `question_type` and `free_text_submission_rejected`
to `assessment_event_type` for spec 007 (Free-Text Grading via a Real
A2A Service) -- see FR-001, FR-012, and data-model.md's §9. No new
tables: the free-text rubric reuses `generated_questions.answer_key`
(already a type-agnostic JSON column), and both new Grading Decision
and Moderation Flag concepts map onto the existing `assessment_events`
stream with richer payloads.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "407938ba90fc"
down_revision: str | Sequence[str] | None = "a7b77bd7fea5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # ALTER TYPE ... ADD VALUE cannot run inside the same transaction
    # that later reads/writes that value, but adding the label itself is
    # safe inside Alembic's default transaction on Postgres 12+ -- same
    # technique as 533736af33d7_recommendation_event_types.py.
    op.execute("ALTER TYPE question_type ADD VALUE IF NOT EXISTS 'free_text'")
    op.execute(
        "ALTER TYPE assessment_event_type ADD VALUE IF NOT EXISTS "
        "'free_text_submission_rejected'"
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Postgres has no DROP VALUE for enum labels; removing them safely
    # requires rebuilding the type (new type, migrate column, drop old
    # type). Not done here -- the two new labels are left in place on
    # downgrade, matching this project's existing precedent.
