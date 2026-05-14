from collections import deque
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import case, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import (
    Genealogy,
    GenealogyCollaborator,
    Marriage,
    Member,
    ParentChildRelation,
    User,
)
from app.schemas import (
    AdminDashboardRead,
    AncestorRead,
    CommonAncestorRead,
    DashboardRead,
    FamilyRead,
    GenealogyCreate,
    GenealogyRead,
    GenealogyUpdate,
    InviteRequest,
    LoginRequest,
    MarriageCreate,
    MemberCreate,
    MemberListRead,
    MemberRead,
    MemberUpdate,
    ParentChildCreate,
    RegisterRequest,
    RelationshipPathRead,
    SqlQueryDefinitionRead,
    SqlQueryResultRead,
    SqlQueryRunRequest,
    TokenResponse,
    TreeNode,
    TreePageRead,
    UserRead,
)
from app.security import create_access_token, hash_password, verify_password
from app.services import (
    accessible_genealogies_query,
    assert_genealogy_access,
    get_member_with_access,
)

app = FastAPI(title="族谱管理系统 API", version="0.1.0")

TREE_PREVIEW_PAGE_SIZE = 1500
TREE_PREVIEW_REQUIRE_ROOT_MEMBER_THRESHOLD = 10000

ANCESTOR_QUERY_SQL = """
WITH RECURSIVE ancestors AS (
    SELECT
        pcr.parent_id AS member_id,
        pcr.child_id,
        pcr.parent_role,
        1 AS depth,
        ARRAY[CAST(pcr.child_id AS BIGINT), CAST(pcr.parent_id AS BIGINT)] AS path
    FROM parent_child_relations pcr
    WHERE pcr.child_id = CAST(:member_id AS BIGINT)
      AND pcr.genealogy_id = CAST(:genealogy_id AS BIGINT)

    UNION ALL

    SELECT
        pcr.parent_id,
        pcr.child_id,
        pcr.parent_role,
        ancestors.depth + 1,
        ancestors.path || pcr.parent_id
    FROM parent_child_relations pcr
    JOIN ancestors ON ancestors.member_id = pcr.child_id
    WHERE pcr.genealogy_id = CAST(:genealogy_id AS BIGINT)
      AND NOT pcr.parent_id = ANY(ancestors.path)
),
minimum_depth AS (
    SELECT member_id, MIN(depth) AS depth
    FROM ancestors
    GROUP BY member_id
),
summarized AS (
    SELECT
        ancestors.member_id,
        minimum_depth.depth,
        ARRAY_AGG(DISTINCT ancestors.parent_role ORDER BY ancestors.parent_role)
            FILTER (WHERE ancestors.depth = minimum_depth.depth) AS parent_roles,
        COUNT(*) FILTER (WHERE ancestors.depth = minimum_depth.depth) AS path_count
    FROM ancestors
    JOIN minimum_depth ON minimum_depth.member_id = ancestors.member_id
    GROUP BY ancestors.member_id, minimum_depth.depth
)
SELECT
    summarized.depth,
    summarized.parent_roles,
    summarized.path_count,
    summarized.parent_roles[1] AS parent_role,
    members.*
FROM summarized
JOIN members ON members.id = summarized.member_id
ORDER BY summarized.depth, members.id
""".strip()

