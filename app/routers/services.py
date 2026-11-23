from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.errors import ProblemException
from app.models import Service, User
from app.schemas import ServiceCreate, ServiceOut, ServiceUpdate
from app.security import require_manager

router = APIRouter(prefix="/api/services", tags=["Каталог послуг"])


@router.get("", response_model=list[ServiceOut])
def list_services(
    category: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[ServiceOut]:
    stmt = select(Service).order_by(Service.id.asc())
    if not include_inactive:
        stmt = stmt.where(Service.is_active.is_(True))
    if category:
        stmt = stmt.where(Service.category == category)

    services = db.scalars(stmt).all()
    return [ServiceOut.model_validate(item) for item in services]


@router.post("", response_model=ServiceOut, status_code=201)
def create_service(
    payload: ServiceCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> ServiceOut:
    service = Service(
        title=payload.title.strip(),
        category=payload.category,
        description=payload.description.strip(),
        base_price=payload.base_price,
        estimated_hours=payload.estimated_hours,
        is_active=payload.is_active,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return ServiceOut.model_validate(service)


@router.patch("/{service_id}", response_model=ServiceOut)
def update_service(
    service_id: int,
    payload: ServiceUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> ServiceOut:
    service = db.get(Service, service_id)
    if service is None:
        raise ProblemException(
            status_code=404,
            title="Послугу не знайдено",
            detail=f"Послуга з ідентифікатором {service_id} відсутня в каталозі.",
        )

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if isinstance(value, str):
            value = value.strip()
        setattr(service, field, value)

    db.commit()
    db.refresh(service)
    return ServiceOut.model_validate(service)