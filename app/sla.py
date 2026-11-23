from datetime import datetime, timedelta, timezone
from app.errors import ProblemException

STATUS_LABELS: dict[str, str] = {
    "new": "Нова",
    "diagnostics": "Діагностика",
    "in_progress": "У роботі",
    "waiting_parts": "Очікує запчастини",
    "ready": "Готово до видачі",
    "completed": "Виконано",
    "cancelled": "Скасовано",
}

TERMINAL_STATUSES: set[str] = {"completed", "cancelled"}

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "new": {"diagnostics", "in_progress", "cancelled"},
    "diagnostics": {"in_progress", "waiting_parts", "ready", "cancelled"},
    "in_progress": {"waiting_parts", "ready", "cancelled"},
    "waiting_parts": {"in_progress", "ready", "cancelled"},
    "ready": {"completed", "in_progress"},
    "completed": set(),
    "cancelled": set(),
}

PRIORITY_MULTIPLIERS: dict[str, float] = {
    "urgent": 0.5,
    "high": 0.75,
    "normal": 1.0,
    "low": 1.5,
}


def validate_status_transition(current_status: str, target_status: str) -> None:
    if current_status == target_status:
        return
    allowed = ALLOWED_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        current_label = STATUS_LABELS.get(current_status, current_status)
        target_label = STATUS_LABELS.get(target_status, target_status)
        raise ProblemException(
            status_code=422,
            title="Недопустимий перехід статусу заявки",
            detail=f"Перехід зі статусу «{current_label}» у «{target_label}» заборонений регламентом обробки.",
            error_type="https://technoservice.ua/problems/invalid-status-transition",
        )


def calculate_initial_sla(
    estimated_hours: int,
    priority: str,
    base_time: datetime | None = None,
) -> datetime:
    start = base_time or datetime.now(timezone.utc)
    multiplier = PRIORITY_MULTIPLIERS.get(priority, 1.0)
    sla_hours = max(2, round(estimated_hours * multiplier))
    return start + timedelta(hours=sla_hours)


def evaluate_sla(
    status: str,
    sla_deadline: datetime | None,
    now: datetime | None = None,
) -> dict[str, str | int | bool | None]:
    if status in TERMINAL_STATUSES:
        return {
            "is_overdue": False,
            "sla_state": "closed",
            "remaining_minutes": None,
        }
    if sla_deadline is None:
        return {
            "is_overdue": False,
            "sla_state": "unset",
            "remaining_minutes": None,
        }

    current = now or datetime.now(timezone.utc)
    if sla_deadline.tzinfo is None:
        sla_deadline = sla_deadline.replace(tzinfo=timezone.utc)

    delta_minutes = int((sla_deadline - current).total_seconds() // 60)
    if delta_minutes < 0:
        return {
            "is_overdue": True,
            "sla_state": "overdue",
            "remaining_minutes": delta_minutes,
        }
    if delta_minutes <= 240:
        return {
            "is_overdue": False,
            "sla_state": "warning",
            "remaining_minutes": delta_minutes,
        }
    return {
        "is_overdue": False,
        "sla_state": "ok",
        "remaining_minutes": delta_minutes,
    }