"""Users router — /api/users (Admin CRUD) and /api/users/me (self)."""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.middleware import get_current_user, require_admin
from app.database import get_db
from app.models.user import User, UserRole, UserStatus, ThemePreference
from app.models.user_audit_log import UserAuditLog, AuditAction

router = APIRouter(tags=["users"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _count_active_admins(db: AsyncSession, excluding_id: Optional[uuid.UUID] = None) -> int:
    q = select(func.count()).where(
        User.role == UserRole.admin,
        User.status == UserStatus.active,
    )
    if excluding_id is not None:
        q = q.where(User.id != excluding_id)
    result = await db.execute(q)
    return result.scalar_one()


async def _assert_active_admin_remains(db: AsyncSession, excluding_id: uuid.UUID) -> None:
    count = await _count_active_admins(db, excluding_id=excluding_id)
    if count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot perform this action: at least one active Admin must remain.",
        )


async def _write_audit_log(
    db: AsyncSession,
    actor_user_id: Optional[uuid.UUID],
    actor_email: str,
    target_user_id: Optional[uuid.UUID],
    target_email: str,
    action: AuditAction,
    before_value: Optional[dict],
    after_value: Optional[dict],
    ip_address: Optional[str],
) -> None:
    assert actor_user_id is not None or (
        await _count_active_admins(db) == 0
    ), "actor_user_id must be set for non-bootstrap operations"
    db.add(UserAuditLog(
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        target_user_id=target_user_id,
        target_email=target_email,
        action=action,
        before_value=before_value,
        after_value=after_value,
        ip_address=ip_address,
    ))


def _user_out(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "status": user.status.value,
        "theme_preference": user.theme_preference.value,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        "created_by": str(user.created_by) if user.created_by else None,
        "updated_by": str(user.updated_by) if user.updated_by else None,
        "last_selected_source_id": str(user.last_selected_source_id) if user.last_selected_source_id else None,
    }


# ---------------------------------------------------------------------------
# Self endpoints (any authenticated user)
# ---------------------------------------------------------------------------

@router.get("/users/me")
async def get_me(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.id == uuid.UUID(current_user["sub"])))
    user: User | None = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_out(user)


class PreferencesRequest(BaseModel):
    theme_preference: Optional[ThemePreference] = None
    last_selected_source_id: Optional[str] = None