SQL_QUERY_DEFINITIONS: dict[str, dict[str, Any]] = {
    "family_lookup": {
        "title": "基本查询：配偶与子女",
        "description": "给定一个成员 ID，查询其配偶及所有子女。",
        "required_params": ["member_id"],
        "sql": """
WITH target AS (
    SELECT CAST(:member_id AS BIGINT) AS member_id, CAST(:genealogy_id AS BIGINT) AS genealogy_id
),
spouses AS (
    SELECT
        CASE
            WHEN m.spouse_a_id = target.member_id THEN m.spouse_b_id
            ELSE m.spouse_a_id
        END AS related_member_id,
        'spouse' AS relation_type
    FROM marriages m
    JOIN target ON target.member_id IN (m.spouse_a_id, m.spouse_b_id)
    WHERE m.genealogy_id = target.genealogy_id
),
children AS (
    SELECT child_id AS related_member_id, 'child' AS relation_type
    FROM parent_child_relations pcr
    JOIN target ON target.member_id = pcr.parent_id
    WHERE pcr.genealogy_id = target.genealogy_id
)
SELECT r.relation_type, mem.*
FROM (
    SELECT * FROM spouses
    UNION ALL
    SELECT * FROM children
) r
JOIN members mem ON mem.id = r.related_member_id
ORDER BY r.relation_type, mem.birth_date NULLS LAST, mem.id
""".strip(),
    },
    "ancestor_cte": {
        "title": "递归查询：所有祖先",
        "description": "输入成员 A 的 ID，输出其向上追溯的所有历代祖先。",
        "required_params": ["member_id"],
        "sql": ANCESTOR_QUERY_SQL,
    },
    "longest_lifespan_generation": {
        "title": "统计分析：平均寿命最长的一代",
        "description": "统计当前族谱中平均寿命最长的一代人。",
        "required_params": [],
        "sql": """
SELECT
    generation_index,
    ROUND(
        AVG(EXTRACT(YEAR FROM age(death_date, birth_date)))::NUMERIC,
        2
    ) AS average_lifespan_years,
    COUNT(*) AS sample_count
FROM members
WHERE genealogy_id = CAST(:genealogy_id AS BIGINT)
  AND birth_date IS NOT NULL
  AND death_date IS NOT NULL
GROUP BY generation_index
ORDER BY average_lifespan_years DESC, sample_count DESC
LIMIT 1
""".strip(),
    },
    "single_male_over_50": {
        "title": "条件筛选：超过 50 岁且无配偶的男性",
        "description": "查询当前族谱中年龄超过 50 岁且没有配偶的男性成员。",
        "required_params": [],
        "sql": """
SELECT members.*
FROM members
WHERE members.genealogy_id = CAST(:genealogy_id AS BIGINT)
  AND members.gender = 'male'
  AND members.birth_date IS NOT NULL
  AND members.birth_date <= CURRENT_DATE - INTERVAL '50 years'
  AND NOT EXISTS (
      SELECT 1
      FROM marriages
      WHERE marriages.genealogy_id = members.genealogy_id
        AND members.id IN (marriages.spouse_a_id, marriages.spouse_b_id)
  )
ORDER BY members.birth_date, members.id
""".strip(),
    },
    "earlier_than_generation_average": {
        "title": "对比分析：早于本代平均出生年份的成员",
        "description": "找出当前族谱中出生年份早于该辈分平均出生年份的所有成员。",
        "required_params": [],
        "sql": """
WITH generation_average AS (
    SELECT
        genealogy_id,
        generation_index,
        AVG(EXTRACT(YEAR FROM birth_date)) AS average_birth_year
    FROM members
    WHERE genealogy_id = CAST(:genealogy_id AS BIGINT)
      AND birth_date IS NOT NULL
    GROUP BY genealogy_id, generation_index
)
SELECT members.*, generation_average.average_birth_year
FROM members
JOIN generation_average
  ON generation_average.genealogy_id = members.genealogy_id
 AND generation_average.generation_index = members.generation_index
WHERE members.genealogy_id = CAST(:genealogy_id AS BIGINT)
  AND members.birth_date IS NOT NULL
  AND EXTRACT(YEAR FROM members.birth_date) < generation_average.average_birth_year
ORDER BY members.generation_index, members.birth_date, members.id
""".strip(),
    },
}


def load_relationship_graph(
    db: Session, genealogy_id: int
) -> dict[int, list[tuple[int, str]]]:
    """将父母与婚姻关系统一展开为图结构，便于后续 BFS 搜索最短通路。"""

    rows = db.execute(
        text(
            """
            SELECT parent_id AS from_id, child_id AS to_id, 'parent_child' AS relation_type
            FROM parent_child_relations
            WHERE genealogy_id = :genealogy_id
            UNION ALL
            SELECT child_id AS from_id, parent_id AS to_id, 'child_parent' AS relation_type
            FROM parent_child_relations
            WHERE genealogy_id = :genealogy_id
            UNION ALL
            SELECT spouse_a_id AS from_id, spouse_b_id AS to_id, 'marriage' AS relation_type
            FROM marriages
            WHERE genealogy_id = :genealogy_id
            UNION ALL
            SELECT spouse_b_id AS from_id, spouse_a_id AS to_id, 'marriage' AS relation_type
            FROM marriages
            WHERE genealogy_id = :genealogy_id
            """
        ),
        {"genealogy_id": genealogy_id},
    ).mappings()

    graph: dict[int, list[tuple[int, str]]] = {}
    for row in rows:
        graph.setdefault(row["from_id"], []).append((row["to_id"], row["relation_type"]))

    for neighbors in graph.values():
        neighbors.sort(key=lambda item: (item[0], item[1]))

    return graph


