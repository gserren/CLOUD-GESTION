CREATE TABLE IF NOT EXISTS documents (
 id INTEGER PRIMARY KEY,
 source_system TEXT NOT NULL, source_id TEXT NOT NULL, source_revision TEXT NOT NULL DEFAULT '',
 source_reference TEXT NOT NULL DEFAULT '', kind TEXT NOT NULL,
 original_name TEXT NOT NULL, mime_type TEXT NOT NULL DEFAULT '',
 sha256 TEXT NOT NULL CHECK(length(sha256)=64), byte_size INTEGER NOT NULL CHECK(byte_size>0),
 source_url TEXT NOT NULL DEFAULT '', source_created_at TEXT NOT NULL DEFAULT '',
 source_modified_at TEXT NOT NULL DEFAULT '', source_metadata TEXT NOT NULL DEFAULT '{}',
 client_id INTEGER REFERENCES clients(id), site_id INTEGER REFERENCES sites(id),
 order_id INTEGER REFERENCES orders(id), imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(source_system,source_id,source_revision,sha256)
);
CREATE INDEX IF NOT EXISTS idx_documents_client ON documents(client_id);
CREATE TABLE IF NOT EXISTS document_imports (
 id INTEGER PRIMARY KEY, manifest_sha256 TEXT NOT NULL, result TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
UPDATE settings SET value='2' WHERE key='schema_version';
