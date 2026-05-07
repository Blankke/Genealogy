from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import case, func, or_, select, text
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
    AncestorRead,
    DashboardRead,
    FamilyRead,
    GenealogyCreate,
    GenealogyRead,
    GenealogyUpdate,
    InviteRequest,
    LoginRequest,
    MarriageCreate,
    MemberCreate,
    MemberRead,
    MemberUpdate,
    ParentChildCreate,
    RegisterRequest,
    RelationshipPathRead,
    TokenResponse,
    TreeNode,
    UserRead,
)
from app.security import create_access_token, hash_password, verify_password
from app.services import (
    accessible_genealogies_query,
    assert_genealogy_access,
    get_member_with_access,
)

app = FastAPI(title="族谱管理系统 API", version="0.1.0")

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


@app.get("/genealogies/{genealogy_id}/members", response_model=list[MemberRead])
def list_members(
    genealogy_id: int,
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Member]:
    assert_genealogy_access(db, current_user, genealogy_id)
    statement = select(Member).where(Member.genealogy_id == genealogy_id)
    if search:
        statement = statement.where(Member.name.ilike(f"%{search}%"))
    statement = statement.order_by(Member.generation_index, Member.id).limit(limit).offset(offset)
    return list(db.scalars(statement).all())


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
    if (
        parent is None
        or child is None
        or parent.genealogy_id != genealogy_id
        or child.genealogy_id != genealogy_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="亲子关系成员不属于该族谱",
        )
    relation = ParentChildRelation(genealogy_id=genealogy_id, **payload.model_dump())
    db.add(relation)
    db.commit()
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
        text(
            """
            WITH RECURSIVE ancestors AS (
                SELECT pcr.parent_id AS member_id, pcr.parent_role, 1 AS depth,
                       ARRAY[pcr.child_id, pcr.parent_id] AS path
                FROM parent_child_relations pcr
                WHERE pcr.child_id = :member_id AND pcr.genealogy_id = :genealogy_id
                UNION ALL
                SELECT pcr.parent_id, pcr.parent_role, ancestors.depth + 1,
                       ancestors.path || pcr.parent_id
                FROM parent_child_relations pcr
                JOIN ancestors ON ancestors.member_id = pcr.child_id
                WHERE pcr.genealogy_id = :genealogy_id
                  AND NOT pcr.parent_id = ANY(ancestors.path)
            )
            SELECT ancestors.depth, ancestors.parent_role, members.*
            FROM ancestors
            JOIN members ON members.id = ancestors.member_id
            ORDER BY ancestors.depth, members.id
            """
        ),
        {"member_id": member_id, "genealogy_id": member.genealogy_id},
    ).mappings()
    return [
        AncestorRead(
            depth=row["depth"],
            parent_role=row["parent_role"],
            member=MemberRead.model_validate(dict(row)),
        )
        for row in rows
    ]


@app.get("/genealogies/{genealogy_id}/tree", response_model=list[TreeNode])
def get_descendant_tree(
    genealogy_id: int,
    root_member_id: int | None = None,
    max_depth: int = Query(default=5, ge=1, le=12),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TreeNode]:
    assert_genealogy_access(db, current_user, genealogy_id)
    if root_member_id is None:
        root_member_id = db.scalar(
            select(Member.id)
            .where(Member.genealogy_id == genealogy_id)
            .order_by(Member.generation_index, Member.birth_date, Member.id)
            .limit(1)
        )
    if root_member_id is None:
        return []

    rows = list(
        db.execute(
            text(
                """
                WITH RECURSIVE descendants AS (
                    SELECT id AS member_id, NULL::BIGINT AS parent_id, 0 AS depth
                    FROM members
                    WHERE id = :root_member_id AND genealogy_id = :genealogy_id
                    UNION ALL
                    SELECT child.id, pcr.parent_id, descendants.depth + 1
                    FROM descendants
                    JOIN parent_child_relations pcr ON pcr.parent_id = descendants.member_id
                    JOIN members child ON child.id = pcr.child_id
                    WHERE pcr.genealogy_id = :genealogy_id
                      AND descendants.depth < :max_depth
                )
                SELECT descendants.parent_id, descendants.depth, members.*
                FROM descendants
                JOIN members ON members.id = descendants.member_id
                ORDER BY descendants.depth, members.birth_date NULLS LAST, members.id
                """
            ),
            {
                "root_member_id": root_member_id,
                "genealogy_id": genealogy_id,
                "max_depth": max_depth,
            },
        ).mappings()
    )
    return build_tree_nodes(rows)


@app.get("/genealogies/{genealogy_id}/relationship-path", response_model=RelationshipPathRead)
def relationship_path(
    genealogy_id: int,
    source_member_id: int,
    target_member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RelationshipPathRead:
    assert_genealogy_access(db, current_user, genealogy_id)
    member_count = db.scalar(
        select(func.count(Member.id)).where(
            Member.genealogy_id == genealogy_id,
            Member.id.in_([source_member_id, target_member_id]),
        )
    )
    if member_count != 2:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="查询成员不存在")

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
                SELECT :source_member_id AS member_id,
                       ARRAY[:source_member_id] AS path_ids,
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
