PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS clients (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, company TEXT NOT NULL DEFAULT 'PCI',
 contact TEXT NOT NULL DEFAULT '', email TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sites (
 id INTEGER PRIMARY KEY, client_id INTEGER NOT NULL REFERENCES clients(id),
 name TEXT NOT NULL, address TEXT NOT NULL DEFAULT '', system TEXT NOT NULL DEFAULT '',
 UNIQUE(client_id, name)
);
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
 name TEXT NOT NULL, password_hash TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('admin','tecnico','cliente')),
 client_id INTEGER REFERENCES clients(id), active INTEGER NOT NULL DEFAULT 1,
 CHECK((role='cliente' AND client_id IS NOT NULL) OR (role!='cliente' AND client_id IS NULL))
);
CREATE TABLE IF NOT EXISTS sessions (
 token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
 csrf TEXT NOT NULL, expires REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS login_attempts (key TEXT PRIMARY KEY, attempts INTEGER NOT NULL, until REAL NOT NULL);
CREATE TABLE IF NOT EXISTS orders (
 id INTEGER PRIMARY KEY, site_id INTEGER NOT NULL REFERENCES sites(id),
 title TEXT NOT NULL, service TEXT NOT NULL,
 scheduled_date TEXT NOT NULL, technician_id INTEGER REFERENCES users(id),
 status TEXT NOT NULL DEFAULT 'programada' CHECK(status IN ('programada','en_curso','completada','cancelada')),
 priority TEXT NOT NULL DEFAULT 'media' CHECK(priority IN ('baja','media','alta','urgente')),
 notes TEXT NOT NULL DEFAULT '', result TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS observations (
 id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id),
 description TEXT NOT NULL, risk TEXT NOT NULL CHECK(risk IN ('bajo','medio','alto','critico')),
 value REAL, status TEXT NOT NULL DEFAULT 'abierta' CHECK(status IN ('abierta','resuelta')),
 resolution TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 resolved_at TEXT
);
CREATE TABLE IF NOT EXISTS reports (
 id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id),
 client_id INTEGER NOT NULL REFERENCES clients(id),
 revision INTEGER NOT NULL, snapshot TEXT NOT NULL,
 published INTEGER NOT NULL DEFAULT 0, created_by INTEGER NOT NULL REFERENCES users(id),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, published_at TEXT,
 UNIQUE(order_id, revision)
);
CREATE TABLE IF NOT EXISTS audit (
 id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id),
 action TEXT NOT NULL, entity TEXT NOT NULL, entity_id INTEGER,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT OR IGNORE INTO settings(key,value) VALUES('schema_version','1');
CREATE INDEX IF NOT EXISTS idx_orders_technician ON orders(technician_id);
CREATE INDEX IF NOT EXISTS idx_sites_client ON sites(client_id);
CREATE INDEX IF NOT EXISTS idx_observations_order ON observations(order_id);
CREATE INDEX IF NOT EXISTS idx_reports_client ON reports(client_id, published);
CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires);
