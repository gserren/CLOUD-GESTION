import hashlib
import importlib.util
import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

spec = importlib.util.spec_from_file_location('migration_guard', Path(__file__).resolve().parents[1] / 'scripts/check_migration.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class MigrationGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def archive(self, name, *, omit=False, corrupt=False, change_name=False, snapshot='{}', extra=False):
        dbpath = self.root / (name + '.sqlite3')
        root = Path(__file__).resolve().parents[1]
        with sqlite3.connect(dbpath) as db:
            db.executescript((root / 'backend/schema.sql').read_text())
            db.executescript((root / 'backend/migrations/002_documents.sql').read_text())
            db.execute("INSERT INTO clients(id,name,company) VALUES(1,'Demo','QTECH')")
            data = b'Original ficticio para prueba'
            sha = hashlib.sha256(data).hexdigest()
            if not omit:
                db.execute("INSERT INTO documents(id,source_system,source_id,source_revision,sha256,byte_size,original_name,kind,client_id) VALUES(1,'test','1','1',?,?,?,'parte',1)", (sha,len(data),'changed.pdf' if change_name else 'demo.pdf'))
            if extra:
                db.execute("INSERT INTO documents(id,source_system,source_id,source_revision,sha256,byte_size,original_name,kind,client_id) VALUES(2,'test','2','1',?,?,'demo2.pdf','parte',1)",(sha,len(data)))
            db.execute("INSERT INTO sites(id,client_id,name) VALUES(1,1,'Demo')")
            db.execute("INSERT INTO orders(id,site_id,title,service,scheduled_date) VALUES(1,1,'Demo','Demo','2026-01-01')")
            db.execute("INSERT INTO users(id,username,name,password_hash,role) VALUES(1,'demo','Demo','not-a-real-hash','admin')")
            db.execute("INSERT INTO reports(id,order_id,client_id,revision,snapshot,created_by) VALUES(1,1,1,1,?,1)", (snapshot,))
        target=self.root/(name+'.zip')
        with zipfile.ZipFile(target,'w') as z:
            z.write(dbpath,'qtech.sqlite3')
            if not omit or extra:z.writestr('documents/'+sha[:2]+'/'+sha,b'damaged' if corrupt else data)
        return target

    def test_accepts_identical_and_additive_copy(self):
        old=self.archive('old');new=self.archive('new',extra=True)
        result=guard.check(new,old)
        self.assertTrue(result['previous_records_preserved'])
        self.assertEqual(result['counts']['documents'],2)
        self.assertEqual(result['unique_files'],1)
        self.assertEqual(result['source_completeness'],'not_assessed')

    def test_rejects_lost_original(self):
        old=self.archive('old');new=self.archive('new',omit=True)
        with self.assertRaisesRegex(ValueError,'faltan'):guard.check(new,old)

    def test_rejects_modified_original_metadata(self):
        old=self.archive('old');new=self.archive('new',change_name=True)
        with self.assertRaisesRegex(ValueError,'original previo'):guard.check(new,old)

    def test_rejects_modified_report_snapshot(self):
        old=self.archive('old');new=self.archive('new',snapshot='{"changed":true}')
        with self.assertRaisesRegex(ValueError,'instantánea'):guard.check(new,old)

    def test_rejects_damaged_bytes(self):
        with self.assertRaisesRegex(ValueError,'original|SHA-256'):guard.check(self.archive('damaged',corrupt=True))

    def test_rejects_unsafe_zip_path(self):
        file=self.archive('unsafe')
        with zipfile.ZipFile(file,'a') as z:z.writestr('../escape','x')
        with self.assertRaisesRegex(ValueError,'Ruta'):guard.check(file)

if __name__=='__main__':unittest.main()
