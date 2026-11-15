from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_password, create_access_token, get_password_hash
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, LoginResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
def register(register_data: RegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new frontline worker or supervisor.
    Validates phone uniqueness, hashes password, saves record,
    and returns auth tokens for immediate login.
    """
    clean_phone = register_data.phone.strip()
    existing_user = db.query(User).filter(User.phone == clean_phone).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this phone number already exists.",
        )

    clean_name = register_data.name.strip() if register_data.name and register_data.name.strip() else None
    if not clean_name:
        last_digits = clean_phone[-4:] if len(clean_phone) >= 4 else clean_phone
        clean_name = f"Worker {last_digits}"

    role = register_data.role if register_data.role in ["worker", "supervisor", "admin"] else "worker"

    new_user = User(
        name=clean_name,
        phone=clean_phone,
        password_hash=get_password_hash(register_data.password),
        role=role,
        location_id=register_data.location_id,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_access_token(
        data={"sub": new_user.id, "role": new_user.role, "phone": new_user.phone}
    )

    return LoginResponse(
        access_token=token,
        token=token,
        role=new_user.role,
        name=new_user.name,
        user_id=new_user.id,
    )


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
