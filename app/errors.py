from typing import Any
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ProblemException(Exception):
    def __init__(
        self,
        status_code: int,
        title: str,
        detail: str,
        error_type: str = "about:blank",
        errors: list[dict[str, Any]] | None = None,
    ) -> None:
        self.status_code = status_code
        self.title = title
        self.detail = detail
        self.error_type = error_type
        self.errors = errors
        super().__init__(detail)


def _problem_response(
    request: Request,
    status_code: int,
    title: str,
    detail: str,
    error_type: str = "about:blank",
    errors: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    payload: dict[str, Any] = {
        "type": error_type,
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": str(request.url.path),
    }
    if errors is not None:
        payload["errors"] = errors
    return JSONResponse(
        status_code=status_code,
        content=payload,
        media_type="application/problem+json",
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProblemException)
    async def handle_problem_exception(request: Request, exc: ProblemException) -> JSONResponse:
        return _problem_response(
            request=request,
            status_code=exc.status_code,
            title=exc.title,
            detail=exc.detail,
            error_type=exc.error_type,
            errors=exc.errors,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _problem_response(
            request=request,
            status_code=exc.status_code,
            title="Помилка обробки HTTP-запиту",
            detail=str(exc.detail),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_exception(request: Request, exc: RequestValidationError) -> JSONResponse:
        formatted_errors = []
        for err in exc.errors():
            loc = ".".join(str(part) for part in err.get("loc", []) if part != "body")
            formatted_errors.append({
                "field": loc or "request",
                "message": err.get("msg", "Некоректне значення"),
            })
        return _problem_response(
            request=request,
            status_code=422,
            title="Помилка валідації вхідних даних",
            detail="Перевірте коректність заповнення обов’язкових полів.",
            error_type="https://technoservice.ua/problems/validation-error",
            errors=formatted_errors,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
        return _problem_response(
            request=request,
            status_code=500,
            title="Внутрішня помилка сервера",
            detail="Виникла непередбачена помилка під час обробки запиту.",
            error_type="https://technoservice.ua/problems/internal-error",
        )