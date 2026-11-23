from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field

UserRole = Literal["client", "manager"]
ServiceCategory = Literal["diagnostics", "hardware", "software", "maintenance"]
RequestPriority = Literal["low", "normal", "high", "urgent"]
RequestStatus = Literal[
    "new",
    "diagnostics",
    "in_progress",
    "waiting_parts",
    "ready",
    "completed",
    "cancelled",
]


# --- Auth & Users ---
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)
    full_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=7, max_length=30)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    phone: str
    role: UserRole
    created_at: datetime


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- Services ---
class ServiceCreate(BaseModel):
    title: str = Field(min_length=3, max_length=150)
    category: ServiceCategory
    description: str = Field(min_length=10, max_length=2000)
    base_price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    estimated_hours: int = Field(default=24, ge=1, le=720)
    is_active: bool = True


class ServiceUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=150)
    category: ServiceCategory | None = None
    description: str | None = Field(default=None, min_length=10, max_length=2000)
    base_price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    estimated_hours: int | None = Field(default=None, ge=1, le=720)
    is_active: bool | None = None


class ServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    category: ServiceCategory
    description: str
    base_price: Decimal
    estimated_hours: int
    is_active: bool


# --- Requests, History & Comments ---
class RequestCreate(BaseModel):
    service_id: int = Field(gt=0)
    contact_name: str = Field(min_length=2, max_length=120)
    contact_phone: str = Field(min_length=7, max_length=30)
    contact_email: EmailStr | None = None
    device_type: str = Field(min_length=2, max_length=80)
    device_model: str = Field(min_length=2, max_length=120)
    problem_description: str = Field(min_length=10, max_length=3000)
    priority: RequestPriority = "normal"


class ManagerRequestUpdate(BaseModel):
    status: RequestStatus | None = None
    priority: RequestPriority | None = None
    sla_deadline: datetime | None = None
    estimated_cost: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    status_comment: str | None = Field(default=None, max_length=1000)


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    is_internal: bool = False


class StatusHistoryOut(BaseModel):
    id: int
    old_status: str | None
    new_status: str
    new_status_label: str
    comment: str | None
    changed_by_name: str
    changed_at: datetime


class CommentOut(BaseModel):
    id: int
    author_name: str
    author_role: str
    body: str
    is_internal: bool
    created_at: datetime


class RequestSummaryOut(BaseModel):
    id: int
    tracking_code: str
    service_id: int
    service_title: str
    contact_name: str
    contact_phone: str
    device_type: str
    device_model: str
    priority: RequestPriority
    status: RequestStatus
    status_label: str
    sla_deadline: datetime | None
    is_overdue: bool
    sla_state: str
    remaining_minutes: int | None
    estimated_cost: Decimal | None
    created_at: datetime
    updated_at: datetime


class RequestDetailOut(RequestSummaryOut):
    client_id: int | None
    contact_email: str | None
    problem_description: str
    closed_at: datetime | None
    allowed_next_statuses: list[RequestStatus]
    status_history: list[StatusHistoryOut]
    comments: list[CommentOut]


class DashboardStatsOut(BaseModel):
    total: int
    active: int
    new_count: int
    overdue: int
    warning: int
    ready: int
    completed: int