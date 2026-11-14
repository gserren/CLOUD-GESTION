import json
import tempfile
import unittest
from pathlib import Path
from backend.app import create_app
from backend.auth import password_hash
from backend.db import get_db

HEADERS = {'X-Qtech-Request':'1'}
TEST_PASSWORD = 'test-only-password-2026'


class ApplicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hashed = password_hash(TEST_PASSWORD)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app({'TESTING':True,'DATABASE':str(Path(self.tmp.name)/'test.db')})
        with self.app.app_context():
            db=get_db()
            db.executemany('INSERT INTO clients(id,name) VALUES(?,?)',[(1,'Cliente uno'),(2,'Cliente dos')])
            db.executemany('INSERT INTO sites(id,client_id,name) VALUES(?,?,?)',[(1,1,'Sitio uno'),(2,2,'Sitio dos')])
            for ident,username,role,cid in [(1,'admin','admin',None),(2,'tech','tecnico',None),(3,'client1','cliente',1),(4,'client2','cliente',2),(5,'tech2','tecnico',None)]:
                db.execute('INSERT INTO users VALUES(?,?,?,?,?,?,1)',(ident,username,username,self.hashed,role,cid))
            db.executemany('INSERT INTO orders(id,site_id,title,service,scheduled_date,technician_id,notes) VALUES(?,?,?,?,?,?,?)',
                 [(1,1,'Control uno','Inspección','2026-11-14',2,'INTERNAL_SECRET'),(2,2,'Control dos','Inspección','2026-11-15',5,'Nota privada')])
            db.commit()
        self.client=self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def login(self,username='admin',client=None):
        client=client or self.client
        response=client.post('/api/login',json={'username':username,'password':TEST_PASSWORD},headers=HEADERS)
        self.assertEqual(response.status_code,200,response.json)
        return {**HEADERS,'X-CSRF-Token':response.json['csrf']}

    def complete_and_report(self,order=1,publish=True):
        h=self.login()
        self.assertEqual(self.client.patch(f'/api/orders/{order}',json={'status':'en_curso'},headers=h).status_code,200)
        self.assertEqual(self.client.patch(f'/api/orders/{order}',json={'status':'completada','result':'Trabajo realizado.'},headers=h).status_code,200)
        r=self.client.post('/api/reports',json={'order_id':order},headers=h)
        self.assertEqual(r.status_code,201,r.json)
        if publish:
            self.assertEqual(self.client.post(f'/api/reports/{r.json["id"]}/publish',json={},headers=h).status_code,200)
        return r.json['id'],h

    def test_health_and_authentication_required(self):
        self.assertEqual(self.client.get('/api/health').status_code,200)
        self.assertEqual(self.client.get('/api/data').status_code,401)
        self.assertEqual(self.client.post('/api/login',json={'username':'admin','password':'wrong'},headers=HEADERS).status_code,401)

    def test_csrf_and_cross_origin(self):
        h=self.login()
        self.assertEqual(self.client.post('/api/clients',json={'name':'x'},headers=HEADERS).status_code,403)
        self.assertEqual(self.client.post('/api/clients',json={'name':'x'},headers={**h,'Origin':'https://evil.example'}).status_code,403)
        self.assertEqual(self.client.post('/api/login',json={'username':'admin','password':TEST_PASSWORD}).status_code,403)

    def test_client_isolation_and_preview_enforcement(self):
        self.login('client1')
        d=self.client.get('/api/data').json
        self.assertEqual([c['id'] for c in d['clients']],[1])
        self.assertEqual([s['id'] for s in d['sites']],[1])
        self.assertEqual(d['users'],[])
        self.assertEqual(self.client.get('/api/data?view_client=2').status_code,403)

    def test_technician_assignment(self):
        h=self.login('tech')
        d=self.client.get('/api/data').json
        self.assertEqual([o['id'] for o in d['orders']],[1])
        self.assertEqual([c['id'] for c in d['clients']],[1])
        self.assertEqual(self.client.patch('/api/orders/2',json={'status':'en_curso'},headers=h).status_code,404)
        self.assertEqual(self.client.post('/api/clients',json={'name':'x'},headers=h).status_code,403)
        self.assertEqual(self.client.post('/api/observations',json={'order_id':2,'description':'x','risk':'alto'},headers=h).status_code,404)

    def test_order_lifecycle_and_report(self):
        rid,h=self.complete_and_report()
        self.assertEqual(self.client.get(f'/api/reports/{rid}').json['revision'],1)
        self.assertEqual(self.client.patch('/api/orders/1',json={'result':'overwrite'},headers=h).status_code,409)
        self.assertEqual(self.client.patch('/api/orders/1',json={'status':'en_curso'},headers=h).status_code,200)

    def test_invalid_transitions_and_missing_result(self):
        h=self.login()
        self.assertEqual(self.client.patch('/api/orders/1',json={'status':'completada'},headers=h).status_code,409)
        self.assertEqual(self.client.patch('/api/orders/1',json={'status':'en_curso'},headers=h).status_code,200)
        self.assertEqual(self.client.patch('/api/orders/1',json={'status':'completada'},headers=h).status_code,400)
        self.assertEqual(self.client.post('/api/reports',json={'order_id':1},headers=h).status_code,409)

    def test_report_zero_filter_and_internal_notes_hidden(self):
        h=self.login()
        for value,description in [(0,'ZERO_HIDDEN'),(1,'VISIBLE_FINDING'),(None,'VISIBLE_TEXT')]:
            r=self.client.post('/api/observations',json={'order_id':1,'description':description,'risk':'alto','value':value},headers=h)
            self.assertEqual(r.status_code,201)
        rid,_=self.complete_and_report()
        internal=self.client.get(f'/api/reports/{rid}').json
        self.assertEqual(len(internal['snapshot']['observations']),3)
        preview=self.client.get(f'/api/reports/{rid}?view_client=1').json
        self.assertEqual(len(preview['snapshot']['observations']),2)
        self.login('client1')
        for url in ['/api/data',f'/api/reports/{rid}',f'/reports/{rid}']:
            r=self.client.get(url)
            self.assertEqual(r.status_code,200)
            self.assertNotIn('ZERO_HIDDEN',r.text)
            self.assertNotIn('INTERNAL_SECRET',r.text)
            self.assertIn('VISIBLE_FINDING',r.text)

    def test_unpublished_and_other_clients_reports_denied(self):
        rid,_=self.complete_and_report(publish=False)
        self.login('client1')
        self.assertEqual(self.client.get(f'/reports/{rid}').status_code,404)
        self.assertEqual(self.client.get('/api/data').json['reports'],[])
        h=self.login()
        self.client.post(f'/api/reports/{rid}/publish',json={},headers=h)
        self.login('client2')
        self.assertEqual(self.client.get(f'/api/reports/{rid}').status_code,404)
        self.assertEqual(self.client.get(f'/reports/{rid}').status_code,404)

    def test_report_snapshot_is_immutable(self):
        rid,h=self.complete_and_report()
        self.client.patch('/api/clients/1',json={'name':'Changed client'},headers=h)
        self.client.patch('/api/orders/1',json={'status':'en_curso','result':'Changed result'},headers=h)
        snap=self.client.get(f'/api/reports/{rid}').json['snapshot']
        self.assertEqual(snap['client']['name'],'Cliente uno')
        self.assertEqual(snap['order']['result'],'Trabajo realizado.')

    def test_admin_preview_is_filtered_on_server(self):
        self.complete_and_report(1)
        self.complete_and_report(2)
        d=self.client.get('/api/data?view_client=1').json
        self.assertEqual([c['id'] for c in d['clients']],[1])
        self.assertEqual(len(d['reports']),1)
        self.assertEqual(d['reports'][0]['client_id'],1)
        self.assertEqual(d['orders'],[])
        self.assertEqual(d['audit'],[])

    def test_logout_revokes_cookie(self):
        h=self.login()
        cookie=self.client.get_cookie('qtech_session').value
        self.client.post('/api/logout',json={},headers=h)
        self.client.set_cookie('qtech_session',cookie)
        self.assertEqual(self.client.get('/api/data').status_code,401)

    def test_disable_user_revokes_active_session(self):
        other=self.app.test_client()
        self.login('tech',other)
        h=self.login()
        self.assertEqual(self.client.patch('/api/users/2',json={'active':False},headers=h).status_code,200)
        self.assertEqual(other.get('/api/data').status_code,401)
        self.assertEqual(self.client.patch('/api/users/1',json={'active':False},headers=h).status_code,400)

    def test_password_change_revokes_all_sessions(self):
        other=self.app.test_client()
        self.login('admin',other)
        h=self.login()
        r=self.client.post('/api/password',json={'current_password':TEST_PASSWORD,'password':'new-test-only-password'},headers=h)
        self.assertEqual(r.status_code,200)
        self.assertEqual(other.get('/api/data').status_code,401)

    def test_validation_and_missing_relations(self):
        h=self.login()
        self.assertEqual(self.client.post('/api/orders',json={'site_id':999},headers=h).status_code,404)
        self.assertEqual(self.client.post('/api/clients',json={'name':''},headers=h).status_code,400)
        self.assertEqual(self.client.post('/api/observations',json={'order_id':1,'description':'x','risk':'invented'},headers=h).status_code,400)
        self.assertEqual(self.client.post('/api/users',json={'username':'new','name':'New','role':'cliente','client_id':999,'password':TEST_PASSWORD},headers=h).status_code,404)
        self.assertEqual(self.client.post('/api/clients',json=[],headers=h).status_code,400)

    def test_report_html_escapes_user_content(self):
        with self.app.app_context():
            get_db().execute('UPDATE clients SET name=? WHERE id=1',('<script>alert(1)</script>',))
            get_db().commit()
        rid,_=self.complete_and_report()
        html=self.client.get(f'/reports/{rid}').text
        self.assertNotIn('<script>alert(1)</script>',html)
        self.assertIn('&lt;script&gt;',html)

    def test_records_persist_after_restart(self):
        h=self.login()
        self.client.post('/api/clients',json={'name':'Persistent client'},headers=h)
        app2=create_app({'TESTING':True,'DATABASE':self.app.config['DATABASE']})
        with app2.app_context():
            self.assertIsNotNone(get_db().execute("SELECT id FROM clients WHERE name='Persistent client'").fetchone())

    def test_login_rate_limit(self):
        for _ in range(10):
            r=self.client.post('/api/login',json={'username':'admin','password':'wrong'},headers=HEADERS)
            self.assertEqual(r.status_code,401)
        r=self.client.post('/api/login',json={'username':'admin','password':TEST_PASSWORD},headers=HEADERS)
        self.assertEqual(r.status_code,429)

    def test_observation_resolution_requires_open_order(self):
        h=self.login('tech')
        r=self.client.post('/api/observations',json={'order_id':1,'description':'Hallazgo','risk':'alto'},headers=h)
        oid=r.json['id']
        self.assertEqual(self.client.patch(f'/api/observations/{oid}',json={'resolution':'Corregido'},headers=h).status_code,200)
        self.assertEqual(self.client.patch(f'/api/observations/{oid}',json={'resolution':'Otra'},headers=h).status_code,409)

    def test_full_workflow_with_new_records(self):
        h=self.login()
        r=self.client.post('/api/clients',json={'name':'Nuevo cliente'},headers=h)
        self.assertEqual(r.status_code,201,r.json)
        cid=r.json['id']
        r=self.client.post('/api/sites',json={'client_id':cid,'name':'Planta nueva'},headers=h)
        self.assertEqual(r.status_code,201,r.json)
        sid=r.json['id']
        r=self.client.post('/api/users',json={'name':'Cliente nuevo','username':'new-client','role':'cliente','client_id':cid,'password':TEST_PASSWORD},headers=h)
        self.assertEqual(r.status_code,201,r.json)
        r=self.client.post('/api/orders',json={'site_id':sid,'title':'Trabajo nuevo','service':'Inspección','scheduled_date':'2026-11-14','technician_id':2},headers=h)
        self.assertEqual(r.status_code,201,r.json)
        oid=r.json['id']
        tech=self.login('tech')
        self.assertEqual(self.client.patch(f'/api/orders/{oid}',json={'status':'en_curso'},headers=tech).status_code,200)
        self.assertEqual(self.client.post('/api/observations',json={'order_id':oid,'description':'Hallazgo nuevo','risk':'alto'},headers=tech).status_code,201)
        self.assertEqual(self.client.patch(f'/api/orders/{oid}',json={'status':'completada','result':'Intervención terminada'},headers=tech).status_code,200)
        r=self.client.post('/api/reports',json={'order_id':oid},headers=tech)
        self.assertEqual(r.status_code,201,r.json)
        rid=r.json['id']
        self.assertEqual(self.client.post(f'/api/reports/{rid}/publish',json={},headers=tech).status_code,403)
        h=self.login()
        self.assertEqual(self.client.post(f'/api/reports/{rid}/publish',json={},headers=h).status_code,200)
        self.login('new-client')
        d=self.client.get('/api/data').json
        self.assertEqual(len(d['reports']),1)
        self.assertEqual(d['reports'][0]['snapshot']['order']['result'],'Intervención terminada')
        self.assertEqual(self.client.get(f'/reports/{rid}').status_code,200)

    def test_frontend_assets_and_headers(self):
        for path in ['/','/static/app.js','/static/style.css','/static/fonts.css','/static/favicon.svg','/static/report.js']:
            response=self.client.get(path)
            self.assertEqual(response.status_code,200,path)
            self.assertEqual(response.headers['X-Content-Type-Options'],'nosniff')
            response.close()
        self.assertEqual(self.client.get('/api/session').headers['Cache-Control'],'no-store')


if __name__=='__main__':
    unittest.main()
