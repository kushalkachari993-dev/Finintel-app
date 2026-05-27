CREATE TABLE IF NOT EXISTS chat_conversations (
    id TEXT PRIMARY KEY,
    principal_id TEXT NOT NULL,
    title TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_conversations_principal_updated
ON chat_conversations (principal_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    payload_json TEXT,
    created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation_created
ON chat_messages (conversation_id, created_at ASC, id ASC);

ALTER TABLE chat_audit
ADD COLUMN conversation_id TEXT;
