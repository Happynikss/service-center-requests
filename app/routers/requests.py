from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload
from app.database import get_db
from app.errors import ProblemException
from app.models import RepairRequest, RequestComment, RequestStatusHistory, Service, User
from app.schemas import (
    CommentCreate,
    CommentOut,
    DashboardStatsOut,
    ManagerRequestUpdate,
    RequestCreate,
    RequestDetailOut,
    RequestSummaryOut,
    StatusHistoryOut,
)
from app.security import get_current_user, get_optional_user, require_manager
from app.sla import (
    ALLOWED_TRANSITIONS,
    STATUS_LABELS,
    TERMINAL_STATUSES,
    calculate_initial_sla,
    evaluate_sla,
    validate_status_transition,
)

router = APIRouter(prefix="/api/requests", tags=["Заявки на ремонт та SLA"])


def _generate_tracking_code(db: Session) -> str:
    year = datetime.now(timezone.utc).year
    last_id = db.scalar(select(RepairRequest.id).order_by(RepairRequest.id.desc()).limit(1)) or 0
    seq = last_id + 1
    while True:
        candidate = f"SC-{year}-{seq:04d}"
        exists = db.scalar(select(RepairRequest.id).where(RepairRequest.tracking_code == candidate))
        if exists is None:
            return candidate
        seq += 1


def _to_summary(req: RepairRequest) -> RequestSummaryOut:
    sla = evaluate_sla(req.status, req.sla_deadline)
    return RequestSummaryOut(
        id=req.id,
        tracking_code=req.tracking_code,
        service_id=req.service_id,
        service_title=req.service.title if req.service else "Послуга",
        contact_name=req.contact_name,
        contact_phone=req.contact_phone,
        device_type=req.device_type,
        device_model=req.device_model,
        priority=req.priority,
        status=req.status,
        status_label=STATUS_LABELS.get(req.status, req.status),
        sla_deadline=req.sla_deadline,
        is_overdue=bool(sla["is_overdue"]),
        sla_state=str(sla["sla_state"]),
        remaining_minutes=sla["remaining_minutes"] if isinstance(sla["remaining_minutes"], int) else None,
        estimated_cost=req.estimated_cost,
        created_at=req.created_at,
        updated_at=req.updated_at,
    )


def _to_detail(req: RepairRequest, include_internal_comments: bool) -> RequestDetailOut:
    summary = _to_summary(req)
    history_items = [
        StatusHistoryOut(
            id=h.id,
            old_status=h.old_status,
            new_status=h.new_status,
            new_status_label=STATUS_LABELS.get(h.new_status, h.new_status),
            comment=h.comment,
            changed_by_name=h.author.full_name if h.author else "Система / Клієнт",
            changed_at=h.changed_at,
        )
        for h in req.status_history
    ]
    visible_comments = [
        CommentOut(
            id=c.id,
            author_name=c.author.full_name if c.author else "Користувач",
            author_role=c.author.role if c.author else "client",
            body=c.body,
            is_internal=c.is_internal,
            created_at=c.created_at,
        )
        for c in req.comments
        if include_internal_comments or not c.is_internal
    ]
    next_statuses = sorted(ALLOWED_TRANSITIONS.get(req.status, set()))
    return RequestDetailOut(
        **summary.model_dump(),
        client_id=req.client_id,
        contact_email=req.contact_email,
        problem_description=req.problem_description,
        closed_at=req.closed_at,
        allowed_next_statuses=next_statuses,  # type: ignore[arg-type]
        status_history=history_items,
        comments=visible_comments,
    )


def _load_request_full(db: Session, request_id: int) -> RepairRequest:
    stmt = (
        select(RepairRequest)
        .options(
            selectinload(RepairRequest.service),
            selectinload(RepairRequest.status_history).selectinload(RequestStatusHistory.author),
            selectinload(RepairRequest.comments).selectinload(RequestComment.author),
        )
        .where(RepairRequest.id == request_id)
    )
    req = db.scalar(stmt)
    if req is None:
        raise ProblemException(
            status_code=404,
            title="Заявку не знайдено",
            detail=f"Звернення з номером #{request_id} не існує в базі даних.",
        )
    return req


