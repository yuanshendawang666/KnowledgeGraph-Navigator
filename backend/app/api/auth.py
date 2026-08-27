"""
用户认证 API 路由
------------------
提供 JWT 注册、登录功能，以及获取当前用户信息的依赖注入。

端点：
- POST /api/auth/register  — 用户注册
- POST /api/auth/login     — 用户登录
- GET  /api/auth/me        — 获取当前用户信息
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models import User, UserRole

settings = get_settings()

router = APIRouter(prefix="/api/auth", tags=["认证"])

# ---- 密码加密 & JWT 配置 ----

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def create_access_token(data: dict) -> str:
    """创建 JWT access token"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    try:
        # bcrypt 限制密码最长 72 字节，超长则截断
        return bcrypt.checkpw(
            plain_password.encode("utf-8")[:72],
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    return bcrypt.hashpw(
        password.encode("utf-8")[:72],
        bcrypt.gensalt(),
    ).decode("utf-8")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    依赖注入：从 JWT token 中解析并返回当前登录用户。
    在所有需要认证的 API 端点中使用。
    """
    import logging
    logger = logging.getLogger("auth")
    logging.basicConfig(level=logging.INFO)

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        logger.info(f"[AUTH] Token received: {token[:30]}... (len={len(token)})")
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        logger.info(f"[AUTH] Decode success, payload keys: {list(payload.keys())}")
        user_id: int = int(payload.get("sub"))
        logger.info(f"[AUTH] user_id from token: {user_id}")
        if user_id is None:
            logger.warning("[AUTH] user_id is None in token payload")
            raise credentials_exception
    except JWTError as e:
        logger.error(f"[AUTH] JWT decode failed: {type(e).__name__}: {e}")
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        logger.warning(f"[AUTH] User {user_id} not found in DB")
        raise credentials_exception
    logger.info(f"[AUTH] Authenticated user: {user.username}")
    return user


# ---- 请求/响应模型 ----

class UserRegister(BaseModel):
    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, max_length=72, description="密码（6-72字符）")
    role: UserRole = UserRole.STUDENT


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: UserRole
    major: str = ""
    grade: str = ""
    learning_goal: str = ""

    class Config:
        from_attributes = True


class ProfileUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    major: Optional[str] = None
    grade: Optional[str] = None
    learning_goal: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ---- 路由端点 ----

@router.post("/register", response_model=TokenResponse, status_code=201)
def register(data: UserRegister, db: Session = Depends(get_db)):
    """用户注册"""
    # 检查用户名是否已存在
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(
            status_code=400, detail="用户名已被注册"
        )

    # 检查邮箱是否已存在
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(
            status_code=400, detail="邮箱已被注册"
        )

    # 创建用户
    user = User(
        username=data.username,
        email=data.email,
        hashed_password=get_password_hash(data.password),
        role=data.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # 生成 token (sub 必须是字符串)
    token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
def login(data: UserLogin, db: Session = Depends(get_db)):
    """用户登录"""
    user = db.query(User).filter(User.username == data.username).first()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=401, detail="用户名或密码错误"
        )

    token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return UserResponse.model_validate(current_user)


@router.put("/me", response_model=UserResponse)
def update_me(
    data: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新当前用户的画像信息（用户名/邮箱/专业/年级/学习目标）。"""
    if data.username is not None:
        if data.username != current_user.username:
            if db.query(User).filter(User.username == data.username).first():
                raise HTTPException(status_code=400, detail="用户名已被占用")
        current_user.username = data.username
    if data.email is not None:
        if data.email != current_user.email:
            if db.query(User).filter(User.email == data.email).first():
                raise HTTPException(status_code=400, detail="邮箱已被注册")
        current_user.email = data.email
    if data.major is not None:
        current_user.major = data.major
    if data.grade is not None:
        current_user.grade = data.grade
    if data.learning_goal is not None:
        current_user.learning_goal = data.learning_goal

    db.commit()
    db.refresh(current_user)
    return UserResponse.model_validate(current_user)
