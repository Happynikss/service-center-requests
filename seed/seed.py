from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import func, select
from app.database import SessionLocal
from app.models import RepairRequest, RequestComment, RequestStatusHistory, Service, User
from app.security import hash_password


def run_seed() -> None:
    db = SessionLocal()
    try:
        existing_users = db.scalar(select(func.count(User.id))) or 0
        if existing_users > 0:
            print("База даних уже містить початкові дані. Повторне заповнення пропущено.")
            return

        now = datetime.now(timezone.utc)

        # 1. Користувачі (1 менеджер + 3 клієнти)
        manager = User(
            email="manager@technoservice.ua",
            password_hash=hash_password("Manager2026!"),
            full_name="Демешко Микита Ігорович",
            phone="+380671112233",
            role="manager",
        )
        client1 = User(
            email="olena.kovalenko@example.ua",
            password_hash=hash_password("Client2026!"),
            full_name="Коваленко Олена Вікторівна",
            phone="+380503334455",
            role="client",
        )
        client2 = User(
            email="andriy.melnyk@example.ua",
            password_hash=hash_password("Client2026!"),
            full_name="Мельник Андрій Ігорович",
            phone="+380935556677",
            role="client",
        )
        client3 = User(
            email="iryna.savchenko@example.ua",
            password_hash=hash_password("Client2026!"),
            full_name="Савченко Ірина Олегівна",
            phone="+380667778899",
            role="client",
        )
        db.add_all([manager, client1, client2, client3])
        db.flush()

        # 2. Каталог послуг (8 позицій)
        services = [
            Service(
                title="Комплексна апаратна діагностика ПК / ноутбука",
                category="diagnostics",
                description="Тестування накопичувачів, оперативної пам’яті, ланцюгів живлення та температурного режиму під навантаженням.",
                base_price=Decimal("350.00"),
                estimated_hours=12,
            ),
            Service(
                title="Чищення системи охолодження та заміна термоінтерфейсу",
                category="maintenance",
                description="Розбирання корпусу, видалення пилу з радіаторів, заміна термопасти (Arctic MX-6) та термопрокладок.",
                base_price=Decimal("650.00"),
                estimated_hours=24,
            ),
            Service(
                title="Заміна матриці екрана ноутбука",
                category="hardware",
                description="Підбір сумісної IPS/OLED матриці, демонтаж рамки дисплея, встановлення та перевірка підсвічування.",
                base_price=Decimal("1200.00"),
                estimated_hours=48,
            ),
            Service(
                title="Ремонт ланцюгів живлення материнської плати",
                category="hardware",
                description="Відновлення після залиття рідиною або стрибка напруги, заміна контролерів живлення та BGA-пайка.",
                base_price=Decimal("1850.00"),
                estimated_hours=72,
            ),
            Service(
                title="Заміна клавіатури або акумулятора ноутбука",
                category="hardware",
                description="Заміна зношеної АКБ або клавіатурного модуля з перевіркою контролера заряду.",
                base_price=Decimal("750.00"),
                estimated_hours=36,
            ),
            Service(
                title="Встановлення ОС, драйверів та базового ПЗ",
                category="software",
                description="Розбиття диска, встановлення ліцензійної ОС, налаштування драйверів та збереження даних користувача.",
                base_price=Decimal("550.00"),
                estimated_hours=16,
            ),
            Service(
                title="Відновлення даних із пошкоджених SSD / HDD",
                category="software",
                description="Апаратно-програмне вичитування секторів та відновлення файлової структури з носіїв.",
                base_price=Decimal("1500.00"),
                estimated_hours=48,
            ),
            Service(
                title="Апгрейд конфігурації (ОЗП, NVMe SSD) та оптимізація",
                category="maintenance",
                description="Підбір сумісних комплектуючих, встановлення, клонування системи та стрес-тестування.",
                base_price=Decimal("500.00"),
                estimated_hours=24,
            ),
        ]
        db.add_all(services)
        db.flush()

        # 3. Заявки на ремонт (включно з простроченими SLA та терміновими)
        sample_requests = [
            RepairRequest(
                tracking_code="SC-2026-0001",
                client_id=client1.id,
                service_id=services[3].id,
                contact_name=client1.full_name,
                contact_phone=client1.phone,
                contact_email=client1.email,
                device_type="Ноутбук",
                device_model="ASUS ROG Zephyrus G14",
                problem_description="Після потрапляння кави на клавіатуру ноутбук не реагує на кнопку живлення.",
                priority="urgent",
                status="in_progress",
                sla_deadline=now - timedelta(hours=5),  # Прострочено за SLA
                estimated_cost=Decimal("2400.00"),
                created_at=now - timedelta(hours=41),
            ),
            RepairRequest(
                tracking_code="SC-2026-0002",
                client_id=client2.id,
                service_id=services[1].id,
                contact_name=client2.full_name,
                contact_phone=client2.phone,
                contact_email=client2.email,
                device_type="Ноутбук",
                device_model="Lenovo ThinkPad T14 Gen 3",
                problem_description="Сильно шумить вентилятор і під навантаженням температура процесора сягає 98°C.",
                priority="high",
                status="diagnostics",
                sla_deadline=now - timedelta(hours=2),  # Прострочено за SLA
                estimated_cost=Decimal("700.00"),
                created_at=now - timedelta(hours=20),
            ),
            RepairRequest(
                tracking_code="SC-2026-0003",
                client_id=client1.id,
                service_id=services[2].id,
                contact_name=client1.full_name,
                contact_phone=client1.phone,
                contact_email=client1.email,
                device_type="Ноутбук",
                device_model="HP EliteBook 845 G8",
                problem_description="Тріщина у правому куті матриці після падіння зі столу, половина екрана без зображення.",
                priority="high",
                status="waiting_parts",
                sla_deadline=now + timedelta(hours=2),  # На межі SLA (< 4 годин)
                estimated_cost=Decimal("3450.00"),
                created_at=now - timedelta(hours=34),
            ),
            RepairRequest(
                tracking_code="SC-2026-0004",
                client_id=client3.id,
                service_id=services[5].id,
                contact_name=client3.full_name,
                contact_phone=client3.phone,
                contact_email=client3.email,
                device_type="Системний блок",
                device_model="Custom Ryzen 5 5600 / B550",
                problem_description="Після невдалого оновлення Windows система циклічно перезавантажується з синім екраном.",
                priority="normal",
                status="new",
                sla_deadline=now + timedelta(hours=15),
                estimated_cost=Decimal("550.00"),
                created_at=now - timedelta(hours=1),
            ),
            RepairRequest(
                tracking_code="SC-2026-0005",
                client_id=None,  # Гостьова заявка без реєстрації
                service_id=services[0].id,
                contact_name="Бондаренко Тарас Миколайович",
                contact_phone="+380971234567",
                contact_email="taras.bondarenko@ukr.net",
                device_type="Моноблок",
                device_model="Acer Aspire C24-1700",
                problem_description="Періодично зникає зображення на 2-3 секунди та чути клацання з боку блоку живлення.",
                priority="normal",
                status="new",
                sla_deadline=now + timedelta(hours=11),
                estimated_cost=Decimal("350.00"),
                created_at=now - timedelta(minutes=45),
            ),
            RepairRequest(
                tracking_code="SC-2026-0006",
                client_id=client2.id,
                service_id=services[7].id,
                contact_name=client2.full_name,
                contact_phone=client2.phone,
                contact_email=client2.email,
                device_type="Ноутбук",
                device_model="Dell XPS 15 9520",
                problem_description="Встановити додатковий NVMe SSD на 1 ТБ та перенести робоче середовище.",
                priority="low",
                status="ready",
                sla_deadline=now + timedelta(hours=18),
                estimated_cost=Decimal("600.00"),
                created_at=now - timedelta(hours=18),
            ),
            RepairRequest(
                tracking_code="SC-2026-0007",
                client_id=client3.id,
                service_id=services[4].id,
                contact_name=client3.full_name,
                contact_phone=client3.phone,
                contact_email=client3.email,
                device_type="Ноутбук",
                device_model="Apple MacBook Air M1",
                problem_description="Здулася батарея, тачпад погано натискається.",
                priority="normal",
                status="completed",
                sla_deadline=now - timedelta(hours=12),
                estimated_cost=Decimal("2900.00"),
                created_at=now - timedelta(hours=48),
                closed_at=now - timedelta(hours=14),
            ),
        ]
        db.add_all(sample_requests)
        db.flush()

        # 4. Історія статусів та коментарі (публічні + внутрішні службові)
        history_entries = [
            RequestStatusHistory(
                request_id=sample_requests[0].id,
                changed_by=client1.id,
                old_status=None,
                new_status="new",
                comment="Заявку зареєстровано клієнтом.",
                changed_at=now - timedelta(hours=41),
            ),
            RequestStatusHistory(
                request_id=sample_requests[0].id,
                changed_by=manager.id,
                old_status="new",
                new_status="diagnostics",
                comment="Пристрій прийнято в роботу. Виявлено окислення в зоні шим-контролера.",
                changed_at=now - timedelta(hours=35),
            ),
            RequestStatusHistory(
                request_id=sample_requests[0].id,
                changed_by=manager.id,
                old_status="diagnostics",
                new_status="in_progress",
                comment="Ультразвукова чистка плати виконана, триває відновлення доріжок живлення.",
                changed_at=now - timedelta(hours=22),
            ),
            RequestStatusHistory(
                request_id=sample_requests[2].id,
                changed_by=manager.id,
                old_status="new",
                new_status="waiting_parts",
                comment="Замовлено оригінальну IPS-матрицю FullHD 400 nits зі складу постачальника.",
                changed_at=now - timedelta(hours=20),
            ),
            RequestStatusHistory(
                request_id=sample_requests[5].id,
                changed_by=manager.id,
                old_status="new",
                new_status="ready",
                comment="Накопичувач встановлено, систему клоновано та протестовано. Можна забирати.",
                changed_at=now - timedelta(hours=2),
            ),
        ]
        db.add_all(history_entries)

        comments = [
            RequestComment(
                request_id=sample_requests[0].id,
                author_id=manager.id,
                body="Узгодили з клієнтом телефоном вартість відновлення плати — 2400 грн.",
                is_internal=False,
                created_at=now - timedelta(hours=30),
            ),
            RequestComment(
                request_id=sample_requests[0].id,
                author_id=manager.id,
                body="СЛУЖБОВА ПРИМІТКА: передати інженеру Іваненку на повторну перевірку під тепловізором після пайки.",
                is_internal=True,
                created_at=now - timedelta(hours=10),
            ),
            RequestComment(
                request_id=sample_requests[0].id,
                author_id=client1.id,
                body="Дякую за оперативність! Підкажіть, чи збережуться файли на SSD?",
                is_internal=False,
                created_at=now - timedelta(hours=8),
            ),
        ]
        db.add_all(comments)

        db.commit()
        print("Тестові дані успішно завантажено (1 менеджер, 3 клієнти, 8 послуг, 7 заявок).")
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()