ALTER TABLE chat_audit
ADD COLUMN response_json TEXT;

ALTER TABLE chat_audit
ADD COLUMN answer_detail TEXT;

ALTER TABLE chat_audit
ADD COLUMN model TEXT;
