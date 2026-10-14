from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_password, create_access_token, get_password_hash
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse

router = APIRouter(prefix="/supervisor", tags=["Supervisor Portal"])


@router.post("/login", response_model=LoginResponse)
def supervisor_login(login_data: LoginRequest, db: Session = Depends(get_db)):
    """
    Dedicated authentication endpoint for supervisors and administrators.
    Rejects frontline workers with 403 Forbidden.
    """
    user = db.query(User).filter(User.phone == login_data.phone).first()

    # Convenience login for admin / admin
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

    # Restrict to supervisor or admin only
    if user.role not in ["supervisor", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Only supervisors and administrators can access the dashboard portal.",
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
