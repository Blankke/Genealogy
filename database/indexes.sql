-- 族谱管理系统索引脚本。
-- 使用示例：
--   psql -U genealogy_app -d genealogy -f database/indexes.sql

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_members_name_trgm
ON members USING gin (name gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_members_genealogy_generation
ON members (genealogy_id, generation_index);

CREATE INDEX IF NOT EXISTS idx_members_genealogy_name
ON members (genealogy_id, name);

CREATE INDEX IF NOT EXISTS idx_parent_child_parent
ON parent_child_relations (parent_id);

CREATE INDEX IF NOT EXISTS idx_parent_child_child
ON parent_child_relations (child_id);

CREATE INDEX IF NOT EXISTS idx_parent_child_genealogy_parent
ON parent_child_relations (genealogy_id, parent_id);

CREATE INDEX IF NOT EXISTS idx_parent_child_genealogy_child
ON parent_child_relations (genealogy_id, child_id);

CREATE INDEX IF NOT EXISTS idx_marriages_spouse_a
ON marriages (spouse_a_id);

CREATE INDEX IF NOT EXISTS idx_marriages_spouse_b
ON marriages (spouse_b_id);
