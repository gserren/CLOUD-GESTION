"""Archivo privado de originales y migración local verificable, sin acceso de red."""
import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import urlsplit
from flask import current_app
from .db import get_db, rows

MAX_FILE = 500 * 1024 * 1024


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def blob_path(digest):
    if not isinstance(digest, str) or not re.fullmatch('[a-f0-9]{64}', digest):
        raise ValueError('Huella de archivo inválida.')
    root = Path(current_app.config['DOCUMENT_ROOT']).resolve()
    path = root / digest[:2] / digest
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError('El archivo privado no puede ser un enlace simbólico.')
    return path


def association(client_id=None, site_id=None, order_id=None):
    """Comprueba consistencia y completa relaciones desde orden o instalación."""
    db = get_db()
    ids = [client_id, site_id, order_id]
    for value in ids:
        if value is not None and (type(value) is not int or value <= 0):
            raise ValueError('Las asociaciones deben ser identificadores positivos o null.')
    if order_id:
        row = db.execute('SELECT site_id FROM orders WHERE id=?', (order_id,)).fetchone()
        if not row or (site_id and row['site_id'] != site_id):
            raise ValueError('Orden e instalación no coinciden.')
        site_id = row['site_id']
    if site_id:
        row = db.execute('SELECT client_id FROM sites WHERE id=?', (site_id,)).fetchone()
        if not row or (client_id and row['client_id'] != client_id):
            raise ValueError('Instalación y cliente no coinciden.')
        client_id = row['client_id']
    if client_id and not db.execute('SELECT 1 FROM clients WHERE id=?', (client_id,)).fetchone():
        raise ValueError('Cliente inexistente.')
    return client_id, site_id, order_id


def _string(item, key, limit=500, required=False):
    value = item.get(key, '')
    if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError(f'{key}: texto inválido.')
    if required and not value.strip():
        raise ValueError(f'Falta {key}.')
    return value


def _entry(item, root):
    if not isinstance(item, dict):
        raise ValueError('Documento inválido.')
    relative = _string(item, 'path', 2000, True)
    p = Path(relative)
    if p.is_absolute() or '..' in p.parts or '\\' in relative:
        raise ValueError('La ruta debe estar dentro de la carpeta de exportación.')
    source = root / p
    if any((root / Path(*p.parts[:i])).is_symlink() for i in range(1, len(p.parts)+1)):
        raise ValueError('No se admiten enlaces simbólicos en la exportación.')
    if not source.is_file() or not source.resolve().is_relative_to(root):
        raise ValueError('Original inexistente o fuera de la exportación.')
    size = source.stat().st_size
    if not 0 < size <= MAX_FILE or type(item.get('byte_size')) is not int or item['byte_size'] != size:
        raise ValueError('El tamaño no coincide o supera 500 MiB.')
    digest = file_hash(source)
    if digest != item.get('sha256'):
        raise ValueError('La huella SHA-256 no coincide con el original.')
    data = {key:_string(item, key, required=key in ('source_system','source_id','original_name','kind'))
            for key in ('source_system','source_id','source_revision','source_reference','original_name','kind',
                        'mime_type','source_created_at','source_modified_at')}
    if '/' in data['original_name'] or '\\' in data['original_name'] or data['original_name'] in ('.','..'):
        raise ValueError('El nombre original debe ser un nombre de archivo.')
    url = _string(item, 'source_url', 2000)
    if url:
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('URL de referencia inválida; no se permiten credenciales.')
        if parsed.query and any(k in parsed.query.lower() for k in ('token', 'signature', 'sig=', 'key=', 'password')):
            raise ValueError('Usá una URL estable, sin credenciales temporales.')
    metadata = item.get('source_metadata', {})
    if not isinstance(metadata, dict):
        raise ValueError('source_metadata debe ser un objeto.')
    metadata = json.dumps(metadata, ensure_ascii=False, allow_nan=False)
    if len(metadata) > 20000:
        raise ValueError('Metadatos demasiado extensos.')
    cid, sid, oid = association(item.get('client_id'), item.get('site_id'), item.get('order_id'))
    data.update(source_url=url, source_metadata=metadata, sha256=digest, byte_size=size,
                client_id=cid, site_id=sid, order_id=oid)
    return data, source


def _load_manifest(path):
    path = Path(path).resolve()
    if path.stat().st_size > 20 * 1024 * 1024:
        raise ValueError('Manifiesto demasiado grande; dividí la exportación en lotes.')
    manifest = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(manifest, dict) or manifest.get('version') != 1:
        raise ValueError('Se requiere un manifiesto de versión 1.')
    entries = manifest.get('documents')
    if not isinstance(entries, list) or not entries or len(entries) > 10000:
        raise ValueError('Se requieren entre 1 y 10000 documentos por lote.')
    valid, errors = [], []
    seen = {}
    for i, item in enumerate(entries):
        try:
            data, source = _entry(item, path.parent)
            key = (data['source_system'], data['source_id'], data['source_revision'], data['sha256'])
            if key in seen and data != seen[key]:
                raise ValueError('La misma identidad tiene metadatos contradictorios dentro del lote.')
            seen[key] = data
            valid.append((data, source))
        except (ValueError, OSError) as error:
            errors.append({'index':i, 'error':str(error)})
    return manifest, valid, errors


