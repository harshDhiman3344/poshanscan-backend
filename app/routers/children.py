from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.child import Child
from app.schemas.child import ChildCreate, ChildResponse

router = APIRouter(prefix="/children", tags=["Children"])


@router.get("/search", response_model=List[ChildResponse])
def search_children(
    q: Optional[str] = Query("", description="Search term for name, guardian, village, or ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Search child records by name, guardian, village, or child ID.
    Matches Navya's GET /children/search?q=
    """
    query = db.query(Child)
    if q:
        search_pattern = f"%{q.strip().lower()}%"
        query = query.filter(
            or_(
                Child.name.ilike(search_pattern),
                Child.guardian_name.ilike(search_pattern),
                Child.village.ilike(search_pattern),
                Child.id.ilike(search_pattern),
            )
        )
    
    results = query.limit(30).all()
    return [
        ChildResponse(
            child_id=c.id,
            name=c.name,
            dob=c.dob,
            gender=c.gender,
            guardian_name=c.guardian_name,
            village=c.village,
        )
        for c in results
    ]


@router.post("", response_model=ChildResponse, status_code=status.HTTP_201_CREATED)
def register_child(
    child_in: ChildCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Register a new child in the system.
    Matches Navya's POST /children
    """
    new_child = Child(
        name=child_in.name,
        dob=child_in.dob,
        gender=child_in.gender,
        guardian_name=child_in.guardian_name,
        village=child_in.village,
        registered_by=current_user.id,
        location_id=current_user.location_id,
    )
    db.add(new_child)
    db.commit()
    db.refresh(new_child)

    return ChildResponse(
        child_id=new_child.id,
        name=new_child.name,
        dob=new_child.dob,
        gender=new_child.gender,
        guardian_name=new_child.guardian_name,
        village=new_child.village,
    )


@router.get("/{child_id}", response_model=ChildResponse)
def get_child(
    child_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch single child record by ID."""
    child = db.query(Child).filter(Child.id == child_id).first()
    if not child:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Child not found",
        )
    return ChildResponse(
        child_id=child.id,
        name=child.name,
        dob=child.dob,
        gender=child.gender,
        guardian_name=child.guardian_name,
        village=child.village,
    )
