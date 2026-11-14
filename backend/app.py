import json
import math
import os
import re
import secrets
import sqlite3
from datetime import date
from pathlib import Path
from flask import Flask, g, jsonify, render_template, request, send_file, send_from_directory
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash
from . import auth
from . import documents
from .db import audit, close_db, get_db, init_db, one, rows

ROOT = Path(__file__).resolve().parent.parent
RISK = ('bajo', 'medio', 'alto', 'critico')
STATUS = ('programada', 'en_curso', 'completada', 'cancelada')


class Problem(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status


def payload():
    data = request.get_json()
    if not isinstance(data, dict):
        raise Problem('Se esperaba un objeto JSON.')
    return data


def text(data, key, required=True, limit=2000):
    value = data.get(key, '')
    if not isinstance(value, str):
        raise Problem(f'{key}: se esperaba texto.')
    value = value.strip()
    if (required and not value) or len(value) > limit:
        raise Problem(f'Completá {key} (máximo {limit} caracteres).')
    return value


def integer(value, nullable=False):
    if nullable and value in (None, ''):
        return None
    if isinstance(value, bool) or not re.fullmatch(r'[1-9][0-9]*', str(value)):
        raise Problem('Identificador inválido.')
    return int(value)


def choice(data, key, options, default=None):
    value = data.get(key, default)
    if value not in options:
        raise Problem(f'{key}: valor no permitido.')
    return value


def exists(table, ident):
    # table is exclusively a constant controlled by this module.
    row = one(f'SELECT * FROM {table} WHERE id=?', (ident,))
    if not row:
        raise Problem('Registro no encontrado.', 404)
    return row


def order_access(ident, write=False):
    order = exists('orders', ident)
    if g.user['role'] == 'cliente' or (g.user['role'] == 'tecnico' and order['technician_id'] != g.user['id']):
        raise Problem('Registro no encontrado.', 404)
    if write and order['status'] in ('completada', 'cancelada'):
        raise Problem('La orden está cerrada. Administración debe reabrirla para editar.', 409)
    return order


def technician(value):
    ident = integer(value, nullable=True)
    if ident is not None:
        user = exists('users', ident)
        if user['role'] not in ('admin', 'tecnico') or not user['active']:
            raise Problem('Seleccioná un técnico activo.')
    return ident


def effective_client():
    preview = request.args.get('view_client')
    if preview is not None:
        if g.user['role'] != 'admin':
            raise Problem('Vista de cliente disponible para administración.', 403)
        return exists('clients', integer(preview))['id']
    return g.user['client_id'] if g.user['role'] == 'cliente' else None


def client_snapshot(snapshot):
    data = json.loads(snapshot) if isinstance(snapshot, str) else json.loads(json.dumps(snapshot))
    # Zero-valued measurements do not become client observations. Keep original
    # snapshots intact so administration retains the complete service record.
    data['observations'] = [o for o in data['observations'] if o['value'] != 0]
    data['order'].pop('notes', None)
    return data


def report_access(ident):
    report = exists('reports', ident)
    client_id = effective_client()
    if client_id is not None:
        if report['client_id'] != client_id or not report['published']:
            raise Problem('Reporte no encontrado.', 404)
        snapshot = client_snapshot(report['snapshot'])
    else:
        order_access(report['order_id'])
        snapshot = json.loads(report['snapshot'])
    report['snapshot'] = snapshot
    return report


def create_app(config=None):
    app = Flask(__name__, static_folder=str(ROOT / 'frontend'), static_url_path='/static',
                template_folder=str(ROOT / 'backend' / 'templates'))
    app.config.update(
        DATABASE=os.environ.get('QTECH_DATABASE', str(ROOT / 'instance' / 'qtech.sqlite3')),
        MAX_CONTENT_LENGTH=128 * 1024, COOKIE_SECURE=os.environ.get('QTECH_HTTPS') == '1',
        DUMMY_HASH=auth.password_hash(secrets.token_urlsafe(24)),
        TRUSTED_HOSTS=os.environ.get('QTECH_HOSTS', 'localhost,127.0.0.1').split(','),
    )
    if config:
        app.config.update(config)
    app.config.setdefault('DOCUMENT_ROOT', os.environ.get('QTECH_DOCUMENT_ROOT',
        str(Path(app.config['DATABASE']).parent / 'documents')))
    Path(app.config['DATABASE']).parent.mkdir(parents=True, exist_ok=True)
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()
    app.before_request(auth.load_user)
    app.before_request(auth.check_mutation)

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        if request.path.startswith(('/api/', '/reports/')):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(Problem)
    def problem(error):
        get_db().rollback()
        return jsonify(error=error.message), error.status

    @app.errorhandler(ValueError)
    def invalid(error):
        get_db().rollback()
        return jsonify(error=str(error)), 400

    @app.errorhandler(sqlite3.IntegrityError)
    def integrity(_error):
        get_db().rollback()
        return jsonify(error='El registro ya existe o la relación indicada no es válida.'), 409

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description), error.code

    @app.get('/')
    def index():
        return send_from_directory(app.static_folder, 'index.html')

    @app.get('/api/health')
    def health():
        return jsonify(status='ok', version='0.2.0')

    @app.get('/api/session')
    def current_session():
        return jsonify(user=g.user, csrf=g.auth_session['csrf'] if g.auth_session else None,
                       initialized=bool(one('SELECT id FROM users LIMIT 1')))

    @app.post('/api/login')
    def login():
        data = payload()
        username = text(data, 'username', limit=80)
        password = data.get('password', '')
        if not isinstance(password, str) or len(password) > 128:
            raise Problem('Usuario o contraseña incorrectos.', 401)
        return auth.login(username, password)

    @app.post('/api/logout')
    @auth.require()
    def logout():
        get_db().execute('DELETE FROM sessions WHERE token_hash=?', (g.auth_session['token_hash'],))
        get_db().commit()
        response = jsonify(ok=True)
        response.delete_cookie(auth.COOKIE, path='/')
        return response

    @app.post('/api/password')
    @auth.require()
    def change_password():
        data = payload()
        user = exists('users', g.user['id'])
        current = data.get('current_password', '')
        if not isinstance(current, str) or not check_password_hash(user['password_hash'], current):
            raise Problem('La contraseña actual no coincide.', 403)
        hashed = auth.password_hash(data.get('password'))
        get_db().execute('UPDATE users SET password_hash=? WHERE id=?', (hashed, g.user['id']))
        get_db().execute('DELETE FROM sessions WHERE user_id=?', (g.user['id'],))
        audit('password_changed', 'users', g.user['id'])
        get_db().commit()
        response = jsonify(ok=True)
        response.delete_cookie(auth.COOKIE, path='/')
        return response

    @app.get('/api/data')
    @auth.require()
    def data():
        client_id = effective_client()
        result = dict(user=g.user, preview_client=client_id if g.user['role'] == 'admin' else None,
                      demo=bool(one("SELECT 1 FROM settings WHERE key='demo' AND value='1'")))
        if client_id is not None:
            result['clients'] = rows('SELECT * FROM clients WHERE id=?', (client_id,))
            result['sites'] = rows('SELECT * FROM sites WHERE client_id=?', (client_id,))
            result['orders'], result['observations'], result['users'] = [], [], []
            reports = rows('SELECT * FROM reports WHERE client_id=? AND published=1 ORDER BY id DESC', (client_id,))
            for report in reports:
                report['snapshot'] = client_snapshot(report['snapshot'])
        else:
            where = 'WHERE o.technician_id=?' if g.user['role'] == 'tecnico' else ''
            args = (g.user['id'],) if where else ()
            result['orders'] = rows('SELECT o.*,s.client_id FROM orders o JOIN sites s ON s.id=o.site_id ' + where +
                                    ' ORDER BY o.scheduled_date,o.id', args)
            allowed_sites = {o['site_id'] for o in result['orders']}
            all_sites = rows('SELECT * FROM sites ORDER BY name')
            result['sites'] = all_sites if not where else [s for s in all_sites if s['id'] in allowed_sites]
            allowed_clients = {s['client_id'] for s in result['sites']}
            all_clients = rows('SELECT * FROM clients ORDER BY name')
            result['clients'] = all_clients if not where else [c for c in all_clients if c['id'] in allowed_clients]
            result['observations'] = rows('SELECT b.* FROM observations b JOIN orders o ON o.id=b.order_id ' + where, args)
            reports = rows('SELECT r.* FROM reports r JOIN orders o ON o.id=r.order_id ' + where + ' ORDER BY r.id DESC', args)
            for report in reports:
                report['snapshot'] = json.loads(report['snapshot'])
            user_where = '' if g.user['role'] == 'admin' else "WHERE id=?"
            result['users'] = rows('SELECT id,username,name,role,client_id,active FROM users ' + user_where,
                                   () if not user_where else (g.user['id'],))
        result['reports'] = reports
        result['documents'] = rows('SELECT * FROM documents ORDER BY id DESC') if g.user['role'] == 'admin' and client_id is None else []
        result['audit'] = rows('SELECT a.*,u.name FROM audit a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT 30') if g.user['role'] == 'admin' and client_id is None else []
        return jsonify(result)

    @app.post('/api/clients')
    @auth.require('admin')
    def create_client():
        d = payload()
        values = (text(d, 'name', limit=160), choice(d, 'company', ('PCI','AQUATECH','VORTEX','QTECH'), 'PCI'),
                  text(d, 'contact', False, 160), text(d, 'email', False, 200), text(d, 'phone', False, 80))
        ident = get_db().execute('INSERT INTO clients(name,company,contact,email,phone) VALUES(?,?,?,?,?)', values).lastrowid
        audit('created', 'clients', ident)
        get_db().commit()
        return jsonify(id=ident), 201

    @app.patch('/api/clients/<int:ident>')
    @auth.require('admin')
    def update_client(ident):
        old = exists('clients', ident)
        old.update(payload())
        values = (text(old,'name',limit=160), choice(old,'company',('PCI','AQUATECH','VORTEX','QTECH')),
                  text(old,'contact',False,160), text(old,'email',False,200), text(old,'phone',False,80), ident)
        get_db().execute('UPDATE clients SET name=?,company=?,contact=?,email=?,phone=? WHERE id=?', values)
        audit('updated','clients',ident)
        get_db().commit()
        return jsonify(ok=True)

    @app.post('/api/sites')
    @auth.require('admin')
    def create_site():
        d = payload()
        client_id = exists('clients', integer(d.get('client_id')))['id']
        ident = get_db().execute('INSERT INTO sites(client_id,name,address,system) VALUES(?,?,?,?)',
             (client_id,text(d,'name',limit=160),text(d,'address',False,300),text(d,'system',False,300))).lastrowid
        audit('created','sites',ident)
        get_db().commit()
        return jsonify(id=ident),201

    @app.post('/api/users')
    @auth.require('admin')
    def create_user():
        d = payload()
        username = text(d,'username',limit=80)
        if not re.fullmatch(r'[A-Za-z0-9_.@-]{3,80}',username):
            raise Problem('Usuario: 3 a 80 letras, números o signos . _ @ -')
        role = choice(d,'role',('admin','tecnico','cliente'))
        client_id = exists('clients',integer(d.get('client_id')))['id'] if role == 'cliente' else None
        hashed = auth.password_hash(d.get('password'))
        ident = get_db().execute('INSERT INTO users(username,name,password_hash,role,client_id) VALUES(?,?,?,?,?)',
             (username,text(d,'name',limit=160),hashed,role,client_id)).lastrowid
        audit('created','users',ident)
        get_db().commit()
        return jsonify(id=ident),201

    @app.patch('/api/users/<int:ident>')
    @auth.require('admin')
    def update_user(ident):
        exists('users',ident)
        if ident == g.user['id']:
            raise Problem('No podés desactivar tu propia cuenta.')
        active = payload().get('active')
        if not isinstance(active,bool):
            raise Problem('Indicá active como verdadero o falso.')
        get_db().execute('UPDATE users SET active=? WHERE id=?',(int(active),ident))
        get_db().execute('DELETE FROM sessions WHERE user_id=?',(ident,))
        audit('activated' if active else 'deactivated','users',ident)
        get_db().commit()
        return jsonify(ok=True)

    @app.post('/api/orders')
    @auth.require('admin')
    def create_order():
        d = payload()
        site_id = exists('sites',integer(d.get('site_id')))['id']
        scheduled = text(d,'scheduled_date',limit=10)
        date.fromisoformat(scheduled)
        ident = get_db().execute('INSERT INTO orders(site_id,title,service,scheduled_date,technician_id,priority,notes) VALUES(?,?,?,?,?,?,?)',
            (site_id,text(d,'title',limit=200),text(d,'service',limit=160),scheduled,technician(d.get('technician_id')),
             choice(d,'priority',('baja','media','alta','urgente'),'media'),text(d,'notes',False,4000))).lastrowid
        audit('created','orders',ident)
        get_db().commit()
        return jsonify(id=ident),201

    @app.patch('/api/orders/<int:ident>')
    @auth.require('admin','tecnico')
    def update_order(ident):
        old = order_access(ident)
        d = payload()
        status = choice(d,'status',STATUS,old['status'])
        if old['status'] in ('completada','cancelada'):
            if g.user['role'] != 'admin' or status != 'en_curso':
                raise Problem('Administración debe reabrir la orden antes de modificarla.',409)
        allowed = {'programada': {'programada','en_curso','cancelada'},
                   'en_curso': {'en_curso','completada','cancelada'},
                   'completada': {'en_curso'}, 'cancelada': {'en_curso'}}
        if status not in allowed[old['status']]:
            raise Problem('Cambio de estado no permitido.',409)
        merged = {**old, **d}
        result = text(merged,'result',status == 'completada',6000)
        scheduled, tech = old['scheduled_date'], old['technician_id']
        if g.user['role'] == 'admin':
            scheduled = text(merged,'scheduled_date',limit=10)
            date.fromisoformat(scheduled)
            tech = technician(merged.get('technician_id'))
        get_db().execute('UPDATE orders SET status=?,result=?,scheduled_date=?,technician_id=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',
                         (status,result,scheduled,tech,ident))
        audit('status:'+status,'orders',ident)
        get_db().commit()
        return jsonify(ok=True)

    @app.post('/api/observations')
    @auth.require('admin','tecnico')
    def create_observation():
        d = payload()
        order_id = order_access(integer(d.get('order_id')),write=True)['id']
        value = d.get('value')
        if value in ('',None):
            value = None
        elif isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
            raise Problem('El valor debe ser numérico o vacío.')
        ident = get_db().execute('INSERT INTO observations(order_id,description,risk,value) VALUES(?,?,?,?)',
                   (order_id,text(d,'description',limit=3000),choice(d,'risk',RISK),value)).lastrowid
        audit('created','observations',ident)
        get_db().commit()
        return jsonify(id=ident),201

    @app.patch('/api/observations/<int:ident>')
    @auth.require('admin','tecnico')
    def resolve_observation(ident):
        obs = exists('observations',ident)
        order_access(obs['order_id'],write=True)
        if obs['status'] == 'resuelta':
            raise Problem('La observación ya está resuelta.',409)
        resolution = text(payload(),'resolution',limit=3000)
        get_db().execute("UPDATE observations SET status='resuelta',resolution=?,resolved_at=CURRENT_TIMESTAMP WHERE id=?",(resolution,ident))
        audit('resolved','observations',ident)
        get_db().commit()
        return jsonify(ok=True)

    @app.post('/api/reports')
    @auth.require('admin','tecnico')
    def create_report():
        ident = integer(payload().get('order_id'))
        db = get_db()
        db.execute('BEGIN IMMEDIATE')
        order = order_access(ident)
        if order['status'] != 'completada':
            raise Problem('Completá la orden antes de generar su reporte.',409)
        site = exists('sites',order['site_id'])
        client = exists('clients',site['client_id'])
        tech = one('SELECT name FROM users WHERE id=?',(order['technician_id'],))
        snapshot = dict(order=order,site=site,client=client,technician=tech['name'] if tech else 'Sin asignar',
                        observations=rows('SELECT * FROM observations WHERE order_id=? ORDER BY id',(ident,)))
        revision = one('SELECT COALESCE(MAX(revision),0)+1 AS n FROM reports WHERE order_id=?',(ident,))['n']
        report_id = db.execute('INSERT INTO reports(order_id,client_id,revision,snapshot,created_by) VALUES(?,?,?,?,?)',
                     (ident,client['id'],revision,json.dumps(snapshot,ensure_ascii=False),g.user['id'])).lastrowid
        audit('generated','reports',report_id)
        db.commit()
        return jsonify(id=report_id),201

    @app.post('/api/reports/<int:ident>/publish')
    @auth.require('admin')
    def publish_report(ident):
        exists('reports',ident)
        get_db().execute('UPDATE reports SET published=1,published_at=COALESCE(published_at,CURRENT_TIMESTAMP) WHERE id=?',(ident,))
        audit('published_to_client','reports',ident)
        get_db().commit()
        return jsonify(ok=True)

    @app.get('/api/reports/<int:ident>')
    @auth.require()
    def get_report(ident):
        return jsonify(report_access(ident))

    @app.get('/reports/<int:ident>')
    @auth.require()
    def report_html(ident):
        report = report_access(ident)
        return render_template('report.html',report=report,s=report['snapshot'],client_view=effective_client() is not None)

    @app.get('/api/documents/<int:ident>/download')
    @auth.require('admin')
    def download_document(ident):
        if effective_client() is not None:
            raise Problem('Original no disponible en vista cliente.', 404)
        doc = exists('documents', ident)
        path = documents.blob_path(doc['sha256'])
        if not path.is_file():
            raise Problem('Original no disponible; verificá el archivo privado.', 503)
        if path.stat().st_size != doc['byte_size'] or documents.file_hash(path) != doc['sha256']:
            raise Problem('Falló la verificación de integridad del original.', 503)
        audit('downloaded_original', 'documents', ident)
        get_db().commit()
        return send_file(path, as_attachment=True, download_name=doc['original_name'],
                         mimetype='application/octet-stream', conditional=False, etag=False)

    @app.patch('/api/documents/<int:ident>/association')
    @auth.require('admin')
    def associate_document(ident):
        if effective_client() is not None:
            raise Problem('La vista cliente es de solo lectura.', 403)
        exists('documents', ident)
        d = payload()
        if set(d) - {'client_id','site_id','order_id'}:
            raise Problem('Solo se pueden modificar las asociaciones del original.')
        ids = [integer(d.get(k), nullable=True) for k in ('client_id','site_id','order_id')]
        cid, sid, oid = documents.association(*ids)
        get_db().execute('UPDATE documents SET client_id=?,site_id=?,order_id=? WHERE id=?', (cid,sid,oid,ident))
        audit('associated_original', 'documents', ident)
        get_db().commit()
        return jsonify(ok=True)

    return app
