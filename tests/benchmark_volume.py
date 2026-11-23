import statistics
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from app.database import SessionLocal
from app.main import app
from app.models import RepairRequest, Service


def _measure_ms(func, iterations: int = 20) -> tuple[float, float]:
    samples = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        func()
        samples.append((time.perf_counter() - t0) * 1000.0)
    avg_ms = statistics.mean(samples)
    p95_ms = sorted(samples)[int(iterations * 0.95) - 1]
    return avg_ms, p95_ms


def run_benchmark() -> None:
    db = SessionLocal()
    client = TestClient(app)

    try:
        login = client.post(
            "/api/auth/login",
            json={"email": "manager@technoservice.ua", "password": "Manager2026!"},
        ).json()
        headers = {"Authorization": f"Bearer {login['access_token']}"}
        service_id = db.scalar(select(Service.id).limit(1))

        now = datetime.now(timezone.utc)
        stages = [100, 1000, 10000]
        current_count = 0

        print("\n=== РЕЗУЛЬТАТИ НАВАНТАЖУВАЛЬНОГО ТА ОБСЯГОВОГО ТЕСТУВАННЯ ===")
        print(f"{'Обсяг БД':<12} | {'Пошук за треком (avg/p95)':<28} | {'Фільтр прострочених SLA (avg/p95)':<34} | {'Статистика KPI (avg/p95)':<26}")
        print("-" * 108)

        for target in stages:
            to_insert = target - current_count
            batch = [
                RepairRequest(
                    tracking_code=f"SC-BENCH-{current_count + i + 1:05d}",
                    service_id=service_id,
                    contact_name=f"Тест Обсягу #{current_count + i + 1}",
                    contact_phone="+380670000000",
                    device_type="Ноутбук",
                    device_model="Benchmark Model X1",
                    problem_description="Синтетичний запис для перевірки швидкодії індексів PostgreSQL.",
                    priority="normal" if i % 3 else "urgent",
                    status="in_progress" if i % 4 else "new",
                    sla_deadline=now + timedelta(hours=(i % 48) - 12),
                    estimated_cost=Decimal("650.00"),
                )
                for i in range(to_insert)
            ]
            db.bulk_save_objects(batch)
            db.commit()
            current_count = target

            target_code = f"SC-BENCH-{target // 2:05d}"
            t_avg, t_p95 = _measure_ms(lambda: client.get(f"/api/requests/track/{target_code}"))
            o_avg, o_p95 = _measure_ms(lambda: client.get("/api/requests?overdue_only=true", headers=headers))
            s_avg, s_p95 = _measure_ms(lambda: client.get("/api/requests/stats", headers=headers))

            print(
                f"{target:<12} | {t_avg:6.2f} / {t_p95:6.2f} мс         | "
                f"{o_avg:6.2f} / {o_p95:6.2f} мс               | {s_avg:6.2f} / {s_p95:6.2f} мс"
            )
    finally:
        db.execute(delete(RepairRequest).where(RepairRequest.tracking_code.like("SC-BENCH-%")))
        db.commit()
        db.close()
        print("\nТестові записи SC-BENCH-* видалено, БД повернуто до початкового стану.")


if __name__ == "__main__":
    run_benchmark()