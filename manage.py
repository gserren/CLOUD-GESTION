#!/usr/bin/env python3
"""Operaciones locales. Las contraseñas nunca se aceptan como argumentos."""
import argparse
import getpass
import os
import re
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from backend.app import create_app
from backend.auth import password_hash
from backend.db import get_db


def main():
    parser = argparse.ArgumentParser(description='QTECH Gestión')
    sub = parser.add_subparsers(dest='command',required=True)
    admin = sub.add_parser('init-admin',help='Crear el administrador inicial')
    admin.add_argument('--username',default='admin')
    admin.add_argument('--name',default='Administración QTECH')
    reset = sub.add_parser('reset-password',help='Restablecer una contraseña desde el servidor')
    reset.add_argument('username')
    sub.add_parser('seed-demo',help='Cargar ejemplos ficticios, solo si no hay clientes')
    run = sub.add_parser('serve',help='Ejecutar con Waitress')
    run.add_argument('--host',default='127.0.0.1')
    run.add_argument('--port',type=int,default=8000)
    backup = sub.add_parser('backup',help='Copia consistente de SQLite, incluyendo WAL')
    backup.add_argument('destination')
    args = parser.parse_args()
    app = create_app()
    with app.app_context():
        db = get_db()
        if args.command in ('init-admin','reset-password'):
            if args.command == 'init-admin' and db.execute('SELECT 1 FROM users LIMIT 1').fetchone():
                parser.error('Ya hay usuarios. Ingresá con el administrador existente o usá reset-password.')
            if not re.fullmatch(r'[A-Za-z0-9_.@-]{3,80}',args.username):
                parser.error('Nombre de usuario inválido.')
            password = getpass.getpass('Nueva contraseña (mínimo 10 caracteres): ')
            if password != getpass.getpass('Repetir contraseña: '):
                parser.error('Las contraseñas no coinciden.')
            hashed = password_hash(password)
            if args.command == 'init-admin':
                db.execute("INSERT INTO users(username,name,password_hash,role) VALUES(?,?,?,'admin')",(args.username,args.name,hashed))
            else:
                row = db.execute('SELECT id FROM users WHERE username=? COLLATE NOCASE',(args.username,)).fetchone()
                if not row:
                    parser.error('Usuario inexistente.')
                db.execute('UPDATE users SET password_hash=? WHERE id=?',(hashed,row['id']))
                db.execute('DELETE FROM sessions WHERE user_id=?',(row['id'],))
            db.commit()
            print('Usuario listo. La contraseña no se imprime ni se guarda en archivos de configuración.')
        elif args.command == 'seed-demo':
            if db.execute('SELECT 1 FROM clients LIMIT 1').fetchone():
                parser.error('La demostración requiere una base sin clientes.')
            admin_row = db.execute("SELECT id FROM users WHERE role='admin' LIMIT 1").fetchone()
            if not admin_row:
                parser.error('Ejecutá init-admin primero.')
            samples = [('Edificio Horizonte · DEMO','PCI','Torre Norte','Red de incendio',-2,'alta'),
                       ('Industria del Sur · DEMO','PCI','Planta de producción','Detección y alarma',1,'media'),
                       ('Centro Logístico · DEMO','AQUATECH','Depósito central','Bombas y red sanitaria',4,'media')]
            for i,(client,company,site,system,offset,priority) in enumerate(samples):
                cid = db.execute('INSERT INTO clients(name,company,contact) VALUES(?,?,?)',(client,company,'Contacto ficticio')).lastrowid
                sid = db.execute('INSERT INTO sites(client_id,name,address,system) VALUES(?,?,?,?)',(cid,site,'Dirección de ejemplo',system)).lastrowid
                oid = db.execute('INSERT INTO orders(site_id,title,service,scheduled_date,technician_id,priority) VALUES(?,?,?,?,?,?)',
                    (sid,'Mantenimiento preventivo','Inspección de ejemplo',(date.today()+timedelta(days=offset)).isoformat(),admin_row['id'],priority)).lastrowid
                if i == 0:
                    db.execute("UPDATE orders SET status='en_curso' WHERE id=?",(oid,))
                    db.execute('INSERT INTO observations(order_id,description,risk) VALUES(?,?,?)',(oid,'Ejemplo ficticio: componente pendiente de revisión.','alto'))
                    db.execute('INSERT INTO observations(order_id,description,risk,value) VALUES(?,?,?,0)',(oid,'Campo de control con valor cero (oculto en vista cliente).','bajo'))
            db.execute("INSERT OR REPLACE INTO settings VALUES('demo','1')")
            db.commit()
            print('Tres clientes ficticios creados. No se importaron datos de Cloud Gestión.')
        elif args.command == 'backup':
            destination = Path(args.destination).resolve()
            if destination.exists() or destination == Path(app.config['DATABASE']).resolve():
                parser.error('El destino ya existe; elegí otro nombre.')
            destination.parent.mkdir(parents=True,exist_ok=True)
            with sqlite3.connect(destination) as target:
                db.backup(target)
            os.chmod(destination,0o600)
            print(f'Copia creada: {destination}')
    if args.command == 'serve':
        from waitress import serve
        print(f'QTECH Gestión: http://{args.host}:{args.port}',flush=True)
        serve(app,host=args.host,port=args.port,threads=6)


if __name__ == '__main__':
    main()