def reconstruct_relationship_path(
    previous: dict[int, tuple[int | None, str | None]], target_member_id: int
) -> tuple[list[int], list[str]]:
    """根据 BFS 前驱表还原成员路径与边类型。"""

    path_ids: list[int] = []
    relation_steps: list[str] = []
    current_id: int | None = target_member_id

    while current_id is not None:
        previous_id, relation_type = previous[current_id]
        path_ids.append(current_id)
        if relation_type is not None:
            relation_steps.append(relation_type)
        current_id = previous_id

    path_ids.reverse()
    relation_steps.reverse()
    return path_ids, relation_steps


def find_shortest_relationship_path(
    graph: dict[int, list[tuple[int, str]]], source_member_id: int, target_member_id: int
) -> tuple[list[int], list[str]] | None:
    """使用 BFS 搜索最短亲缘通路，避免递归 SQL 在大图上指数扩张。"""

    if source_member_id == target_member_id:
        return [source_member_id], []

    previous: dict[int, tuple[int | None, str | None]] = {
        source_member_id: (None, None)
    }
    queue: deque[int] = deque([source_member_id])

    while queue:
        current_id = queue.popleft()
        for neighbor_id, relation_type in graph.get(current_id, []):
            if neighbor_id in previous:
                continue

            previous[neighbor_id] = (current_id, relation_type)
            if neighbor_id == target_member_id:
                return reconstruct_relationship_path(previous, target_member_id)

            queue.append(neighbor_id)

    return None

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def serialize_sql_cell(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


@app.post("/auth/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    exists_user = db.scalar(
        select(User).where(or_(User.username == payload.username, User.email == payload.email))
    )
    if exists_user is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名或邮箱已存在")

    user = User(
        username=payload.username,
        email=str(payload.email),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(str(user.id)))


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")
    return TokenResponse(access_token=create_access_token(str(user.id)))


@app.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@app.get("/genealogies/{genealogy_id}/sql-queries", response_model=list[SqlQueryDefinitionRead])
def list_sql_queries(
    genealogy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SqlQueryDefinitionRead]:
    assert_genealogy_access(db, current_user, genealogy_id)
    return [
        SqlQueryDefinitionRead(
            key=key,
            title=query["title"],
            description=query["description"],
            sql=query["sql"],
            required_params=query["required_params"],
        )
        for key, query in SQL_QUERY_DEFINITIONS.items()
    ]


@app.post(
    "/genealogies/{genealogy_id}/sql-queries/run",
    response_model=SqlQueryResultRead,
)
def run_sql_query(
    genealogy_id: int,
    payload: SqlQueryRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SqlQueryResultRead:
    assert_genealogy_access(db, current_user, genealogy_id)
    query = SQL_QUERY_DEFINITIONS.get(payload.query_key)
    if query is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SQL 查询模板不存在")

    params: dict[str, Any] = {"genealogy_id": genealogy_id}
    if "member_id" in query["required_params"]:
        if payload.member_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="member_id 为必填参数",
            )
        member_exists = db.scalar(
            select(func.count(Member.id)).where(
                Member.id == payload.member_id,
                Member.genealogy_id == genealogy_id,
            )
        )
        if not member_exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="查询成员不存在")
        params["member_id"] = payload.member_id

    result = db.execute(text(query["sql"]), params)
    columns = list(result.keys())
    rows = [
        {column: serialize_sql_cell(row[column]) for column in columns}
        for row in result.mappings().all()
    ]
    return SqlQueryResultRead(
        key=payload.query_key,
        title=query["title"],
        description=query["description"],
        sql=query["sql"],
        columns=columns,
        rows=rows,
    )


@app.get("/admin/dashboard", response_model=AdminDashboardRead)
def admin_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AdminDashboardRead:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可访问")

    member_row = db.execute(
        select(
            func.count(Member.id).label("total_members"),
            func.sum(case((Member.gender == "male", 1), else_=0)).label("male_count"),
            func.sum(case((Member.gender == "female", 1), else_=0)).label("female_count"),
            func.sum(case((Member.gender == "unknown", 1), else_=0)).label("unknown_count"),
        )
    ).one()
    return AdminDashboardRead(
        total_users=db.scalar(select(func.count(User.id))) or 0,
        total_genealogies=db.scalar(select(func.count(Genealogy.id))) or 0,
        total_members=int(member_row.total_members or 0),
        male_count=int(member_row.male_count or 0),
        female_count=int(member_row.female_count or 0),
        unknown_count=int(member_row.unknown_count or 0),
        total_parent_child_relations=db.scalar(select(func.count(ParentChildRelation.id))) or 0,
        total_marriages=db.scalar(select(func.count(Marriage.id))) or 0,
    )


