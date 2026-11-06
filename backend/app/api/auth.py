from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import Token, UserCreate, UserLogin, UserResponse
from app.services.auth_service import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)


router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user_data.email).first() is not None:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(email=user_data.email, hashed_password=get_password_hash(user_data.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Handle concurrent registrations for the same unique email as well.
        db.rollback()
        raise HTTPException(status_code=400, detail="Email already registered") from None
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(user_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_data.email).first()
    hashed_password = user.hashed_password if user is not None else DUMMY_PASSWORD_HASH
    password_valid = verify_password(user_data.password, hashed_password)
    if user is None or not password_valid or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(data={"sub": user.email}))


@router.get("/me", response_model=UserResponse)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user