def import_manifest(path, commit=False):
    manifest, entries, errors = _load_manifest(path)
    result = dict(mode='imported' if commit else 'preview', total=len(manifest['documents']),
                  created=0, existing=0, new_versions=0, unassociated=0, errors=errors)
    if errors:
        result['mode'] = 'rejected'
        return result
    db = get_db()
    root = Path(current_app.config['DOCUMENT_ROOT'])
    staging = None
    try:
        if commit:
            root.mkdir(mode=0o700, parents=True, exist_ok=True)
            # Copy and rehash before beginning the metadata transaction.
            staging = tempfile.TemporaryDirectory(prefix='.import-', dir=root)
            for data, source in entries:
                target = Path(staging.name) / data['sha256']
                if not target.exists():
                    with source.open('rb') as inp, target.open('xb') as out:
                        os.chmod(target, 0o600)
                        shutil.copyfileobj(inp, out, 1024*1024)
                        out.flush()
                        os.fsync(out.fileno())
                    if file_hash(target) != data['sha256'] or target.stat().st_size != data['byte_size']:
                        raise ValueError('El original cambió durante la copia. No se importó el lote.')
            db.execute('BEGIN IMMEDIATE')
        seen = set()
        sources = set()
        for data, _ in entries:
            key = (data['source_system'], data['source_id'], data['source_revision'], data['sha256'])
            old = db.execute('SELECT id FROM documents WHERE source_system=? AND source_id=? AND source_revision=? AND sha256=?', key).fetchone()
            if old or key in seen:
                result['existing'] += 1
                continue
            seen.add(key)
            if key[:2] in sources or db.execute('SELECT 1 FROM documents WHERE source_system=? AND source_id=?', key[:2]).fetchone():
                result['new_versions'] += 1
            sources.add(key[:2])
            result['created'] += 1
            result['unassociated'] += data['client_id'] is None
            if commit:
                # Validate again while holding the write lock.
                association(data['client_id'], data['site_id'], data['order_id'])
                target = blob_path(data['sha256'])
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                if target.exists():
                    if file_hash(target) != data['sha256'] or target.stat().st_size != data['byte_size']:
                        raise ValueError('Hay un original almacenado dañado. Importación cancelada.')
                else:
                    os.replace(Path(staging.name)/data['sha256'], target)
                keys = list(data)
                ident = db.execute('INSERT INTO documents('+','.join(keys)+') VALUES('+','.join('?' for _ in keys)+')',
                                   tuple(data.values())).lastrowid
                db.execute("INSERT INTO audit(action,entity,entity_id) VALUES('imported_original','documents',?)", (ident,))
        if commit:
            db.execute('INSERT INTO document_imports(manifest_sha256,result) VALUES(?,?)',
                       (file_hash(path), json.dumps(result)))
            db.commit()
    except Exception:
        if commit:
            db.rollback()
        raise
    finally:
        if staging:
            staging.cleanup()
    return result


def verify_archive():
    docs = rows('SELECT id,sha256,byte_size FROM documents')
    errors = []
    checked = {}
    for doc in docs:
        try:
            if doc['sha256'] not in checked:
                p = blob_path(doc['sha256'])
                checked[doc['sha256']] = (file_hash(p), p.stat().st_size)
            if checked[doc['sha256']] != (doc['sha256'], doc['byte_size']):
                raise ValueError('El contenido o tamaño difiere del registrado.')
        except (ValueError, OSError) as error:
            errors.append({'id':doc['id'], 'error':str(error)})
    return {'documents':len(docs), 'unique_files':len(checked), 'errors':errors}


def backup_archive(destination):
    """Copia SQLite coherente más los blobs referidos por esa misma instantánea."""
    dest = Path(destination).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        raise ValueError('El respaldo de destino ya existe.')
    with tempfile.TemporaryDirectory() as tmp:
        snapshot = Path(tmp)/'qtech.sqlite3'
        with sqlite3.connect(snapshot) as copy:
            get_db().backup(copy)
            docs = copy.execute('SELECT DISTINCT sha256,byte_size FROM documents').fetchall()
        # Exclusive creation: never overwrite an earlier backup.
        with dest.open('xb') as output:
            os.chmod(dest, 0o600)
            try:
                with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
                    archive.write(snapshot, 'qtech.sqlite3')
                    for digest, size in docs:
                        p = blob_path(digest)
                        if file_hash(p) != digest or p.stat().st_size != size:
                            raise ValueError('Original dañado; respaldo cancelado.')
                        archive.write(p, 'documents/'+digest[:2]+'/'+digest)
            except Exception:
                dest.unlink(missing_ok=True)
                raise
    return {'files':len(docs), 'backup':str(dest)}
