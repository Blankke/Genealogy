from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    is_admin: bool
    created_at: datetime


class GenealogyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    surname: str = Field(min_length=1, max_length=32)
    revision_time: date | None = None


class GenealogyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    surname: str | None = Field(default=None, min_length=1, max_length=32)
    revision_time: date | None = None


class GenealogyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    surname: str
    revision_time: date | None
    owner_user_id: int
    created_at: datetime


class InviteRequest(BaseModel):
    email: EmailStr
    role: str = Field(default="editor", pattern="^(editor|viewer)$")


class MemberCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    gender: str = Field(pattern="^(male|female|unknown)$")
    birth_date: date | None = None
    death_date: date | None = None
    generation_index: int = Field(ge=1)
    biography: str = ""


class MemberUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    gender: str | None = Field(default=None, pattern="^(male|female|unknown)$")
    birth_date: date | None = None
    death_date: date | None = None
    generation_index: int | None = Field(default=None, ge=1)
    biography: str | None = None


class MemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    genealogy_id: int
    name: str
    gender: str
    birth_date: date | None
    death_date: date | None
    generation_index: int
    biography: str
    created_at: datetime


class ParentChildCreate(BaseModel):
    parent_id: int
    child_id: int
    parent_role: str = Field(pattern="^(father|mother)$")


class MarriageCreate(BaseModel):
    spouse_a_id: int
    spouse_b_id: int
    start_date: date | None = None
    end_date: date | None = None
    status: str = Field(default="active", pattern="^(active|ended)$")


class DashboardRead(BaseModel):
    genealogy_id: int
    total_members: int
    male_count: int
    female_count: int
    unknown_count: int


class AdminDashboardRead(BaseModel):
    total_users: int
    total_genealogies: int
    total_members: int
    male_count: int
    female_count: int
    unknown_count: int
    total_parent_child_relations: int
    total_marriages: int


class FamilyRead(BaseModel):
    member: MemberRead
    spouses: list[MemberRead]
    children: list[MemberRead]


class AncestorRead(BaseModel):
    depth: int
    parent_role: str
    member: MemberRead


class TreeNode(BaseModel):
    member: MemberRead
    depth: int
    children: list["TreeNode"] = Field(default_factory=list)


class RelationshipPathRead(BaseModel):
    connected: bool
    path_members: list[MemberRead] = []
    relation_steps: list[str] = []
    depth: int = 0