@router.patch("/users/me/preferences")
async def update_my_preferences(
    body: PreferencesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.id == uuid.UUID(current_user["sub"])))
    user: User | None = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.theme_preference is not None:
        user.theme_preference = body.theme_preference
    if body.last_selected_source_id is not None:
        try:
            user.last_selected_source_id = uuid.UUID(body.last_selected_source_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid source ID")
    user.updated_at = datetime.utcnow()
    return _user_out(user)


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------

@router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    result = await db.execute(select(User).order_by(User.created_at.asc()))
    users = result.scalars().all()
    return [_user_out(u) for u in users]


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    role: UserRole = UserRole.viewer


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already in use")

    actor_id = uuid.UUID(current_user["sub"])
    new_user = User(
        email=body.email,
        hashed_password=pwd_context.hash(body.password),
        full_name=body.full_name,
        role=body.role,
        status=UserStatus.active,
        created_by=actor_id,
        updated_by=actor_id,
        password_updated_at=datetime.utcnow(),
    )
    db.add(new_user)
    await db.flush()

    await _write_audit_log(
        db,
        actor_user_id=actor_id,
        actor_email=current_user["email"],
        target_user_id=new_user.id,
        target_email=new_user.email,
        action=AuditAction.create,
        before_value=None,
        after_value={"email": new_user.email, "role": new_user.role.value, "status": new_user.status.value},
        ip_address=_get_ip(request),
    )
    return _user_out(new_user)


class ModifyUserRequest(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None
    password: Optional[str] = None


@router.patch("/users/{user_id}")
async def modify_user(
    user_id: uuid.UUID,
    body: ModifyUserRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    target: User | None = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    actor_id = uuid.UUID(current_user["sub"])
    ip = _get_ip(request)
    now = datetime.utcnow()

    # Role demotion or status disable: ensure an active admin remains
    would_demote = body.role is not None and body.role != UserRole.admin and target.role == UserRole.admin
    would_disable = body.status == UserStatus.disabled and target.status == UserStatus.active
    if (would_demote or would_disable) and target.role == UserRole.admin:
        await _assert_active_admin_remains(db, excluding_id=target.id)

    # Email uniqueness
    if body.email is not None and body.email != target.email:
        dup = await db.execute(select(User).where(User.email == body.email))
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already in use")

    # Apply changes and emit one audit entry per changed field
    if body.email is not None and body.email != target.email:
        old_email = target.email
        target.email = body.email
        target.updated_by = actor_id
        target.updated_at = now
        await _write_audit_log(
            db, actor_id, current_user["email"], target.id, target.email,
            AuditAction.modify_email,
            {"email": old_email}, {"email": target.email}, ip,
        )

    if body.role is not None and body.role != target.role:
        old_role = target.role.value
        target.role = body.role
        target.updated_by = actor_id
        target.updated_at = now
        await _write_audit_log(
            db, actor_id, current_user["email"], target.id, target.email,
            AuditAction.modify_role,
            {"role": old_role}, {"role": target.role.value}, ip,
        )

    if body.status is not None and body.status != target.status:
        old_status = target.status.value
        target.status = body.status
        target.updated_by = actor_id
        target.updated_at = now
        await _write_audit_log(
            db, actor_id, current_user["email"], target.id, target.email,
            AuditAction.modify_status,
            {"status": old_status}, {"status": target.status.value}, ip,
        )

    if body.password is not None:
        target.hashed_password = pwd_context.hash(body.password)
        target.password_updated_at = now
        target.updated_by = actor_id
        target.updated_at = now
        await _write_audit_log(
            db, actor_id, current_user["email"], target.id, target.email,
            AuditAction.reset_password,
            None, None, ip,
        )

    if body.full_name is not None:
        target.full_name = body.full_name
        target.updated_by = actor_id
        target.updated_at = now

    return _user_out(target)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    target: User | None = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target.role == UserRole.admin and target.status == UserStatus.active:
        await _assert_active_admin_remains(db, excluding_id=target.id)

    actor_id = uuid.UUID(current_user["sub"])
    await _write_audit_log(
        db, actor_id, current_user["email"],
        target.id, target.email,
        AuditAction.delete,
        {"email": target.email, "role": target.role.value, "status": target.status.value},
        None,
        _get_ip(request),
    )
    await db.flush()  # flush so audit log FK resolves before delete
    await db.delete(target)


# ---------------------------------------------------------------------------
# Audit log endpoint
# ---------------------------------------------------------------------------

@router.get("/users/audit-log")
async def get_audit_log(
    actor_id: Optional[str] = None,
    target_id: Optional[str] = None,
    action: Optional[AuditAction] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    q = select(UserAuditLog).order_by(UserAuditLog.timestamp.desc())

    if actor_id:
        try:
            q = q.where(UserAuditLog.actor_user_id == uuid.UUID(actor_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid actor_id")
    if target_id:
        try:
            q = q.where(UserAuditLog.target_user_id == uuid.UUID(target_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid target_id")
    if action:
        q = q.where(UserAuditLog.action == action)
    if date_from:
        try:
            q = q.where(UserAuditLog.timestamp >= datetime.fromisoformat(date_from))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_from format")
    if date_to:
        try:
            q = q.where(UserAuditLog.timestamp <= datetime.fromisoformat(date_to))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_to format")

    offset = (page - 1) * page_size
    q = q.offset(offset).limit(page_size)

    result = await db.execute(q)
    logs = result.scalars().all()

    return [
        {
            "id": str(log.id),
            "timestamp": log.timestamp.isoformat(),
            "actor_user_id": str(log.actor_user_id) if log.actor_user_id else None,
            "actor_email": log.actor_email,
            "target_user_id": str(log.target_user_id) if log.target_user_id else None,
            "target_email": log.target_email,
            "action": log.action.value,
            "before_value": log.before_value,
            "after_value": log.after_value,
            "ip_address": log.ip_address,
        }
        for log in logs
    ]
