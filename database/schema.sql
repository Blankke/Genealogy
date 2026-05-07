-- 族谱管理系统 PostgreSQL 建表脚本。
-- 使用示例：
--   psql -U genealogy_app -d genealogy -f database/schema.sql

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS genealogies (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    surname VARCHAR(32) NOT NULL,
    revision_time DATE,
    owner_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS genealogy_collaborators (
    id BIGSERIAL PRIMARY KEY,
    genealogy_id BIGINT NOT NULL REFERENCES genealogies(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(16) NOT NULL DEFAULT 'editor',
    invited_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_genealogy_collaborators_role CHECK (role IN ('editor', 'viewer')),
    CONSTRAINT ux_genealogy_collaborators UNIQUE (genealogy_id, user_id)
);

CREATE TABLE IF NOT EXISTS members (
    id BIGSERIAL PRIMARY KEY,
    genealogy_id BIGINT NOT NULL REFERENCES genealogies(id) ON DELETE CASCADE,
    name VARCHAR(128) NOT NULL,
    gender VARCHAR(16) NOT NULL,
    birth_date DATE,
    death_date DATE,
    generation_index INTEGER NOT NULL,
    biography TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_members_gender CHECK (gender IN ('male', 'female', 'unknown')),
    CONSTRAINT ck_members_life_dates CHECK (
        birth_date IS NULL OR death_date IS NULL OR death_date >= birth_date
    ),
    CONSTRAINT ck_members_generation CHECK (generation_index >= 1)
);

CREATE TABLE IF NOT EXISTS parent_child_relations (
    id BIGSERIAL PRIMARY KEY,
    genealogy_id BIGINT NOT NULL REFERENCES genealogies(id) ON DELETE CASCADE,
    parent_id BIGINT NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    child_id BIGINT NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    parent_role VARCHAR(16) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_parent_child_role CHECK (parent_role IN ('father', 'mother')),
    CONSTRAINT ck_parent_child_not_self CHECK (parent_id <> child_id),
    CONSTRAINT ux_parent_child_role UNIQUE (parent_id, child_id, parent_role)
);

CREATE TABLE IF NOT EXISTS marriages (
    id BIGSERIAL PRIMARY KEY,
    genealogy_id BIGINT NOT NULL REFERENCES genealogies(id) ON DELETE CASCADE,
    spouse_a_id BIGINT NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    spouse_b_id BIGINT NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    start_date DATE,
    end_date DATE,
    status VARCHAR(16) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_marriages_not_self CHECK (spouse_a_id <> spouse_b_id),
    CONSTRAINT ck_marriages_status CHECK (status IN ('active', 'ended')),
    CONSTRAINT ck_marriages_dates CHECK (
        start_date IS NULL OR end_date IS NULL OR end_date >= start_date
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_marriages_pair
ON marriages (genealogy_id, LEAST(spouse_a_id, spouse_b_id), GREATEST(spouse_a_id, spouse_b_id));

CREATE OR REPLACE FUNCTION validate_parent_child_relation()
RETURNS trigger AS $$
DECLARE
    parent_member members%ROWTYPE;
    child_member members%ROWTYPE;
BEGIN
    SELECT * INTO parent_member FROM members WHERE id = NEW.parent_id;
    SELECT * INTO child_member FROM members WHERE id = NEW.child_id;

    IF parent_member.genealogy_id <> NEW.genealogy_id OR child_member.genealogy_id <> NEW.genealogy_id THEN
        RAISE EXCEPTION '亲子关系两端成员必须属于同一个族谱';
    END IF;

    IF NEW.parent_role = 'father' AND parent_member.gender <> 'male' THEN
        RAISE EXCEPTION '父亲关系的父节点性别必须为 male';
    END IF;

    IF NEW.parent_role = 'mother' AND parent_member.gender <> 'female' THEN
        RAISE EXCEPTION '母亲关系的父节点性别必须为 female';
    END IF;

    IF parent_member.generation_index >= child_member.generation_index THEN
        RAISE EXCEPTION '父母辈分必须早于子女辈分';
    END IF;

    IF parent_member.birth_date IS NOT NULL
       AND child_member.birth_date IS NOT NULL
       AND parent_member.birth_date >= child_member.birth_date THEN
        RAISE EXCEPTION '父母出生日期必须早于子女出生日期';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validate_parent_child_relation ON parent_child_relations;
CREATE TRIGGER trg_validate_parent_child_relation
BEFORE INSERT OR UPDATE ON parent_child_relations
FOR EACH ROW EXECUTE FUNCTION validate_parent_child_relation();

CREATE OR REPLACE FUNCTION validate_marriage_relation()
RETURNS trigger AS $$
DECLARE
    spouse_a members%ROWTYPE;
    spouse_b members%ROWTYPE;
BEGIN
    SELECT * INTO spouse_a FROM members WHERE id = NEW.spouse_a_id;
    SELECT * INTO spouse_b FROM members WHERE id = NEW.spouse_b_id;

    IF spouse_a.genealogy_id <> NEW.genealogy_id OR spouse_b.genealogy_id <> NEW.genealogy_id THEN
        RAISE EXCEPTION '婚姻关系两端成员必须属于同一个族谱';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validate_marriage_relation ON marriages;
CREATE TRIGGER trg_validate_marriage_relation
BEFORE INSERT OR UPDATE ON marriages
FOR EACH ROW EXECUTE FUNCTION validate_marriage_relation();