@app.get("/genealogies", response_model=list[GenealogyRead])
def list_genealogies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Genealogy]:
    return list(db.scalars(accessible_genealogies_query(current_user).order_by(Genealogy.id)).all())


@app.post("/genealogies", response_model=GenealogyRead, status_code=status.HTTP_201_CREATED)
def create_genealogy(
    payload: GenealogyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Genealogy:
    genealogy = Genealogy(
        name=payload.name,
        surname=payload.surname,
        revision_time=payload.revision_time,
        owner_user_id=current_user.id,
    )
    db.add(genealogy)
    db.commit()
    db.refresh(genealogy)
    return genealogy


@app.get("/genealogies/{genealogy_id}", response_model=GenealogyRead)
def get_genealogy(
    genealogy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Genealogy:
    return assert_genealogy_access(db, current_user, genealogy_id)


@app.patch("/genealogies/{genealogy_id}", response_model=GenealogyRead)
def update_genealogy(
    genealogy_id: int,
    payload: GenealogyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Genealogy:
    genealogy = assert_genealogy_access(db, current_user, genealogy_id, write=True)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(genealogy, field, value)
    db.commit()
    db.refresh(genealogy)
    return genealogy


@app.delete("/genealogies/{genealogy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_genealogy(
    genealogy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    genealogy = assert_genealogy_access(db, current_user, genealogy_id, owner_only=True)
    db.delete(genealogy)
    db.commit()


@app.post("/genealogies/{genealogy_id}/invite")
def invite_collaborator(
    genealogy_id: int,
    payload: InviteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    genealogy = assert_genealogy_access(db, current_user, genealogy_id, owner_only=True)
    invited_user = db.scalar(select(User).where(User.email == payload.email))
    if invited_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="被邀请用户不存在")
    if invited_user.id == genealogy.owner_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="创建者不需要被邀请")

    collaborator = db.scalar(
        select(GenealogyCollaborator).where(
            GenealogyCollaborator.genealogy_id == genealogy_id,
            GenealogyCollaborator.user_id == invited_user.id,
        )
    )
    if collaborator is None:
        collaborator = GenealogyCollaborator(
            genealogy_id=genealogy_id,
            user_id=invited_user.id,
            role=payload.role,
        )
        db.add(collaborator)
    else:
        collaborator.role = payload.role
    db.commit()
    return {"genealogy_id": genealogy_id, "user_id": invited_user.id, "role": payload.role}


@app.get("/genealogies/{genealogy_id}/dashboard", response_model=DashboardRead)
def dashboard(
    genealogy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DashboardRead:
    assert_genealogy_access(db, current_user, genealogy_id)
    row = db.execute(
        select(
            func.count(Member.id).label("total_members"),
            func.sum(case((Member.gender == "male", 1), else_=0)).label("male_count"),
            func.sum(case((Member.gender == "female", 1), else_=0)).label("female_count"),
            func.sum(case((Member.gender == "unknown", 1), else_=0)).label("unknown_count"),
        ).where(Member.genealogy_id == genealogy_id)
    ).one()
    return DashboardRead(
        genealogy_id=genealogy_id,
        total_members=int(row.total_members or 0),
        male_count=int(row.male_count or 0),
        female_count=int(row.female_count or 0),
        unknown_count=int(row.unknown_count or 0),
    )


@app.get("/genealogies/{genealogy_id}/members", response_model=MemberListRead)
def list_members(
    genealogy_id: int,
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MemberListRead:
    assert_genealogy_access(db, current_user, genealogy_id)
    statement = select(Member).where(Member.genealogy_id == genealogy_id)
    if search:
        statement = statement.where(Member.name.ilike(f"%{search}%"))
    # 先统计总数，再按稳定排序返回当前页，便于前端做翻页。
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    statement = statement.order_by(Member.generation_index, Member.id).limit(limit).offset(offset)
    return MemberListRead(
        items=list(db.scalars(statement).all()),
        total=total,
        limit=limit,
        offset=offset,
    )


@app.post(
    "/genealogies/{genealogy_id}/members",
    response_model=MemberRead,
    status_code=status.HTTP_201_CREATED,
)
def create_member(
    genealogy_id: int,
    payload: MemberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Member:
    assert_genealogy_access(db, current_user, genealogy_id, write=True)
    member = Member(genealogy_id=genealogy_id, **payload.model_dump())
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@app.patch("/members/{member_id}", response_model=MemberRead)
def update_member(
    member_id: int,
    payload: MemberUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Member:
    member = get_member_with_access(db, current_user, member_id, write=True)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(member, field, value)
    db.commit()
    db.refresh(member)
    return member


@app.delete("/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_member(
    member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    member = get_member_with_access(db, current_user, member_id, write=True)
    db.delete(member)
    db.commit()


@app.post("/genealogies/{genealogy_id}/relations/parent-child", status_code=status.HTTP_201_CREATED)
def create_parent_child_relation(
    genealogy_id: int,
    payload: ParentChildCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int]:
    assert_genealogy_access(db, current_user, genealogy_id, write=True)
    parent = db.get(Member, payload.parent_id)
    child = db.get(Member, payload.child_id)
    if parent is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"父/母成员不存在：{payload.parent_id}",
        )
    if child is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"子女成员不存在：{payload.child_id}",
        )
    if parent.genealogy_id != genealogy_id or child.genealogy_id != genealogy_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"亲子关系成员不属于当前族谱 {genealogy_id}。"
                f"parent_id={payload.parent_id} 属于族谱 {parent.genealogy_id}；"
                f"child_id={payload.child_id} 属于族谱 {child.genealogy_id}。"
            ),
        )
    if payload.parent_role == "father" and parent.gender != "male":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="父亲关系要求父节点性别为男性",
        )
    if payload.parent_role == "mother" and parent.gender != "female":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="母亲关系要求母节点性别为女性",
        )
    if parent.generation_index >= child.generation_index:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="父母辈分必须早于子女辈分",
        )
    if (
        parent.birth_date is not None
        and child.birth_date is not None
        and parent.birth_date >= child.birth_date
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="父母出生日期必须早于子女出生日期",
        )
    relation = ParentChildRelation(genealogy_id=genealogy_id, **payload.model_dump())
    db.add(relation)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"创建亲子关系失败：{exc.orig}",
        ) from exc
    db.refresh(relation)
    return {"id": relation.id}