@router.post("", response_model=RequestDetailOut, status_code=201)
def create_request(
    payload: RequestCreate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> RequestDetailOut:
    service = db.get(Service, payload.service_id)
    if service is None or not service.is_active:
        raise ProblemException(
            status_code=404,
            title="Обрана послуга недоступна",
            detail="Вказана послуга не знайдена або тимчасово виведена з прайс-листа.",
        )

    now = datetime.now(timezone.utc)
    tracking_code = _generate_tracking_code(db)
    sla_deadline = calculate_initial_sla(service.estimated_hours, payload.priority, base_time=now)

    req = RepairRequest(
        tracking_code=tracking_code,
        client_id=current_user.id if (current_user and current_user.role == "client") else None,
        service_id=service.id,
        contact_name=payload.contact_name.strip(),
        contact_phone=payload.contact_phone.strip(),
        contact_email=str(payload.contact_email).lower() if payload.contact_email else (
            current_user.email if current_user else None
        ),
        device_type=payload.device_type.strip(),
        device_model=payload.device_model.strip(),
        problem_description=payload.problem_description.strip(),
        priority=payload.priority,
        status="new",
        sla_deadline=sla_deadline,
        estimated_cost=service.base_price,
    )
    db.add(req)
    db.flush()

    history = RequestStatusHistory(
        request_id=req.id,
        changed_by=current_user.id if current_user else None,
        old_status=None,
        new_status="new",
        comment="Заявку зареєстровано в системі.",
    )
    db.add(history)
    db.commit()

    full_req = _load_request_full(db, req.id)
    is_mgr = bool(current_user and current_user.role == "manager")
    return _to_detail(full_req, include_internal_comments=is_mgr)


@router.get("/track/{tracking_code}", response_model=RequestDetailOut)
def track_request_by_code(
    tracking_code: str,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> RequestDetailOut:
    normalized_code = tracking_code.strip().upper()
    stmt = (
        select(RepairRequest)
        .options(
            selectinload(RepairRequest.service),
            selectinload(RepairRequest.status_history).selectinload(RequestStatusHistory.author),
            selectinload(RepairRequest.comments).selectinload(RequestComment.author),
        )
        .where(RepairRequest.tracking_code == normalized_code)
    )
    req = db.scalar(stmt)
    if req is None:
        raise ProblemException(
            status_code=404,
            title="Звернення за трек-номером не знайдено",
            detail=f"Перевірте правильність введення номера «{normalized_code}».",
        )

    is_mgr = bool(current_user and current_user.role == "manager")
    return _to_detail(req, include_internal_comments=is_mgr)


@router.get("/my", response_model=list[RequestSummaryOut])
def list_my_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RequestSummaryOut]:
    stmt = (
        select(RepairRequest)
        .options(selectinload(RepairRequest.service))
        .where(RepairRequest.client_id == current_user.id)
        .order_by(RepairRequest.created_at.desc())
    )
    items = db.scalars(stmt).all()
    return [_to_summary(item) for item in items]


@router.get("/stats", response_model=DashboardStatsOut)
def get_manager_stats(
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> DashboardStatsOut:
    items = db.scalars(select(RepairRequest)).all()
    total = len(items)
    active = 0
    new_count = 0
    overdue = 0
    warning = 0
    ready = 0
    completed = 0

    for item in items:
        if item.status == "new":
            new_count += 1
        if item.status == "ready":
            ready += 1
        if item.status == "completed":
            completed += 1
        if item.status not in TERMINAL_STATUSES:
            active += 1
        sla = evaluate_sla(item.status, item.sla_deadline)
        if sla["sla_state"] == "overdue":
            overdue += 1
        elif sla["sla_state"] == "warning":
            warning += 1

    return DashboardStatsOut(
        total=total,
        active=active,
        new_count=new_count,
        overdue=overdue,
        warning=warning,
        ready=ready,
        completed=completed,
    )


@router.get("", response_model=list[RequestSummaryOut])
def list_all_requests(
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    overdue_only: bool = Query(default=False),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
) -> list[RequestSummaryOut]:
    stmt = (
        select(RepairRequest)
        .options(selectinload(RepairRequest.service))
        .order_by(RepairRequest.created_at.desc())
    )
    if status:
        stmt = stmt.where(RepairRequest.status == status)
    if priority:
        stmt = stmt.where(RepairRequest.priority == priority)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                RepairRequest.tracking_code.ilike(pattern),
                RepairRequest.contact_name.ilike(pattern),
                RepairRequest.contact_phone.ilike(pattern),
                RepairRequest.device_model.ilike(pattern),
            )
        )

    items = db.scalars(stmt).all()
    summaries = [_to_summary(item) for item in items]
    if overdue_only:
        summaries = [s for s in summaries if s.is_overdue]
    return summaries


