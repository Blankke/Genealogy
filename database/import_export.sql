-- CSV 导入导出示例。请先执行 database/schema.sql。
-- Windows PowerShell 推荐通过 scripts/import_csv.ps1 调用，避免手工维护绝对路径。

-- 导入顺序必须满足外键依赖：
-- \copy users(id, username, email, password_hash, is_admin, created_at) FROM 'data/generated/users.csv' WITH (FORMAT csv, HEADER true)
-- \copy genealogies(id, name, surname, revision_time, owner_user_id, created_at) FROM 'data/generated/genealogies.csv' WITH (FORMAT csv, HEADER true)
-- \copy genealogy_collaborators(id, genealogy_id, user_id, role, invited_at) FROM 'data/generated/genealogy_collaborators.csv' WITH (FORMAT csv, HEADER true)
-- \copy members(id, genealogy_id, name, gender, birth_date, death_date, generation_index, biography, created_at) FROM 'data/generated/members.csv' WITH (FORMAT csv, HEADER true)
-- \copy parent_child_relations(id, genealogy_id, parent_id, child_id, parent_role, created_at) FROM 'data/generated/parent_child_relations.csv' WITH (FORMAT csv, HEADER true)
-- \copy marriages(id, genealogy_id, spouse_a_id, spouse_b_id, start_date, end_date, status, created_at) FROM 'data/generated/marriages.csv' WITH (FORMAT csv, HEADER true)

-- 导出某成员分支备份：
WITH RECURSIVE branch AS (
    SELECT :root_member_id::BIGINT AS member_id
    UNION ALL
    SELECT pcr.child_id
    FROM parent_child_relations pcr
    JOIN branch ON branch.member_id = pcr.parent_id
)
SELECT members.*
FROM members
JOIN branch ON branch.member_id = members.id
ORDER BY members.generation_index, members.id;
