# SQL 查询逻辑报告

## 1. 查询配偶及所有子女

需求：给定一个成员 ID，查询其配偶及所有子女。

逻辑：从 `marriages` 查配偶，从 `parent_child_relations` 查子女，使用 `UNION ALL` 合并两类结果。

SQL 文件：`database/core_queries.sql`

```sql
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
```

## 2. 递归查询所有祖先

需求：输入成员 A 的 ID，输出其向上追溯的所有历代祖先。

逻辑：递归 CTE 第一层查父母，后续层继续从上一层祖先向上查父母，用 `path` 数组避免循环。

SQL 文件：`database/core_queries.sql`

```sql
WITH RECURSIVE ancestors AS (
    SELECT pcr.parent_id AS member_id, pcr.child_id, pcr.parent_role, 1 AS depth,
           ARRAY[pcr.child_id, pcr.parent_id] AS path
    FROM parent_child_relations pcr
    WHERE pcr.child_id = :member_id::BIGINT
    UNION ALL
    SELECT pcr.parent_id, pcr.child_id, pcr.parent_role, ancestors.depth + 1,
           ancestors.path || pcr.parent_id
    FROM parent_child_relations pcr
    JOIN ancestors ON ancestors.member_id = pcr.child_id
    WHERE NOT pcr.parent_id = ANY(ancestors.path)
)
SELECT ancestors.depth, ancestors.parent_role, members.*
FROM ancestors
JOIN members ON members.id = ancestors.member_id
ORDER BY ancestors.depth, members.id;
```

## 3. 平均寿命最长的一代人

需求：统计某个家族中平均寿命最长的一代人。

逻辑：按 `generation_index` 分组，只统计有生卒日期的成员，用 `age(death_date, birth_date)` 计算寿命并取平均。

SQL 文件：`database/core_queries.sql`

```sql
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
```

## 4. 超过 50 岁且没有配偶的男性成员

需求：查询所有年龄超过 50 岁且没有配偶的男性成员。

逻辑：限定男性和出生日期，用当前日期减 50 年判断年龄，再用 `NOT EXISTS` 排除婚姻表中出现过的成员。

SQL 文件：`database/core_queries.sql`

```sql
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
```

## 5. 早于该辈分平均出生年份的成员

需求：找出家族中出生年份早于该辈分平均出生年份的所有成员。

逻辑：先按族谱和辈分计算平均出生年份，再与成员表回连，筛选出生年份小于平均值的成员。

SQL 文件：`database/core_queries.sql`

```sql
WITH generation_average AS (
    SELECT genealogy_id, generation_index, AVG(EXTRACT(YEAR FROM birth_date)) AS average_birth_year
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
```

## 6. 两人亲缘关系通路

需求：输入两个人的 ID，查询两者之间是否存在亲缘关系通路。

逻辑：把亲子关系和婚姻关系转成无向边，从成员 A 递归搜索成员 B，用 `path_ids` 防止重复访问并返回最短路径。

SQL 文件：`database/relationship_path.sql`

```sql
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
    SELECT :source_member_id::BIGINT AS member_id,
           ARRAY[:source_member_id::BIGINT] AS path_ids,
           ARRAY[]::TEXT[] AS relation_steps,
           0 AS depth
    UNION ALL
    SELECT edges.to_id, search.path_ids || edges.to_id,
           search.relation_steps || edges.relation_type, search.depth + 1
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
```