@app.post("/genealogies/{genealogy_id}/marriages", status_code=status.HTTP_201_CREATED)
def create_marriage(
    genealogy_id: int,
    payload: MarriageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int]:
    assert_genealogy_access(db, current_user, genealogy_id, write=True)
    spouse_a = db.get(Member, payload.spouse_a_id)
    spouse_b = db.get(Member, payload.spouse_b_id)
    if (
        spouse_a is None
        or spouse_b is None
        or spouse_a.genealogy_id != genealogy_id
        or spouse_b.genealogy_id != genealogy_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="婚姻关系成员不属于该族谱",
        )
    marriage = Marriage(genealogy_id=genealogy_id, **payload.model_dump())
    db.add(marriage)
    db.commit()
    db.refresh(marriage)
    return {"id": marriage.id}


@app.get("/members/{member_id}/family", response_model=FamilyRead)
def get_family(
    member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FamilyRead:
    member = get_member_with_access(db, current_user, member_id)
    spouse_ids = db.scalars(
        select(
            case(
                (Marriage.spouse_a_id == member_id, Marriage.spouse_b_id),
                else_=Marriage.spouse_a_id,
            )
        ).where(or_(Marriage.spouse_a_id == member_id, Marriage.spouse_b_id == member_id))
    ).all()
    spouses = (
        list(db.scalars(select(Member).where(Member.id.in_(spouse_ids))).all())
        if spouse_ids
        else []
    )
    children = list(
        db.scalars(
            select(Member)
            .join(ParentChildRelation, ParentChildRelation.child_id == Member.id)
            .where(ParentChildRelation.parent_id == member_id)
            .order_by(Member.birth_date, Member.id)
        ).all()
    )
    return FamilyRead(member=member, spouses=spouses, children=children)


@app.get("/members/{member_id}/ancestors", response_model=list[AncestorRead])
def get_ancestors(
    member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AncestorRead]:
    member = get_member_with_access(db, current_user, member_id)
    rows = db.execute(
        text(ANCESTOR_QUERY_SQL),
        {"member_id": member_id, "genealogy_id": member.genealogy_id},
    ).mappings()
    return [
        AncestorRead(
            depth=row["depth"],
            parent_role=row["parent_role"],
            parent_roles=list(row["parent_roles"] or []),
            path_count=row["path_count"],
            member=MemberRead.model_validate(dict(row)),
        )
        for row in rows
    ]


@app.get(
    "/genealogies/{genealogy_id}/common-ancestors",
    response_model=list[CommonAncestorRead],
)
def get_earliest_common_ancestors(
    genealogy_id: int,
    first_member_id: int,
    second_member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CommonAncestorRead]:
    assert_genealogy_access(db, current_user, genealogy_id)
    if first_member_id == second_member_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="请填写两个不同的成员 ID",
        )

    member_count = db.scalar(
        select(func.count(Member.id)).where(
            Member.genealogy_id == genealogy_id,
            Member.id.in_([first_member_id, second_member_id]),
        )
    )
    if member_count != 2:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="查询成员不存在")

    rows = db.execute(
        text(
            """
            WITH RECURSIVE first_ancestors AS (
                SELECT pcr.parent_id AS member_id,
                       1 AS depth,
                       ARRAY[CAST(pcr.child_id AS BIGINT), CAST(pcr.parent_id AS BIGINT)] AS path
                FROM parent_child_relations pcr
                WHERE pcr.child_id = :first_member_id AND pcr.genealogy_id = :genealogy_id
                UNION ALL
                SELECT pcr.parent_id,
                       first_ancestors.depth + 1,
                       first_ancestors.path || pcr.parent_id
                FROM parent_child_relations pcr
                JOIN first_ancestors ON first_ancestors.member_id = pcr.child_id
                WHERE pcr.genealogy_id = :genealogy_id
                  AND NOT pcr.parent_id = ANY(first_ancestors.path)
            ),
            second_ancestors AS (
                SELECT pcr.parent_id AS member_id,
                       1 AS depth,
                       ARRAY[CAST(pcr.child_id AS BIGINT), CAST(pcr.parent_id AS BIGINT)] AS path
                FROM parent_child_relations pcr
                WHERE pcr.child_id = :second_member_id AND pcr.genealogy_id = :genealogy_id
                UNION ALL
                SELECT pcr.parent_id,
                       second_ancestors.depth + 1,
                       second_ancestors.path || pcr.parent_id
                FROM parent_child_relations pcr
                JOIN second_ancestors ON second_ancestors.member_id = pcr.child_id
                WHERE pcr.genealogy_id = :genealogy_id
                  AND NOT pcr.parent_id = ANY(second_ancestors.path)
            ),
            first_ranked AS (
                SELECT member_id, MIN(depth) AS first_depth
                FROM first_ancestors
                GROUP BY member_id
            ),
            second_ranked AS (
                SELECT member_id, MIN(depth) AS second_depth
                FROM second_ancestors
                GROUP BY member_id
            ),
            common_ancestors AS (
                SELECT
                    members.*,
                    first_ranked.first_depth,
                    second_ranked.second_depth
                FROM first_ranked
                JOIN second_ranked ON second_ranked.member_id = first_ranked.member_id
                JOIN members ON members.id = first_ranked.member_id
                WHERE members.genealogy_id = :genealogy_id
            ),
            earliest_generation AS (
                SELECT MIN(generation_index) AS generation_index
                FROM common_ancestors
            )
            SELECT
                common_ancestors.first_depth,
                common_ancestors.second_depth,
                common_ancestors.*
            FROM common_ancestors
            JOIN earliest_generation
              ON earliest_generation.generation_index = common_ancestors.generation_index
            ORDER BY common_ancestors.birth_date NULLS LAST, common_ancestors.id
            """
        ),
        {
            "genealogy_id": genealogy_id,
            "first_member_id": first_member_id,
            "second_member_id": second_member_id,
        },
    ).mappings()
    return [
        CommonAncestorRead(
            first_depth=row["first_depth"],
            second_depth=row["second_depth"],
            member=MemberRead.model_validate(dict(row)),
        )
        for row in rows
    ]


