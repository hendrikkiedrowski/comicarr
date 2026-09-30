#  Copyright (C) 2026 Comicarr contributors
#
#  This file is part of Comicarr.
#
#  Comicarr is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.

"""Record when an issue was last dispatched to search, for the age-scaled
search backoff.

Revision ID: 0010_search_cooldown
Revises: 0009_chat_actions
"""

import sqlalchemy as sa

from alembic import op

revision = "0010_search_cooldown"
down_revision = "0009_chat_actions"
branch_labels = None
depends_on = None

_TABLES = ("issues", "annuals", "storyarcs")


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in _TABLES:
        columns = {column["name"] for column in inspector.get_columns(table)}
        if "LastSearch" not in columns:
            op.add_column(table, sa.Column("LastSearch", sa.Text(), nullable=True))


def downgrade():
    for table in _TABLES:
        op.drop_column(table, "LastSearch")
