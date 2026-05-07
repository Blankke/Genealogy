-- 四代曾孙查询性能对比脚本。
-- 使用示例：
--   psql -U genealogy_app -d genealogy -v root_member_id=1 -f database/performance_compare.sql

\timing on

DROP INDEX IF EXISTS idx_parent_child_parent;
DROP INDEX IF EXISTS idx_parent_child_genealogy_parent;

EXPLAIN (ANALYZE, BUFFERS)
SELECT great_grandchild.*
FROM parent_child_relations p1
JOIN parent_child_relations p2 ON p2.parent_id = p1.child_id
JOIN parent_child_relations p3 ON p3.parent_id = p2.child_id
JOIN members great_grandchild ON great_grandchild.id = p3.child_id
WHERE p1.parent_id = :root_member_id::BIGINT;

CREATE INDEX IF NOT EXISTS idx_parent_child_parent
ON parent_child_relations (parent_id);

CREATE INDEX IF NOT EXISTS idx_parent_child_genealogy_parent
ON parent_child_relations (genealogy_id, parent_id);

EXPLAIN (ANALYZE, BUFFERS)
SELECT great_grandchild.*
FROM parent_child_relations p1
JOIN parent_child_relations p2 ON p2.parent_id = p1.child_id
JOIN parent_child_relations p3 ON p3.parent_id = p2.child_id
JOIN members great_grandchild ON great_grandchild.id = p3.child_id
WHERE p1.parent_id = :root_member_id::BIGINT;
