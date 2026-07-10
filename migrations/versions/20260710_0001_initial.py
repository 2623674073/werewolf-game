"""Create game and event tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260710_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "games",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("player_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("phase", sa.String(length=20), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("players", sa.JSON(), nullable=False),
        sa.Column("winner", sa.String(length=32), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_games_status", "games", ["status"])
    op.create_table(
        "game_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("game_id", sa.String(length=36), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("phase", sa.String(length=20), nullable=False),
        sa.Column("visibility", sa.String(length=20), nullable=False),
        sa.Column("recipients", sa.JSON(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("game_id", "seq"),
    )
    op.create_index("ix_game_events_game_id", "game_events", ["game_id"])
    op.create_index("ix_game_events_type", "game_events", ["type"])
    op.create_index("ix_game_events_visibility", "game_events", ["visibility"])


def downgrade() -> None:
    op.drop_index("ix_game_events_visibility", table_name="game_events")
    op.drop_index("ix_game_events_type", table_name="game_events")
    op.drop_index("ix_game_events_game_id", table_name="game_events")
    op.drop_table("game_events")
    op.drop_index("ix_games_status", table_name="games")
    op.drop_table("games")
