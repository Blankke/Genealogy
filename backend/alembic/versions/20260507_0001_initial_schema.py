"""初始化族谱管理系统数据库结构

Revision ID: 20260507_0001
Revises:
Create Date: 2026-05-07
"""

from pathlib import Path

from alembic import op

revision = "20260507_0001"
down_revision = None
branch_labels = None
depends_on = None


def _read_sql(relative_path: str) -> str:
    repo_root = Path(__file__).resolve().parents[3]
    return (repo_root / relative_path).read_text(encoding="utf-8")


def upgrade() -> None:
    op.execute(_read_sql("database/schema.sql"))
    op.execute(_read_sql("database/indexes.sql"))


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS marriages CASCADE")
    op.execute("DROP TABLE IF EXISTS parent_child_relations CASCADE")
    op.execute("DROP TABLE IF EXISTS members CASCADE")
    op.execute("DROP TABLE IF EXISTS genealogy_collaborators CASCADE")
    op.execute("DROP TABLE IF EXISTS genealogies CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
    op.execute("DROP FUNCTION IF EXISTS validate_parent_child_relation() CASCADE")
    op.execute("DROP FUNCTION IF EXISTS validate_marriage_relation() CASCADE")