@app.get("/genealogies/{genealogy_id}/tree", response_model=TreePageRead)
def get_descendant_tree(
    genealogy_id: int,
    root_member_id: int | None = None,
    max_depth: int = Query(default=3, ge=1, le=12),
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TreePageRead:
    assert_genealogy_access(db, current_user, genealogy_id)
    if root_member_id is None:
        member_total = db.scalar(
            select(func.count(Member.id)).where(Member.genealogy_id == genealogy_id)
        ) or 0
        if member_total > TREE_PREVIEW_REQUIRE_ROOT_MEMBER_THRESHOLD:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"当前族谱成员数为 {member_total}，请先输入根成员 ID 再预览树形分支，"
                    "避免一次性展开过大范围。"
                ),
            )
        root_member_id = db.scalar(
            select(Member.id)
            .where(Member.genealogy_id == genealogy_id)
            .order_by(Member.generation_index, Member.birth_date, Member.id)
            .limit(1)
        )
    if root_member_id is None:
        return TreePageRead(
            items=[],
            page=1,
            page_size=TREE_PREVIEW_PAGE_SIZE,
            page_nodes=0,
            total_nodes=0,
            total_pages=1,
        )
    root_exists = db.scalar(
        select(func.count(Member.id)).where(
            Member.id == root_member_id,
            Member.genealogy_id == genealogy_id,
        )
    )
    if not root_exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="根成员不存在")

    rows = list(
        db.execute(
            text(
                """
                WITH RECURSIVE reachable AS (
                    SELECT CAST(:root_member_id AS BIGINT) AS member_id, 0 AS depth
                    UNION
                    SELECT pcr.child_id AS member_id, reachable.depth + 1
                    FROM reachable
                    JOIN parent_child_relations pcr ON pcr.parent_id = reachable.member_id
                    WHERE pcr.genealogy_id = :genealogy_id
                      AND reachable.depth < :max_depth
                ),
                ranked AS (
                    SELECT member_id, MIN(depth) AS depth
                    FROM reachable
                    GROUP BY member_id
                ),
                tree_edges AS (
                    SELECT DISTINCT ON (pcr.child_id)
                        pcr.child_id AS member_id,
                        pcr.parent_id AS parent_id
                    FROM parent_child_relations pcr
                    JOIN ranked child_rank ON child_rank.member_id = pcr.child_id
                    JOIN ranked parent_rank ON parent_rank.member_id = pcr.parent_id
                    WHERE pcr.genealogy_id = :genealogy_id
                      AND child_rank.depth > 0
                      AND parent_rank.depth = child_rank.depth - 1
                    ORDER BY
                        pcr.child_id,
                        CASE WHEN pcr.parent_role = 'father' THEN 0 ELSE 1 END,
                        pcr.parent_id
                ),
                tree_rows AS (
                    SELECT ranked.member_id, NULL::BIGINT AS parent_id, ranked.depth
                    FROM ranked
                    WHERE ranked.member_id = CAST(:root_member_id AS BIGINT)
                    UNION ALL
                    SELECT ranked.member_id, tree_edges.parent_id, ranked.depth
                    FROM ranked
                    JOIN tree_edges ON tree_edges.member_id = ranked.member_id
                    WHERE ranked.member_id <> CAST(:root_member_id AS BIGINT)
                )
                SELECT tree_rows.parent_id, tree_rows.depth, members.*
                FROM tree_rows
                JOIN members ON members.id = tree_rows.member_id
                ORDER BY tree_rows.depth, members.birth_date NULLS LAST, members.id
                """
            ),
            {
                "root_member_id": root_member_id,
                "genealogy_id": genealogy_id,
                "max_depth": max_depth,
            },
        ).mappings()
    )
    if not rows:
        return TreePageRead(
            items=[],
            page=1,
            page_size=TREE_PREVIEW_PAGE_SIZE,
            page_nodes=0,
            total_nodes=0,
            total_pages=1,
        )

    root_row = rows[0]
    business_rows = rows[1:]
    total_pages = max(
        1,
        (len(business_rows) + TREE_PREVIEW_PAGE_SIZE - 1) // TREE_PREVIEW_PAGE_SIZE,
    )
    if page > total_pages:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"树形预览页码超出范围：第 {page} 页不存在，总页数为 {total_pages}。",
        )

    start = (page - 1) * TREE_PREVIEW_PAGE_SIZE
    end = start + TREE_PREVIEW_PAGE_SIZE
    page_rows = business_rows[start:end]
    rows_by_member_id = {row["id"]: row for row in rows}
    visible_member_ids = {root_row["id"]}

    # 分页按主体节点切片，但会自动补齐这些节点向上的祖先路径，保证每一页仍然是一棵可读的树。
    for row in page_rows:
        current_row = row
        while current_row is not None:
            visible_member_ids.add(current_row["id"])
            parent_id = current_row["parent_id"]
            current_row = rows_by_member_id.get(parent_id) if parent_id is not None else None

    visible_rows = [row for row in rows if row["id"] in visible_member_ids]
    return TreePageRead(
        items=build_tree_nodes(visible_rows),
        page=page,
        page_size=TREE_PREVIEW_PAGE_SIZE,
        page_nodes=len(page_rows),
        total_nodes=len(rows),
        total_pages=total_pages,
    )


