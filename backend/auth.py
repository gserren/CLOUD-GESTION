import hashlib
import hmac
import secrets
import time
from functools import wraps
from flask import current_app, g, request, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from .db import get_db, one

COOKIE = 'qtech_session'


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def password_hash(password):
    if not isinstance(password, str) or not 10 <= len(password) <= 128:
        raise ValueError('La contraseña debe tener entre 10 y 128 caracteres.')
    return generate_password_hash(password, method='scrypt')


def public_user(user):
    return {k: user[k] for k in ('id', 'username', 'name', 'role', 'client_id')}


def load_user():
    g.user = None
    g.auth_session = None
    token = request.cookies.get(COOKIE, '')
    if token:
        row = one('SELECT s.token_hash,s.csrf,s.expires,u.* FROM sessions s JOIN users u ON u.id=s.user_id '
                  'WHERE s.token_hash=? AND s.expires>? AND u.active=1', (digest(token), time.time()))
        if row:
            g.user = public_user(row)
            g.auth_session = row


def require(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not g.user:
                return jsonify(error='Ingresá con tu usuario.'), 401
            if roles and g.user['role'] not in roles:
                return jsonify(error='No tenés acceso a esta acción.'), 403
            return fn(*args, **kwargs)
        return wrapped
    return decorator


def check_mutation():
    if request.method not in ('POST', 'PATCH', 'PUT', 'DELETE') or not request.path.startswith('/api/'):
        return
    # A custom header + strict JSON prevents cross-origin simple-form submissions,
    # including login CSRF. No CORS headers are emitted.
    if request.headers.get('X-Qtech-Request') != '1' or not request.is_json:
        return jsonify(error='Solicitud inválida.'), 403
    origin = request.headers.get('Origin')
    if origin and origin.rstrip('/') != request.host_url.rstrip('/'):
        return jsonify(error='Origen no permitido.'), 403
    if request.path != '/api/login':
        if not g.auth_session:
            return jsonify(error='Ingresá con tu usuario.'), 401
        token = request.headers.get('X-CSRF-Token', '')
        if not hmac.compare_digest(token, g.auth_session['csrf']):
            return jsonify(error='La sesión cambió. Recargá la página.'), 403


def login(username, password):
    db = get_db()
    now = time.time()
    # IP and account limits are independent. Shared DB works across WSGI threads.
    keys = ['ip:' + (request.remote_addr or 'local'), 'user:' + username.lower()]
    db.execute('BEGIN IMMEDIATE')
    db.execute('DELETE FROM login_attempts WHERE until<?', (now,))
    for key in keys:
        limit = 30 if key.startswith('ip:') else 10
        attempt = one('SELECT * FROM login_attempts WHERE key=?', (key,))
        if attempt and attempt['attempts'] >= limit:
            db.commit()
            return jsonify(error='Demasiados intentos. Volvé a intentar en 15 minutos.'), 429
    user = one('SELECT * FROM users WHERE username=? COLLATE NOCASE AND active=1', (username,))
    valid = check_password_hash(user['password_hash'] if user else current_app.config['DUMMY_HASH'], password)
    if not user or not valid:
        for key in keys:
            db.execute('INSERT INTO login_attempts(key,attempts,until) VALUES(?,1,?) '
                       'ON CONFLICT(key) DO UPDATE SET attempts=attempts+1', (key, now + 900))
        db.commit()
        return jsonify(error='Usuario o contraseña incorrectos.'), 401
    db.execute('DELETE FROM login_attempts WHERE key=?', (keys[1],))
    db.execute('DELETE FROM sessions WHERE expires<?', (now,))
    old = request.cookies.get(COOKIE)
    if old:
        db.execute('DELETE FROM sessions WHERE token_hash=?', (digest(old),))
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    db.execute('INSERT INTO sessions VALUES(?,?,?,?)', (digest(token), user['id'], csrf, now + 8 * 3600))
    db.commit()
    response = jsonify(user=public_user(user), csrf=csrf)
    response.set_cookie(COOKIE, token, httponly=True, samesite='Strict',
                        secure=current_app.config['COOKIE_SECURE'], max_age=8 * 3600, path='/')
    return response
