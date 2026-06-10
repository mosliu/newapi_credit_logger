BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 1a94810e8cff

CREATE TABLE api_key_source (
    id SERIAL NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    provider_type VARCHAR(30) NOT NULL, 
    base_url VARCHAR(255) NOT NULL, 
    api_key_encrypted TEXT NOT NULL, 
    key_owner VARCHAR(100) NOT NULL, 
    remark VARCHAR(500), 
    interval_seconds INTEGER NOT NULL, 
    timeout_seconds INTEGER NOT NULL, 
    enabled BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (name)
);

CREATE INDEX ix_api_key_source_id ON api_key_source (id);

CREATE TABLE balance_record (
    id SERIAL NOT NULL, 
    source_id INTEGER NOT NULL, 
    checked_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
    success BOOLEAN NOT NULL, 
    limit_amount NUMERIC(20, 2), 
    usage_amount NUMERIC(20, 2), 
    balance NUMERIC(20, 2), 
    currency VARCHAR(20), 
    http_status INTEGER, 
    latency_ms INTEGER, 
    error_message VARCHAR(500), 
    response_excerpt TEXT, 
    PRIMARY KEY (id), 
    FOREIGN KEY(source_id) REFERENCES api_key_source (id) ON DELETE CASCADE
);

CREATE INDEX ix_balance_record_checked_at ON balance_record (checked_at);

CREATE INDEX ix_balance_record_id ON balance_record (id);

CREATE INDEX ix_balance_record_source_id ON balance_record (source_id);

INSERT INTO alembic_version (version_num) VALUES ('1a94810e8cff') RETURNING alembic_version.version_num;

-- Running upgrade 1a94810e8cff -> 8b9d5e21c0ab

ALTER TABLE api_key_source ADD COLUMN customer_info VARCHAR(255);

ALTER TABLE api_key_source ADD COLUMN key_created_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE api_key_source ADD COLUMN fee_amount NUMERIC(20, 2);

ALTER TABLE api_key_source ADD COLUMN fee_currency VARCHAR(20);

UPDATE alembic_version SET version_num='8b9d5e21c0ab' WHERE alembic_version.version_num = '1a94810e8cff';

-- Running upgrade 8b9d5e21c0ab -> c7f932f7102c

ALTER TABLE api_key_source ADD COLUMN key_account VARCHAR(120);

UPDATE alembic_version SET version_num='c7f932f7102c' WHERE alembic_version.version_num = '8b9d5e21c0ab';

-- Running upgrade c7f932f7102c -> e3d4b2a19f66

CREATE TABLE token_sync_run (
    id SERIAL NOT NULL,
    base_url VARCHAR(255) NOT NULL,
    user_id VARCHAR(120) NOT NULL,
    status VARCHAR(20) NOT NULL,
    fetched_count INTEGER NOT NULL,
    created_count INTEGER NOT NULL,
    skipped_count INTEGER NOT NULL,
    failed_count INTEGER NOT NULL,
    message VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
    finished_at TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (id)
);

CREATE INDEX ix_token_sync_run_id ON token_sync_run (id);

UPDATE alembic_version SET version_num='e3d4b2a19f66' WHERE alembic_version.version_num = 'c7f932f7102c';

-- Running upgrade e3d4b2a19f66 -> a4c9b2d7e8f1

ALTER TABLE api_key_source ADD COLUMN latest_success BOOLEAN;

ALTER TABLE api_key_source ADD COLUMN latest_limit_amount NUMERIC(20, 2);

ALTER TABLE api_key_source ADD COLUMN latest_usage_amount NUMERIC(20, 2);

ALTER TABLE api_key_source ADD COLUMN latest_balance NUMERIC(20, 2);

ALTER TABLE api_key_source ADD COLUMN latest_currency VARCHAR(20);

ALTER TABLE api_key_source ADD COLUMN latest_checked_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE api_key_source ADD COLUMN latest_http_status INTEGER;

ALTER TABLE api_key_source ADD COLUMN latest_latency_ms INTEGER;

ALTER TABLE api_key_source ADD COLUMN latest_error_message VARCHAR(500);

CREATE INDEX ix_balance_record_source_checked_id ON balance_record (source_id, checked_at, id);

UPDATE api_key_source
SET
    latest_success = (
        SELECT br.success
        FROM balance_record AS br
        WHERE br.source_id = api_key_source.id
        ORDER BY br.checked_at DESC, br.id DESC
        LIMIT 1
    ),
    latest_limit_amount = (
        SELECT br.limit_amount
        FROM balance_record AS br
        WHERE br.source_id = api_key_source.id
        ORDER BY br.checked_at DESC, br.id DESC
        LIMIT 1
    ),
    latest_usage_amount = (
        SELECT br.usage_amount
        FROM balance_record AS br
        WHERE br.source_id = api_key_source.id
        ORDER BY br.checked_at DESC, br.id DESC
        LIMIT 1
    ),
    latest_balance = (
        SELECT br.balance
        FROM balance_record AS br
        WHERE br.source_id = api_key_source.id
        ORDER BY br.checked_at DESC, br.id DESC
        LIMIT 1
    ),
    latest_currency = (
        SELECT br.currency
        FROM balance_record AS br
        WHERE br.source_id = api_key_source.id
        ORDER BY br.checked_at DESC, br.id DESC
        LIMIT 1
    ),
    latest_checked_at = (
        SELECT br.checked_at
        FROM balance_record AS br
        WHERE br.source_id = api_key_source.id
        ORDER BY br.checked_at DESC, br.id DESC
        LIMIT 1
    ),
    latest_http_status = (
        SELECT br.http_status
        FROM balance_record AS br
        WHERE br.source_id = api_key_source.id
        ORDER BY br.checked_at DESC, br.id DESC
        LIMIT 1
    ),
    latest_latency_ms = (
        SELECT br.latency_ms
        FROM balance_record AS br
        WHERE br.source_id = api_key_source.id
        ORDER BY br.checked_at DESC, br.id DESC
        LIMIT 1
    ),
    latest_error_message = (
        SELECT br.error_message
        FROM balance_record AS br
        WHERE br.source_id = api_key_source.id
        ORDER BY br.checked_at DESC, br.id DESC
        LIMIT 1
    )
WHERE EXISTS (
    SELECT 1
    FROM balance_record AS br
    WHERE br.source_id = api_key_source.id
);

UPDATE alembic_version SET version_num='a4c9b2d7e8f1' WHERE alembic_version.version_num = 'e3d4b2a19f66';

COMMIT;

