from fastapi import HTTPException, status
from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from app.models import Genealogy, GenealogyCollaborator, Member, User


def get_genealogy_or_404(db: Session, genealogy_id: int) -> Genealogy:
    genealogy = db.get(Genealogy, genealogy_id)
    if genealogy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="族谱不存在")
    return genealogy


def assert_genealogy_access(
    db: Session,
    user: User,
    genealogy_id: int,
    *,
    write: bool = False,
    owner_only: bool = False,
) -> Genealogy:
    genealogy = get_genealogy_or_404(db, genealogy_id)
    if user.is_admin:
        return genealogy
    if genealogy.owner_user_id == user.id:
        return genealogy
    if owner_only:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅族谱创建者可操作")

    allowed_roles = ["editor"] if write else ["editor", "viewer"]
    collaborator_exists = db.scalar(
        select(
            exists().where(
                GenealogyCollaborator.genealogy_id == genealogy_id,
                GenealogyCollaborator.user_id == user.id,
                GenealogyCollaborator.role.in_(allowed_roles),
            )
        )
    )
    if collaborator_exists:
        return genealogy
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该族谱")


def accessible_genealogies_query(user: User):
    if user.is_admin:
        return select(Genealogy)
    return select(Genealogy).where(
        or_(
            Genealogy.owner_user_id == user.id,
            Genealogy.collaborators.any(GenealogyCollaborator.user_id == user.id),
        )
    )


def get_member_with_access(
    db: Session,
    user: User,
    member_id: int,
    *,
    write: bool = False,
) -> Member:
    member = db.get(Member, member_id)
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="成员不存在")
    assert_genealogy_access(db, user, member.genealogy_id, write=write)
    return member
