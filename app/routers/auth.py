from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_password, create_access_token
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse)
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate worker, supervisor, or admin.
    Compatible with both Navya's Worker PWA and Dhruv's Supervisor Dashboard.
    """
    user = db.query(User).filter(User.phone == login_data.phone).first()

    # Also support admin / admin convenience login from Dhruv's dashboard
    if not user and login_data.phone.lower() == "admin" and login_data.password == "admin":
        user = db.query(User).filter(User.role.in_(["supervisor", "admin"])).first()
        if not user:
            user = User(
                id="admin-001",
                name="Admin Supervisor",
                phone="admin",
                password_hash=get_password_hash("admin"),
                role="admin",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
    elif not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect phone number or password.",
        )

    token = create_access_token(
        data={"sub": user.id, "role": user.role, "phone": user.phone}
    )

    return LoginResponse(
        access_token=token,
        token=token,
        role=user.role,
        name=user.name,
        user_id=user.id,
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Retrieve profile of current authenticated user."""
    return current_user
