-- 人物亲缘关系路径查询。
-- 使用示例：
--   psql -U genealogy_app -d genealogy -v source_member_id=1 -v target_member_id=200 -f database/relationship_path.sql

WITH RECURSIVE edges AS (
    SELECT parent_id AS from_id, child_id AS to_id, 'parent_child' AS relation_type
    FROM parent_child_relations
    UNION ALL
    SELECT child_id, parent_id, 'child_parent'
    FROM parent_child_relations
    UNION ALL
    SELECT spouse_a_id, spouse_b_id, 'marriage'
    FROM marriages
    UNION ALL
    SELECT spouse_b_id, spouse_a_id, 'marriage'
    FROM marriages
),
search AS (
    SELECT
        :source_member_id::BIGINT AS member_id,
        ARRAY[:source_member_id::BIGINT] AS path_ids,
        ARRAY[]::TEXT[] AS relation_steps,
        0 AS depth
    UNION ALL
    SELECT
        edges.to_id,
        search.path_ids || edges.to_id,
        search.relation_steps || edges.relation_type,
        search.depth + 1
    FROM search
    JOIN edges ON edges.from_id = search.member_id
    WHERE search.depth < 20
      AND NOT edges.to_id = ANY(search.path_ids)
)
SELECT search.path_ids, search.relation_steps, search.depth
FROM search
WHERE search.member_id = :target_member_id::BIGINT
ORDER BY search.depth
LIMIT 1;
