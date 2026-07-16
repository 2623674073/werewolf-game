"""Cascade game deletion to persisted events."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260716_0003"
down_revision: str | None = "20260716_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "DELETE FROM game_events "
        "WHERE NOT EXISTS (SELECT 1 FROM games WHERE games.id = game_events.game_id)"
    )
    with op.batch_alter_table("game_events", recreate="always") as batch_op:
        batch_op.create_foreign_key(
            "fk_game_events_game_id_games",
            "games",
            ["game_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    with op.batch_alter_table("game_events", recreate="always") as batch_op:
        batch_op.drop_constraint(
            "fk_game_events_game_id_games",
            type_="foreignkey",
        )
