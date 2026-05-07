-- 核心查询 SQL，参数采用 psql 变量写法，例如：
--   psql -U genealogy_app -d genealogy -v member_id=1 -f database/core_queries.sql

-- 1. 基本查询：给定成员 ID，查询其配偶及所有子女。
WITH target AS (
    SELECT :member_id::BIGINT AS member_id
),
spouses AS (
    SELECT
        CASE WHEN m.spouse_a_id = target.member_id THEN m.spouse_b_id ELSE m.spouse_a_id END AS related_member_id,
        'spouse' AS relation_type
    FROM marriages m
    JOIN target ON target.member_id IN (m.spouse_a_id, m.spouse_b_id)
),
children AS (
    SELECT child_id AS related_member_id, 'child' AS relation_type
    FROM parent_child_relations pcr
    JOIN target ON target.member_id = pcr.parent_id
)
SELECT r.relation_type, mem.*
FROM (
    SELECT * FROM spouses
    UNION ALL
    SELECT * FROM children
) r
JOIN members mem ON mem.id = r.related_member_id
ORDER BY r.relation_type, mem.birth_date NULLS LAST, mem.id;

-- 2. 递归查询：输入成员 A 的 ID，输出其所有历代祖先。
WITH RECURSIVE ancestors AS (
    SELECT
        pcr.parent_id AS member_id,
        pcr.child_id,
        pcr.parent_role,
        1 AS depth,
        ARRAY[pcr.child_id, pcr.parent_id] AS path
    FROM parent_child_relations pcr
    WHERE pcr.child_id = :member_id::BIGINT

    UNION ALL

    SELECT
        pcr.parent_id,
        pcr.child_id,
        pcr.parent_role,
        ancestors.depth + 1,
        ancestors.path || pcr.parent_id
    FROM parent_child_relations pcr
    JOIN ancestors ON ancestors.member_id = pcr.child_id
    WHERE NOT pcr.parent_id = ANY(ancestors.path)
)
SELECT ancestors.depth, ancestors.parent_role, members.*
FROM ancestors
JOIN members ON members.id = ancestors.member_id
ORDER BY ancestors.depth, members.id;

-- 3. 统计分析：统计某个家族中平均寿命最长的一代人。
SELECT
    generation_index,
    ROUND(AVG(EXTRACT(YEAR FROM age(death_date, birth_date)))::NUMERIC, 2) AS average_lifespan_years,
    COUNT(*) AS sample_count
FROM members
WHERE genealogy_id = :genealogy_id::BIGINT
  AND birth_date IS NOT NULL
  AND death_date IS NOT NULL
GROUP BY generation_index
ORDER BY average_lifespan_years DESC, sample_count DESC
LIMIT 1;

-- 4. 条件筛选：年龄超过 50 岁且没有配偶的男性成员。
SELECT members.*
FROM members
WHERE gender = 'male'
  AND birth_date IS NOT NULL
  AND birth_date <= CURRENT_DATE - INTERVAL '50 years'
  AND NOT EXISTS (
      SELECT 1
      FROM marriages
      WHERE members.id IN (marriages.spouse_a_id, marriages.spouse_b_id)
  )
ORDER BY birth_date, id;

-- 5. 对比分析：找出家族中出生年份早于该辈分平均出生年份的所有成员。
WITH generation_average AS (
    SELECT
        genealogy_id,
        generation_index,
        AVG(EXTRACT(YEAR FROM birth_date)) AS average_birth_year
    FROM members
    WHERE genealogy_id = :genealogy_id::BIGINT
      AND birth_date IS NOT NULL
    GROUP BY genealogy_id, generation_index
)
SELECT members.*, generation_average.average_birth_year
FROM members
JOIN generation_average
  ON generation_average.genealogy_id = members.genealogy_id
 AND generation_average.generation_index = members.generation_index
WHERE members.birth_date IS NOT NULL
  AND EXTRACT(YEAR FROM members.birth_date) < generation_average.average_birth_year
ORDER BY members.generation_index, members.birth_date, members.id;