@router.get("/{request_id}", response_model=RequestDetailOut)
def get_request_details(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RequestDetailOut:
    req = _load_request_full(db, request_id)
    if current_user.role != "manager" and req.client_id != current_user.id:
        raise ProblemException(
            status_code=403,
            title="Доступ до заявки заборонено",
            detail="Ви можете переглядати лише власні звернення.",
        )
    return _to_detail(req, include_internal_comments=(current_user.role == "manager"))


@router.patch("/{request_id}", response_model=RequestDetailOut)
def update_request_by_manager(
    request_id: int,
    payload: ManagerRequestUpdate,
    db: Session = Depends(get_db),
    manager: User = Depends(require_manager),
) -> RequestDetailOut:
    req = _load_request_full(db, request_id)
    updates = payload.model_dump(exclude_unset=True)

    new_status = updates.get("status")
    status_comment = updates.get("status_comment")
    old_status = req.status

    if new_status is not None:
        validate_status_transition(old_status, new_status)
        req.status = new_status
        if new_status in TERMINAL_STATUSES:
            req.closed_at = datetime.now(timezone.utc)
        elif old_status in TERMINAL_STATUSES:
            req.closed_at = None

    if "priority" in updates and updates["priority"] is not None:
        req.priority = updates["priority"]
    if "sla_deadline" in updates:
        req.sla_deadline = updates["sla_deadline"]
    if "estimated_cost" in updates:
        req.estimated_cost = updates["estimated_cost"]

    if (new_status is not None and new_status != old_status) or status_comment:
        history = RequestStatusHistory(
            request_id=req.id,
            changed_by=manager.id,
            old_status=old_status,
            new_status=req.status,
            comment=status_comment.strip() if status_comment else None,
        )
        db.add(history)

    db.commit()
    refreshed = _load_request_full(db, req.id)
    return _to_detail(refreshed, include_internal_comments=True)


@router.post("/{request_id}/cancel", response_model=RequestDetailOut)
def cancel_own_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RequestDetailOut:
    req = _load_request_full(db, request_id)
    if current_user.role != "manager" and req.client_id != current_user.id:
        raise ProblemException(
            status_code=403,
            title="Доступ заборонено",
            detail="Ви не можете скасувати чуже звернення.",
        )
    if current_user.role == "client" and req.status != "new":
        raise ProblemException(
            status_code=422,
            title="Скасування неможливе",
            detail="Клієнт може самостійно скасувати лише заявку у статусі «Нова».",
        )

    validate_status_transition(req.status, "cancelled")
    old_status = req.status
    req.status = "cancelled"
    req.closed_at = datetime.now(timezone.utc)

    db.add(
        RequestStatusHistory(
            request_id=req.id,
            changed_by=current_user.id,
            old_status=old_status,
            new_status="cancelled",
            comment="Заявку скасовано користувачем.",
        )
    )
    db.commit()

    refreshed = _load_request_full(db, req.id)
    return _to_detail(refreshed, include_internal_comments=(current_user.role == "manager"))


@router.post("/{request_id}/comments", response_model=CommentOut, status_code=201)
def add_comment(
    request_id: int,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommentOut:
    req = db.get(RepairRequest, request_id)
    if req is None:
        raise ProblemException(
            status_code=404,
            title="Заявку не знайдено",
            detail=f"Звернення #{request_id} не існує.",
        )

    if current_user.role != "manager":
        if req.client_id != current_user.id:
            raise ProblemException(
                status_code=403,
                title="Доступ заборонено",
                detail="Ви можете коментувати лише власні заявки.",
            )
        if payload.is_internal:
            raise ProblemException(
                status_code=403,
                title="Недостатньо прав",
                detail="Внутрішні службові нотатки доступні лише менеджерам.",
            )

    comment = RequestComment(
        request_id=req.id,
        author_id=current_user.id,
        body=payload.body.strip(),
        is_internal=payload.is_internal if current_user.role == "manager" else False,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    return CommentOut(
        id=comment.id,
        author_name=current_user.full_name,
        author_role=current_user.role,
        body=comment.body,
        is_internal=comment.is_internal,
        created_at=comment.created_at,
    )