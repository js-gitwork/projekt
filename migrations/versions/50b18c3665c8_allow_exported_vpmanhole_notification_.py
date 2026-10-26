"""Allow exported VPManhole notification status.

Revision ID: 50b18c3665c8
Revises: a63ce1c44c23
"""

from typing import Sequence, Union

from alembic import op


revision: str = "50b18c3665c8"
down_revision: Union[str, None] = "a63ce1c44c23"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_vpmanhole_notification_event_status",
        "vpmanhole_notification_events",
        type_="check",
    )

    op.create_check_constraint(
        "ck_vpmanhole_notification_event_status",
        "vpmanhole_notification_events",
        "status IN ('pending', 'sending', 'sent', 'failed', 'exported')",
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE vpmanhole_notification_events
        SET status = 'pending'
        WHERE status = 'exported'
        """
    )

    op.drop_constraint(
        "ck_vpmanhole_notification_event_status",
        "vpmanhole_notification_events",
        type_="check",
    )

    op.create_check_constraint(
        "ck_vpmanhole_notification_event_status",
        "vpmanhole_notification_events",
        "status IN ('pending', 'sending', 'sent', 'failed')",
    )
