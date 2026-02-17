from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.security import (
    get_password_hash,
    create_access_token,
    authenticate_user,
    get_current_active_user,
    oauth2_scheme,
)
from ...models.user import User, Role
from ...schemas.auth import (
    Token,
    UserCreate,
    UserResponse,
    LoginRequest,
    UserUpdate,
    ChangePassword,
    PasswordResetRequest,
    PasswordResetConfirm,
)
from ...config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Register a new user."""
    # Check if user already exists
    existing_user = await db.execute(
        select(User).where(User.email == user_in.email)
    )
    if existing_user.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    # Create new user
    hashed_password = get_password_hash(user_in.password)
    db_user = User(
        email=user_in.email,
        hashed_password=hashed_password,
        full_name=user_in.full_name,
        is_active=True,
        is_verified=False,  # Email verification would be set up here
    )
    
    # Add default user role
    default_role = await db.execute(
        select(Role).where(Role.name == "user")
    )
    if default_role.scalar_one_or_none() is None:
        # Create default roles if they don't exist
        admin_role = Role(name="admin", description="Administrator")
        user_role = Role(name="user", description="Regular user")
        db.add_all([admin_role, user_role])
        await db.commit()
        await db.refresh(user_role)
        db_user.roles.append(user_role)
    else:
        db_user.roles.append(default_role.scalar_one())
    
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    
    # In a real app, send verification email here
    
    return db_user

@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """OAuth2 compatible token login, get an access token for future requests."""
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )
    
    # Update last login time
    user.last_login = datetime.utcnow()
    db.add(user)
    await db.commit()
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, 
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": int(access_token_expires.total_seconds()),
    }

@router.get("/me", response_model=UserResponse)
async def read_users_me(
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """Get current user."""
    return current_user

@router.put("/me", response_model=UserResponse)
async def update_user_me(
    user_in: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Update current user."""
    update_data = user_in.dict(exclude_unset=True)
    
    # Handle password update
    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
    
    # Update user fields
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    current_user.updated_at = datetime.utcnow()
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    
    return current_user

@router.post("/password/change", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    password_data: ChangePassword,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Change current user's password."""
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    
    current_user.hashed_password = get_password_hash(password_data.new_password)
    current_user.updated_at = datetime.utcnow()
    
    db.add(current_user)
    await db.commit()

@router.post("/password/reset/request", status_code=status.HTTP_202_ACCEPTED)
async def request_password_reset(
    email_data: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Request password reset."""
    # In a real app, you would send a password reset email
    # This is just a placeholder
    return {"message": "If your email is registered, you will receive a password reset link"}

@router.post("/password/reset/confirm", status_code=status.HTTP_200_OK)
async def reset_password_confirm(
    reset_data: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Confirm password reset with token."""
    # In a real app, you would validate the token and reset the password
    # This is just a placeholder
    return {"message": "Password has been reset successfully"}
