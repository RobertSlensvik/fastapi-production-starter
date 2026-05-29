"""Example users CRUD — demonstrates auth + DB patterns for new resources."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select

from app.api.deps import CurrentUser, SessionDep, SuperUser
from app.auth.password import hash_password
from app.core.errors import ConflictError, NotFoundError
from app.db.models.user import User

router = APIRouter()


# ─── Schemas ────────────────────────────────────────────────────────────────


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = None


class UserUpdate(BaseModel):
    full_name: str | None = None
    is_active: bool | None = None


class UserOut(BaseModel):
    id: str
    email: EmailStr
    full_name: str | None
    is_active: bool
    is_superuser: bool

    @classmethod
    def from_orm_user(cls, u: User) -> "UserOut":
        return cls(
            id=str(u.id),
            email=u.email,  # type: ignore[arg-type]
            full_name=u.full_name,
            is_active=u.is_active,
            is_superuser=u.is_superuser,
        )


class UserListResponse(BaseModel):
    items: list[UserOut]
    total: int


# ─── Routes ─────────────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user (superuser only)",
)
async def create_user(
    payload: UserCreate,
    session: SessionDep,
    _: SuperUser,
) -> UserOut:
    existing = await session.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError("Email already registered")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
    )
    session.add(user)
    await session.flush()
    return UserOut.from_orm_user(user)


@router.get("", response_model=UserListResponse, summary="List users (paginated)")
async def list_users(
    session: SessionDep,
    _: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> UserListResponse:
    total = (await session.execute(select(func.count()).select_from(User))).scalar_one()
    result = await session.execute(
        select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    )
    users = result.scalars().all()
    return UserListResponse(items=[UserOut.from_orm_user(u) for u in users], total=total)


@router.get("/{user_id}", response_model=UserOut, summary="Get one user by id")
async def get_user(
    user_id: uuid.UUID,
    session: SessionDep,
    _: CurrentUser,
) -> UserOut:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFoundError(f"User {user_id} not found")
    return UserOut.from_orm_user(user)


@router.patch("/{user_id}", response_model=UserOut, summary="Update a user")
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    session: SessionDep,
    _: SuperUser,
) -> UserOut:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFoundError(f"User {user_id} not found")

    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.is_active is not None:
        user.is_active = payload.is_active

    await session.flush()
    return UserOut.from_orm_user(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a user")
async def delete_user(
    user_id: uuid.UUID,
    session: SessionDep,
    _: SuperUser,
) -> None:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFoundError(f"User {user_id} not found")
    await session.delete(user)
