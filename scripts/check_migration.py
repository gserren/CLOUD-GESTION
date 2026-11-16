#!/usr/bin/env python3
"""Verify a QTECH archive and reject loss of already copied originals/records.

Read-only validation. Does not connect to CG, import records, or certify that
an archive contains all records in CG. No third-party dependencies.
"""
import argparse
import hashlib
import json
import sqlite3
import tempfile
import zipfile
from pathlib import Path

TABLES = ('clients', 'sites', 'users', 'orders', 'observations', 'reports',
          'documents', 'audit', 'document_imports')
ORIGINAL_FIELDS = ('source_system', 'source_id', 'source_revision', 'sha256',
                   'byte_size', 'original_name', 'source_reference', 'kind',
                   'mime_type', 'source_url', 'source_created_at',
                   'source_modified_at', 'source_metadata')


def digest_stream(stream):
    h = hashlib.sha256()
    size = 0
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        h.update(chunk)
        size += len(chunk)
    return h.hexdigest(), size


def inspect_archive(path):
    with zipfile.ZipFile(path) as archive, tempfile.TemporaryDirectory() as tmp:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('El ZIP contiene nombres duplicados.')
        for name in names:
            p = Path(name)
            if p.is_absolute() or '..' in p.parts or '\\' in name:
                raise ValueError('Ruta de ZIP no segura.')
        info = archive.getinfo('qtech.sqlite3')
        if info.file_size > 1024 * 1024 * 1024:
            raise ValueError('La instantánea de base supera el límite de 1 GiB.')
        snapshot = Path(tmp) / 'qtech.sqlite3'
        with snapshot.open('xb') as out, archive.open(info) as src:
            for chunk in iter(lambda: src.read(1024 * 1024), b''):
                out.write(chunk)
        with sqlite3.connect(snapshot.as_uri() + '?mode=ro', uri=True) as db:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA query_only=ON')
            if [r[0] for r in db.execute('PRAGMA integrity_check')] != ['ok']:
                raise ValueError('La base de datos no supera integrity_check.')
            if db.execute('PRAGMA foreign_key_check').fetchone():
                raise ValueError('La base tiene relaciones inválidas.')
            tables = {t: {r['id']: dict(r) for r in db.execute('SELECT * FROM ' + t)} for t in TABLES}
        files = {}
        for row in tables['documents'].values():
            digest, size = row['sha256'], row['byte_size']
            if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
                raise ValueError('Huella registrada inválida.')
            if digest not in files:
                blob = archive.getinfo('documents/' + digest[:2] + '/' + digest)
                if type(size) is not int or not 0 < size <= 500 * 1024 * 1024 or blob.file_size != size:
                    raise ValueError('Tamaño de original inválido o superior a 500 MiB.')
                with archive.open(blob) as stream:
                    files[digest] = digest_stream(stream)
            if files[digest] != (digest, size):
                raise ValueError('Un original no coincide con su SHA-256 o tamaño registrado.')
        return tables, files


def check(candidate, previous=None):
    current, files = inspect_archive(candidate)
    retained = False
    if previous:
        old, old_files = inspect_archive(previous)
        for table in TABLES:
            missing = set(old[table]) - set(current[table])
            if missing:
                raise ValueError(f'Actualización rechazada: faltan {len(missing)} registros previos de {table}.')
        for ident, row in old['documents'].items():
            if any(row[k] != current['documents'][ident][k] for k in ORIGINAL_FIELDS):
                raise ValueError('Actualización rechazada: se modificó un original previo; conservarlo y agregar una versión.')
        for ident, row in old['reports'].items():
            if row['snapshot'] != current['reports'][ident]['snapshot']:
                raise ValueError('Actualización rechazada: cambió una instantánea histórica de reporte.')
        if not set(old_files).issubset(files):
            raise ValueError('Actualización rechazada: faltan originales previos.')
        retained = True
    return {'archive_verified': True, 'previous_records_preserved': retained if previous else None,
            'counts': {table: len(rows) for table, rows in current.items()},
            'unique_files': len(files), 'unique_original_bytes': sum(v[1] for v in files.values()),
            'source_completeness': 'not_assessed',
            'note': 'Verifica la copia disponible; no demuestra una exportación completa de la base de CG.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--previous', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(check(args.candidate, args.previous), ensure_ascii=False, indent=2))
    except (ValueError, KeyError, OSError, sqlite3.Error, zipfile.BadZipFile) as error:
        print(json.dumps({'archive_verified': False, 'error': str(error)}, ensure_ascii=False))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
