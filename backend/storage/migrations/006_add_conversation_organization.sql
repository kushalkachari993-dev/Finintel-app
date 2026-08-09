ALTER TABLE chat_conversations
ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_chat_conversations_principal_pinned_updated
ON chat_conversations (principal_id, pinned DESC, updated_at DESC);
