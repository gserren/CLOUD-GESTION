"""Prueba opcional en Chromium headless. No opera el navegador del usuario.

Instalar Playwright en el intérprete de esta prueba. La aplicación utiliza
.venv/bin/python si existe. CHROMIUM_PATH permite elegir un Chromium instalado.
"""
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    executable = ROOT / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    python = str(executable) if executable.exists() else sys.executable
    with tempfile.TemporaryDirectory() as tmp:
        password = secrets.token_urlsafe(22)
        env = {**os.environ,'QTECH_DATABASE':str(Path(tmp)/'browser.sqlite3'),'QTECH_HOSTS':'127.0.0.1,localhost'}
        setup = '''import json,sys
from backend.app import create_app
from backend.auth import password_hash
from backend.db import get_db
app=create_app()
with app.app_context():
 db=get_db()
 db.execute("INSERT INTO users(username,name,password_hash,role) VALUES('admin','Administración DEMO',?,'admin')",(password_hash(json.load(sys.stdin)['password']),))
 db.commit()
'''
        subprocess.run([python,'-c',setup],input=json.dumps({'password':password}),text=True,env=env,cwd=ROOT,check=True,capture_output=True)
        subprocess.run([python,'manage.py','seed-demo'],env=env,cwd=ROOT,check=True,capture_output=True)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        origin=f'http://127.0.0.1:{port}'
        server=subprocess.Popen([python,'manage.py','serve','--port',str(port)],env=env,cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        try:
            for _ in range(100):
                try:
                    urllib.request.urlopen(origin+'/api/health',timeout=1).close();break
                except OSError:
                    if server.poll() is not None:raise RuntimeError(server.stderr.read().decode())
                    time.sleep(.1)
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'))
                page=browser.new_page(viewport={'width':1440,'height':1000})
                failures=[]
                page.on('pageerror',lambda e:failures.append(str(e)))
                page.goto(origin)
                page.get_by_label('Usuario',exact=True).fill('admin')
                page.get_by_label('Contraseña',exact=True).fill(password)
                page.get_by_role('button',name='Ingresar').click()
                page.get_by_role('heading',name='El mantenimiento, bajo control').wait_for()
                out=ROOT/'test-results';out.mkdir(exist_ok=True)
                page.screenshot(path=str(out/'dashboard.png'),full_page=True)

                page.locator('[data-nav="clients"]').first.click()
                page.get_by_role('button',name='Nuevo cliente').click()
                page.get_by_label('Nombre del cliente').fill('Cliente QA · FICTICIO')
                page.get_by_label('Contacto',exact=True).fill('Contacto de prueba')
                page.get_by_role('button',name='Guardar',exact=True).click()
                page.get_by_role('heading',name='Cliente QA · FICTICIO').wait_for()
                page.locator('[data-nav="sites"]').click()
                page.get_by_role('button',name='Nueva instalación').click()
                page.get_by_label('Cliente',exact=True).select_option(label='Cliente QA · FICTICIO')
                page.get_by_label('Nombre de la instalación').fill('Sitio QA')
                page.get_by_role('button',name='Guardar',exact=True).click()
                page.get_by_text('Sitio QA',exact=True).wait_for()
                page.locator('[data-nav="orders"]').first.click()
                page.get_by_role('button',name='Nueva orden').click()
                page.get_by_label('Instalación',exact=True).select_option(label='Cliente QA · FICTICIO / Sitio QA')
                page.get_by_label('Título',exact=True).fill('Servicio QA')
                page.get_by_label('Servicio',exact=True).fill('Prueba funcional')
                page.get_by_label('Responsable',exact=True).select_option(label='Administración DEMO')
                page.get_by_label('Notas internas').fill('NOTA_INTERNA_QA')
                page.get_by_role('button',name='Guardar',exact=True).click()
                page.get_by_role('button',name='OT-0004 · Servicio QA').click()
                page.get_by_role('button',name='Actualizar orden').click()
                page.get_by_label('Estado',exact=True).select_option('en_curso')
                page.get_by_role('button',name='Guardar',exact=True).click()
                for description,value in [('HALLAZGO_CERO_QA','0'),('Hallazgo visible QA','1')]:
                    page.get_by_role('button',name='Agregar',exact=False).click()
                    page.get_by_label('Descripción del hallazgo').fill(description)
                    page.get_by_label('Riesgo',exact=True).select_option('alto')
                    page.get_by_label('Valor numérico (opcional)').fill(value)
                    page.get_by_role('button',name='Guardar',exact=True).click()
                    page.get_by_role('heading',name='OT-0004 · Servicio QA').wait_for()
                page.get_by_role('button',name='Actualizar orden').click()
                page.get_by_label('Estado',exact=True).select_option('completada')
                page.get_by_label('Resultado de la intervención').fill('Verificación del circuito completo.')
                page.get_by_role('button',name='Guardar',exact=True).click()
                page.get_by_role('button',name='Generar reporte').click()
                page.get_by_role('button',name='Publicar al cliente').click()
                page.get_by_text('Publicado',exact=True).wait_for()

                page.locator('[data-nav="clients"]').click()
                card=page.locator('.client-card').filter(has=page.get_by_role('heading',name='Cliente QA · FICTICIO'))
                card.get_by_role('button',name='Vista de cliente').click()
                page.get_by_role('heading',name='Tus servicios, a la vista').wait_for()
                assert page.get_by_text('Hallazgo visible QA',exact=True).count()==1
                assert 'HALLAZGO_CERO_QA' not in page.locator('body').inner_text()
                assert 'NOTA_INTERNA_QA' not in page.locator('body').inner_text()
                with page.expect_popup() as popup_info:
                    page.get_by_role('link',name='Ver reporte').first.click()
                report=popup_info.value;report.wait_for_load_state()
                assert 'HALLAZGO_CERO_QA' not in report.locator('body').inner_text()
                assert 'NOTA_INTERNA_QA' not in report.locator('body').inner_text()
                assert 'Hallazgo visible QA' in report.locator('body').inner_text()
                report.close()
                page.screenshot(path=str(out/'portal-cliente.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                page.screenshot(path=str(out/'mobile.png'),full_page=True)
                page.get_by_role('button',name='Volver a administración').click()
                page.set_viewport_size({'width':1440,'height':1000})
                page.locator('[data-nav="users"]').click()
                page.get_by_role('button',name='Nuevo usuario').click()
                page.get_by_label('Nombre',exact=True).fill('Cliente de prueba')
                page.get_by_label('Usuario',exact=True).fill('qa-cliente')
                page.get_by_label('Rol',exact=True).select_option('cliente')
                page.get_by_label('Cliente (solo para rol Cliente)').select_option(label='Cliente QA · FICTICIO')
                page.get_by_label('Contraseña inicial').fill(password)
                page.get_by_role('button',name='Guardar',exact=True).click()
                page.get_by_text('qa-cliente',exact=True).wait_for()
                page.get_by_role('button',name='Cerrar sesión',exact=True).click()
                page.get_by_label('Usuario',exact=True).fill('qa-cliente')
                page.get_by_label('Contraseña',exact=True).fill(password)
                page.get_by_role('button',name='Ingresar').click()
                page.get_by_role('heading',name='Tus servicios, a la vista').wait_for()
                assert page.locator('[data-nav="users"]').count()==0
                assert 'Edificio Horizonte' not in page.locator('body').inner_text()
                assert 'HALLAZGO_CERO_QA' not in page.locator('body').inner_text()
                assert not failures, failures
                browser.close()
                print('OK: circuito completo en navegador, portal cliente, impresión y móvil; sin errores JavaScript.')
        finally:
            server.terminate();server.communicate(timeout=10)


if __name__=='__main__':
    main()