@app.get("/genealogies/{genealogy_id}/relationship-path", response_model=RelationshipPathRead)
def relationship_path(
    genealogy_id: int,
    source_member_id: int,
    target_member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RelationshipPathRead:
    assert_genealogy_access(db, current_user, genealogy_id)
    if source_member_id == target_member_id:
        member = db.scalar(
            select(Member).where(
                Member.genealogy_id == genealogy_id,
                Member.id == source_member_id,
            )
        )
        if member is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="查询成员不存在")
        return RelationshipPathRead(
            connected=True,
            path_members=[member],
            relation_steps=[],
            depth=0,
        )

    member_count = db.scalar(
        select(func.count(Member.id)).where(
            Member.genealogy_id == genealogy_id,
            Member.id.in_([source_member_id, target_member_id]),
        )
    )
    if member_count != 2:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="查询成员不存在")

    graph = load_relationship_graph(db, genealogy_id)
    path = find_shortest_relationship_path(graph, source_member_id, target_member_id)
    if path is None:
        return RelationshipPathRead(connected=False)

    path_ids, relation_steps = path
    members = list(db.scalars(select(Member).where(Member.id.in_(path_ids))).all())
    member_by_id = {member.id: member for member in members}
    ordered_members = [
        member_by_id[member_id] for member_id in path_ids if member_id in member_by_id
    ]
    return RelationshipPathRead(
        connected=True,
        path_members=ordered_members,
        relation_steps=relation_steps,
        depth=len(relation_steps),
    )

    row = (
        db.execute(
            text(
                """
            WITH RECURSIVE edges AS (
                SELECT parent_id AS from_id, child_id AS to_id, 'parent_child' AS relation_type
                FROM parent_child_relations WHERE genealogy_id = :genealogy_id
                UNION ALL
                SELECT child_id, parent_id, 'child_parent'
                FROM parent_child_relations WHERE genealogy_id = :genealogy_id
                UNION ALL
                SELECT spouse_a_id, spouse_b_id, 'marriage'
                FROM marriages WHERE genealogy_id = :genealogy_id
                UNION ALL
                SELECT spouse_b_id, spouse_a_id, 'marriage'
                FROM marriages WHERE genealogy_id = :genealogy_id
            ),
            search AS (
                -- PostgreSQL 递归 CTE 要求锚点分支与递归分支列类型完全一致，这里显式转成 BIGINT。
                SELECT CAST(:source_member_id AS BIGINT) AS member_id,
                       ARRAY[CAST(:source_member_id AS BIGINT)] AS path_ids,
                       ARRAY[]::TEXT[] AS relation_steps,
                       0 AS depth
                UNION ALL
                SELECT edges.to_id,
                       search.path_ids || edges.to_id,
                       search.relation_steps || edges.relation_type,
                       search.depth + 1
                FROM search
                JOIN edges ON edges.from_id = search.member_id
                WHERE search.depth < 20
                  AND NOT edges.to_id = ANY(search.path_ids)
            )
            SELECT path_ids, relation_steps, depth
            FROM search
            WHERE member_id = :target_member_id
            ORDER BY depth
            LIMIT 1
            """
            ),
            {
                "genealogy_id": genealogy_id,
                "source_member_id": source_member_id,
                "target_member_id": target_member_id,
            },
        )
        .mappings()
        .first()
    )
    if row is None:
        return RelationshipPathRead(connected=False)

    path_ids = list(row["path_ids"])
    members = list(db.scalars(select(Member).where(Member.id.in_(path_ids))).all())
    member_by_id = {member.id: member for member in members}
    ordered_members = [
        member_by_id[member_id] for member_id in path_ids if member_id in member_by_id
    ]
    return RelationshipPathRead(
        connected=True,
        path_members=ordered_members,
        relation_steps=list(row["relation_steps"]),
        depth=row["depth"],
    )


def build_tree_nodes(rows: list[dict[str, Any]]) -> list[TreeNode]:
    nodes: dict[int, TreeNode] = {}
    roots: list[TreeNode] = []
    pending_children: dict[int, list[TreeNode]] = {}

    for row in rows:
        member = MemberRead.model_validate(dict(row))
        node = TreeNode(member=member, depth=row["depth"], children=[])
        nodes[member.id] = node
        for child in pending_children.pop(member.id, []):
            node.children.append(child)

        parent_id = row["parent_id"]
        if parent_id is None:
            roots.append(node)
        elif parent_id in nodes:
            nodes[parent_id].children.append(node)
        else:
            pending_children.setdefault(parent_id, []).append(node)
    return roots
