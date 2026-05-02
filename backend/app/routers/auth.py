from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.auth import authenticate_user, create_access_token, get_current_user, get_db, get_password_hash
from backend.app.models import User
from backend.app.schemas import AuthResponse, CurrentUserResponse, LoginRequest, RegisterRequest
from backend.app.utils import normalize_name

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    username = normalize_name(request.username)
    password = (request.password or "").strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required")

    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=409, detail="Username already exists")

    user = User(username=username, password_hash=get_password_hash(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return AuthResponse(access_token=create_access_token(user), username=user.username)


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, normalize_name(request.username), request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return AuthResponse(access_token=create_access_token(user), username=user.username)


@router.get("/me", response_model=CurrentUserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
