from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.config import get_settings
from app.errors import ProblemException, register_exception_handlers
from app.routers import auth, requests, services

settings = get_settings()
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(
    title=settings.app_title,
    version="1.0.0",
    description="REST API та вебінтерфейс системи керування зверненнями сервісного центру з контролем SLA.",
)

register_exception_handlers(app)

app.include_router(auth.router)
app.include_router(services.router)
app.include_router(requests.router)


@app.get("/api/health", tags=["Система"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok", "service": "technoservice-api"}


if FRONTEND_DIR.exists():
    app.mount("/css", StaticFiles(directory=FRONTEND_DIR / "css"), name="css")
    app.mount("/js", StaticFiles(directory=FRONTEND_DIR / "js"), name="js")


def _serve_page(filename: str) -> FileResponse:
    file_path = FRONTEND_DIR / filename
    if not file_path.exists():
        raise ProblemException(
            status_code=404,
            title="Сторінку не знайдено",
            detail=f"Файл інтерфейсу {filename} ще не створено.",
        )
    return FileResponse(file_path)


@app.get("/", include_in_schema=False)
@app.get("/index.html", include_in_schema=False)
def page_index() -> FileResponse:
    return _serve_page("index.html")


@app.get("/create-request", include_in_schema=False)
@app.get("/create-request.html", include_in_schema=False)
def page_create_request() -> FileResponse:
    return _serve_page("create-request.html")


@app.get("/track", include_in_schema=False)
@app.get("/track.html", include_in_schema=False)
def page_track() -> FileResponse:
    return _serve_page("track.html")


@app.get("/login", include_in_schema=False)
@app.get("/login.html", include_in_schema=False)
def page_login() -> FileResponse:
    return _serve_page("login.html")


@app.get("/client", include_in_schema=False)
@app.get("/client.html", include_in_schema=False)
def page_client() -> FileResponse:
    return _serve_page("client.html")


@app.get("/manager", include_in_schema=False)
@app.get("/manager.html", include_in_schema=False)
def page_manager() -> FileResponse:
    return _serve_page("manager.html")