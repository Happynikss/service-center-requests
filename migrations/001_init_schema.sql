-- Міграція 001: Ініціалізація структури БД сервісного центру
BEGIN;

CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    full_name       VARCHAR(120) NOT NULL,
    phone           VARCHAR(30)  NOT NULL,
    role            VARCHAR(20)  NOT NULL DEFAULT 'client'
                    CHECK (role IN ('client', 'manager')),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS services (
    id              SERIAL PRIMARY KEY,
    title           VARCHAR(150) NOT NULL,
    category        VARCHAR(50)  NOT NULL
                    CHECK (category IN ('diagnostics', 'hardware', 'software', 'maintenance')),
    description     TEXT         NOT NULL,
    base_price      NUMERIC(10, 2) NOT NULL CHECK (base_price >= 0),
    estimated_hours INTEGER      NOT NULL DEFAULT 24 CHECK (estimated_hours > 0),
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS repair_requests (
    id                  SERIAL PRIMARY KEY,
    tracking_code       VARCHAR(24)  NOT NULL UNIQUE,
    client_id           INTEGER      NULL REFERENCES users(id) ON DELETE SET NULL,
    service_id          INTEGER      NOT NULL REFERENCES services(id) ON DELETE RESTRICT,
    contact_name        VARCHAR(120) NOT NULL,
    contact_phone       VARCHAR(30)  NOT NULL,
    contact_email       VARCHAR(255) NULL,
    device_type         VARCHAR(80)  NOT NULL,
    device_model        VARCHAR(120) NOT NULL,
    problem_description TEXT         NOT NULL,
    priority            VARCHAR(20)  NOT NULL DEFAULT 'normal'
                        CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    status              VARCHAR(30)  NOT NULL DEFAULT 'new'
                        CHECK (status IN (
                            'new',
                            'diagnostics',
                            'in_progress',
                            'waiting_parts',
                            'ready',
                            'completed',
                            'cancelled'
                        )),
    sla_deadline        TIMESTAMPTZ  NULL,
    estimated_cost      NUMERIC(10, 2) NULL CHECK (estimated_cost IS NULL OR estimated_cost >= 0),
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    closed_at           TIMESTAMPTZ  NULL
);

CREATE TABLE IF NOT EXISTS request_status_history (
    id              SERIAL PRIMARY KEY,
    request_id      INTEGER     NOT NULL REFERENCES repair_requests(id) ON DELETE CASCADE,
    changed_by      INTEGER     NULL REFERENCES users(id) ON DELETE SET NULL,
    old_status      VARCHAR(30) NULL,
    new_status      VARCHAR(30) NOT NULL,
    comment         TEXT        NULL,
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS request_comments (
    id              SERIAL PRIMARY KEY,
    request_id      INTEGER     NOT NULL REFERENCES repair_requests(id) ON DELETE CASCADE,
    author_id       INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body            TEXT        NOT NULL,
    is_internal     BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Індекси для швидкої фільтрації в кабінеті клієнта, панелі менеджера та перевірки SLA
CREATE INDEX IF NOT EXISTS idx_requests_client_id    ON repair_requests(client_id);
CREATE INDEX IF NOT EXISTS idx_requests_status       ON repair_requests(status);
CREATE INDEX IF NOT EXISTS idx_requests_sla_deadline ON repair_requests(sla_deadline);
CREATE INDEX IF NOT EXISTS idx_history_request_id    ON request_status_history(request_id);
CREATE INDEX IF NOT EXISTS idx_comments_request_id   ON request_comments(request_id);

-- Тригер автоматичного оновлення updated_at при зміні заявки
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_repair_requests_updated_at ON repair_requests;
CREATE TRIGGER trg_repair_requests_updated_at
BEFORE UPDATE ON repair_requests
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

COMMIT;