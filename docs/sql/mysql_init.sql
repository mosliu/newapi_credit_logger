CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 1a94810e8cff

CREATE TABLE api_key_source (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    name VARCHAR(100) NOT NULL, 
    provider_type VARCHAR(30) NOT NULL, 
    base_url VARCHAR(255) NOT NULL, 
    api_key_encrypted TEXT NOT NULL, 
    key_owner VARCHAR(100) NOT NULL, 
    remark VARCHAR(500), 
    interval_seconds INTEGER NOT NULL, 
    timeout_seconds INTEGER NOT NULL, 
    enabled BOOL NOT NULL, 
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    updated_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    PRIMARY KEY (id), 
    UNIQUE (name)
);

CREATE INDEX ix_api_key_source_id ON api_key_source (id);

CREATE TABLE balance_record (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    source_id INTEGER NOT NULL, 
    checked_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    success BOOL NOT NULL, 
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

INSERT INTO alembic_version (version_num) VALUES ('1a94810e8cff');

-- Running upgrade 1a94810e8cff -> 8b9d5e21c0ab

ALTER TABLE api_key_source ADD COLUMN customer_info VARCHAR(255);

ALTER TABLE api_key_source ADD COLUMN key_created_at DATETIME;

ALTER TABLE api_key_source ADD COLUMN fee_amount NUMERIC(20, 2);

ALTER TABLE api_key_source ADD COLUMN fee_currency VARCHAR(20);

UPDATE alembic_version SET version_num='8b9d5e21c0ab' WHERE alembic_version.version_num = '1a94810e8cff';

-- Running upgrade 8b9d5e21c0ab -> c7f932f7102c

ALTER TABLE api_key_source ADD COLUMN key_account VARCHAR(120);

UPDATE alembic_version SET version_num='c7f932f7102c' WHERE alembic_version.version_num = '8b9d5e21c0ab';

