from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    owned_genealogies: Mapped[list["Genealogy"]] = relationship(back_populates="owner")
    collaborations: Mapped[list["GenealogyCollaborator"]] = relationship(back_populates="user")


class Genealogy(Base):
    __tablename__ = "genealogies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    surname: Mapped[str] = mapped_column(String(32), nullable=False)
    revision_time: Mapped[object | None] = mapped_column(Date, nullable=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    owner: Mapped[User] = relationship(back_populates="owned_genealogies")
    collaborators: Mapped[list["GenealogyCollaborator"]] = relationship(
        back_populates="genealogy",
        cascade="all, delete-orphan",
    )
    members: Mapped[list["Member"]] = relationship(back_populates="genealogy")


class GenealogyCollaborator(Base):
    __tablename__ = "genealogy_collaborators"
    __table_args__ = (
        CheckConstraint("role IN ('editor', 'viewer')", name="ck_genealogy_collaborators_role"),
        UniqueConstraint("genealogy_id", "user_id", name="ux_genealogy_collaborators"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    genealogy_id: Mapped[int] = mapped_column(ForeignKey("genealogies.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="editor")
    invited_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    genealogy: Mapped[Genealogy] = relationship(back_populates="collaborators")
    user: Mapped[User] = relationship(back_populates="collaborations")


class Member(Base):
    __tablename__ = "members"
    __table_args__ = (
        CheckConstraint("gender IN ('male', 'female', 'unknown')", name="ck_members_gender"),
        CheckConstraint(
            "birth_date IS NULL OR death_date IS NULL OR death_date >= birth_date",
            name="ck_members_life_dates",
        ),
        CheckConstraint("generation_index >= 1", name="ck_members_generation"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    genealogy_id: Mapped[int] = mapped_column(ForeignKey("genealogies.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    gender: Mapped[str] = mapped_column(String(16), nullable=False)
    birth_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    death_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    generation_index: Mapped[int] = mapped_column(Integer, nullable=False)
    biography: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    genealogy: Mapped[Genealogy] = relationship(back_populates="members")


class ParentChildRelation(Base):
    __tablename__ = "parent_child_relations"
    __table_args__ = (
        CheckConstraint("parent_role IN ('father', 'mother')", name="ck_parent_child_role"),
        CheckConstraint("parent_id <> child_id", name="ck_parent_child_not_self"),
        UniqueConstraint("parent_id", "child_id", "parent_role", name="ux_parent_child_role"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    genealogy_id: Mapped[int] = mapped_column(ForeignKey("genealogies.id", ondelete="CASCADE"))
    parent_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"))
    child_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"))
    parent_role: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Marriage(Base):
    __tablename__ = "marriages"
    __table_args__ = (
        CheckConstraint("spouse_a_id <> spouse_b_id", name="ck_marriages_not_self"),
        CheckConstraint("status IN ('active', 'ended')", name="ck_marriages_status"),
        CheckConstraint(
            "start_date IS NULL OR end_date IS NULL OR end_date >= start_date",
            name="ck_marriages_dates",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    genealogy_id: Mapped[int] = mapped_column(ForeignKey("genealogies.id", ondelete="CASCADE"))
    spouse_a_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"))
    spouse_b_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"))
    start_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
