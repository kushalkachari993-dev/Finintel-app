CREATE TABLE IF NOT EXISTS chat_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    principal_id TEXT,
    user_id INTEGER,
    api_client_id TEXT,
    query TEXT NOT NULL,
    route TEXT,
    routing_json TEXT,
    intelligence_json TEXT,
    response_success INTEGER NOT NULL,
    response_error TEXT,
    confidence_score REAL,
    latency_ms REAL,
    created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_audit_principal_created
ON chat_audit (principal_id, created_at DESC);
