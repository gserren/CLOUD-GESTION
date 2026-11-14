import hashlib
import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from backend.app import create_app
from backend.auth import password_hash
from backend.db import get_db
from backend.documents import import_manifest, verify_archive, blob_path, backup_archive


class DocumentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = 'test-only-password-2026'
        cls.hashed = password_hash(cls.password)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.app = create_app({'TESTING':True,'DATABASE':str(self.root/'data.db')})
        self.ctx = self.app.app_context()
        self.ctx.push()
        db = get_db()
        db.executemany('INSERT INTO clients(id,name) VALUES(?,?)', [(1,'Uno'),(2,'Dos')])
        db.executemany('INSERT INTO sites(id,client_id,name) VALUES(?,?,?)', [(1,1,'Uno'),(2,2,'Dos')])
        db.execute("INSERT INTO orders(id,site_id,title,service,scheduled_date) VALUES(1,1,'Test','Test','2026-11-14')")
        for name, role, cid in [('admin','admin',None),('tech','tecnico',None),('client','cliente',1)]:
            db.execute('INSERT INTO users(username,name,password_hash,role,client_id) VALUES(?,?,?,?,?)', (name,name,self.hashed,role,cid))
        db.commit()
        self.export = self.root/'export'
        self.export.mkdir()
        self.manifest = self.export/'manifest.json'
        self.client = self.app.test_client()

    def tearDown(self):
        self.ctx.pop()
        self.tmp.cleanup()

    def entry(self, ident='one', content=b'%PDF-1.4\nsynthetic original\n', **extra):
        path = self.export/(ident+'.pdf')
        path.write_bytes(content)
        return dict(path=path.name, source_system='test-export',source_id=ident,source_revision='v1',
                    original_name='service.pdf',kind='parte_trabajo',mime_type='application/pdf',
                    byte_size=len(content),sha256=hashlib.sha256(content).hexdigest(),**extra)

    def run_import(self, entries, commit=True):
        self.manifest.write_text(json.dumps({'version':1,'documents':entries}))
        return import_manifest(self.manifest, commit=commit)

    def login(self, name='admin'):
        r = self.client.post('/api/login',json={'username':name,'password':self.password},headers={'X-Qtech-Request':'1'})
        self.assertEqual(r.status_code,200)
        return {'X-Qtech-Request':'1','X-CSRF-Token':r.json['csrf']}

    def test_preview_is_read_only_and_invalid_batch_is_atomic(self):
        a = self.entry()
        self.assertEqual(self.run_import([a],False)['created'],1)
        self.assertFalse(Path(self.app.config['DOCUMENT_ROOT']).exists())
        b = self.entry('two')
        b['sha256'] = '0'*64
        self.assertEqual(self.run_import([a,b])['mode'],'rejected')
        self.assertEqual(get_db().execute('SELECT count(*) FROM documents').fetchone()[0],0)

    def test_originals_dedup_sources_revisions_and_idempotency(self):
        a,b = self.entry('one'),self.entry('two')
        self.assertEqual(self.run_import([a,b,a])['created'],2)
        self.assertEqual(self.run_import([a,b])['existing'],2)
        self.assertEqual(verify_archive(),{'documents':2,'unique_files':1,'errors':[]})
        new = self.entry('one', b'%PDF-1.4\nchanged original\n')
        result = self.run_import([new])
        self.assertEqual((result['created'],result['new_versions']),(1,1))
        self.assertEqual(blob_path(a['sha256']).read_bytes(),b'%PDF-1.4\nsynthetic original\n')
        self.assertEqual(verify_archive()['unique_files'],2)

    def test_traversal_symlink_and_size_rejected(self):
        a = self.entry()
        for path in ('../data.db', str(self.root/'data.db'), 'a\\b.pdf'):
            self.assertEqual(self.run_import([{**a,'path':path}])['mode'],'rejected')
        (self.export/'link.pdf').symlink_to(self.export/a['path'])
        self.assertEqual(self.run_import([{**a,'path':'link.pdf'}])['mode'],'rejected')
        self.assertEqual(self.run_import([{**a,'byte_size':1}])['mode'],'rejected')

    def test_private_download_auth_preview_headers_and_integrity(self):
        a = self.entry()
        self.run_import([a])
        self.assertEqual(self.client.get('/api/documents/1/download').status_code,401)
        for name in ('client','tech'):
            self.login(name)
            self.assertEqual(self.client.get('/api/documents/1/download').status_code,403)
            self.assertEqual(self.client.get('/api/data').json['documents'],[])
        self.login()
        self.assertEqual(self.client.get('/api/data?view_client=1').json['documents'],[])
        self.assertEqual(self.client.get('/api/documents/1/download?view_client=1').status_code,404)
        r = self.client.get('/api/documents/1/download')
        self.assertEqual(r.status_code,200)
        self.assertEqual(hashlib.sha256(r.data).hexdigest(),a['sha256'])
        self.assertEqual(r.headers['Cache-Control'],'no-store')
        self.assertIn('attachment',r.headers['Content-Disposition'])
        self.assertEqual(r.mimetype,'application/octet-stream')
        r.close()
        self.assertEqual(self.client.get('/static/../instance/documents/'+a['sha256']).status_code,404)
        blob_path(a['sha256']).write_bytes(b'corrupt')
        self.assertEqual(self.client.get('/api/documents/1/download').status_code,503)
        self.assertEqual(len(verify_archive()['errors']),1)

    def test_association_consistency_csrf_and_immutable_source(self):
        a = self.entry(order_id=1)
        self.run_import([a])
        doc = dict(get_db().execute('SELECT * FROM documents').fetchone())
        self.assertEqual((doc['client_id'],doc['site_id'],doc['order_id']),(1,1,1))
        h = self.login()
        url = '/api/documents/1/association'
        self.assertEqual(self.client.patch(url,json={'client_id':2},headers={'X-Qtech-Request':'1'}).status_code,403)
        self.assertEqual(self.client.patch(url,json={'client_id':2,'site_id':1},headers=h).status_code,400)
        self.assertEqual(self.client.patch(url,json={'sha256':'x'},headers=h).status_code,400)
        self.assertEqual(self.client.patch(url,json={'client_id':2,'site_id':2},headers=h).status_code,200)
        doc2 = dict(get_db().execute('SELECT * FROM documents').fetchone())
        self.assertEqual(doc2['sha256'],doc['sha256'])
        self.assertEqual(doc2['client_id'],2)
        self.assertIsNone(doc2['order_id'])

    def test_backup_restores_database_and_original_bytes(self):
        a = self.entry()
        self.run_import([a])
        backup = self.root/'backup.zip'
        backup_archive(backup)
        with self.assertRaises(ValueError):
            backup_archive(backup)
        restore = self.root/'restore'
        with zipfile.ZipFile(backup) as z:
            self.assertIsNone(z.testzip())
            z.extractall(restore)
        app2 = create_app({'TESTING':True,'DATABASE':str(restore/'qtech.sqlite3')})
        with app2.app_context():
            self.assertEqual(verify_archive(),{'documents':1,'unique_files':1,'errors':[]})
            self.assertEqual(get_db().execute('SELECT count(*) FROM clients').fetchone()[0],2)

    def test_schema_migration_preserves_v1_data(self):
        old = self.root/'v1.db'
        with sqlite3.connect(old) as db:
            db.executescript((Path(__file__).parents[1]/'backend/schema.sql').read_text())
            db.execute("INSERT INTO clients(name) VALUES('Preservar')")
        app2 = create_app({'TESTING':True,'DATABASE':str(old)})
        with app2.app_context():
            self.assertEqual(get_db().execute('SELECT name FROM clients').fetchone()[0],'Preservar')
            self.assertEqual(get_db().execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()[0],'2')
            self.assertEqual(verify_archive()['documents'],0)

    def test_conflicting_metadata_and_credentials_rejected(self):
        a = self.entry()
        self.assertEqual(self.run_import([a,{**a,'kind':'factura'}])['mode'],'rejected')
        self.assertEqual(self.run_import([{**a,'source_url':'https://user:secret@example.com'}])['mode'],'rejected')
        self.assertEqual(self.run_import([{**a,'source_url':'https://example.com/?token=secret'}])['mode'],'rejected')

    def test_versions_in_one_batch_have_matching_preview_and_commit_counts(self):
        a = self.entry('first')
        b = self.entry('second',b'%PDF-1.4\nsecond version\n')
        b['source_id'] = a['source_id']
        preview = self.run_import([a,b],False)
        imported = self.run_import([a,b])
        self.assertEqual(preview['new_versions'],1)
        for key in ('created','existing','new_versions','unassociated'):
            self.assertEqual(preview[key],imported[key])


if __name__ == '__main__':
    unittest.main()
