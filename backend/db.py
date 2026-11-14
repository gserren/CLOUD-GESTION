import sqlite3
from pathlib import Path
from flask import current_app, g


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'], timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys=ON')
        g.db.execute('PRAGMA journal_mode=WAL')
    return g.db


def close_db(_error=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(Path(__file__).with_name('schema.sql').read_text())
    version = int(db.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()[0])
    if version > 2:
        raise RuntimeError('La base pertenece a una versión posterior. Actualizá la aplicación.')
    if version < 2:
        migration = Path(__file__).parent / 'migrations' / '002_documents.sql'
        db.executescript('BEGIN IMMEDIATE;\n' + migration.read_text() + '\nCOMMIT;')
    db.commit()


def rows(sql, args=()):
    return [dict(row) for row in get_db().execute(sql, args).fetchall()]


def one(sql, args=()):
    row = get_db().execute(sql, args).fetchone()
    return dict(row) if row else None


def audit(action, entity, entity_id=None):
    get_db().execute('INSERT INTO audit(user_id,action,entity,entity_id) VALUES(?,?,?,?)',
                     (g.user['id'], action, entity, entity_id))
