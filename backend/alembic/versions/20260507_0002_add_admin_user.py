"""新增管理员账号能力

Revision ID: 20260507_0002
Revises: 20260507_0001
Create Date: 2026-05-07
"""

from alembic import op

revision = "20260507_0002"
down_revision = "20260507_0001"
branch_labels = None
depends_on = None

ADMIN_PASSWORD_HASH = "$2b$12$iUVdbQTJEJl4BUGwrfPxXu/7OHvXOTlbpmtrmhTaIPtfwcUfpR81q"


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT false")
    op.execute(
        f"""
        INSERT INTO users (username, email, password_hash, is_admin)
        VALUES ('admin', 'admin@example.com', '{ADMIN_PASSWORD_HASH}', true)
        ON CONFLICT (email)
        DO UPDATE SET is_admin = true, password_hash = EXCLUDED.password_hash
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM users WHERE email = 'admin@example.com'")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS is_admin")
