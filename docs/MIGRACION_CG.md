# Migración de documentos de Cloud Gestión

Para la copia de la base de datos y las actualizaciones conservadoras, seguir
[ACTUALIZACION_CG.md](ACTUALIZACION_CG.md). Conservar los originales en origen
y todas las versiones ya copiadas mientras se completa la transición.

## Alcance obligatorio

Conservar **todos los documentos creados en CG real** y sus adjuntos: partes,
presupuestos, pedidos, albaranes, facturas, recibos, contratos y otras categorías
presentes en la cuenta. El inventario autoritativo debe salir de CG, incluyendo
series, fechas, estados, revisiones y relaciones con clientes, instalaciones,
equipos y documentos. Los respaldos de Drive son una fuente parcial, no una
prueba de que CG esté completamente migrado.

El archivo implementado acepta cualquier tipo de documento. Conserva bytes,
nombre original, identificadores de origen, versión, tipo, fecha del origen,
URL estable, metadatos y SHA-256. La información guardada en PDFs se conserva
dentro del original; no se convierte automáticamente en campos operativos de
facturación, equipos, firmas, fotos ni checklists.

Los originales son privados, exclusivos de administración. Un PDF original
puede contener notas internas y mediciones que no deben publicarse al cliente.
La publicación de reportes propios sigue su circuito independiente. Descargar
un original requiere sesión de administrador y verifica su integridad.

## Importar una exportación

Trabajar fuera de Git con un directorio privado. Preparar `manifest.json` y los
archivos referenciados en rutas relativas bajo esa misma carpeta. Ejemplo de
estructura **ficticia** (reemplazar tamaño y huella por los del archivo real):

```json
{
  "version": 1,
  "source_complete": false,
  "documents": [{
    "path": "originals/documento.pdf",
    "source_system": "cloud-gestion-export",
    "source_id": "ID-estable-en-el-origen",
    "source_revision": "revision-del-origen",
    "source_reference": "SERIE/NUMERO",
    "original_name": "documento.pdf",
    "kind": "parte_trabajo",
    "mime_type": "application/pdf",
    "byte_size": 123,
    "sha256": "REEMPLAZAR_POR_SHA256_DEL_ARCHIVO",
    "source_created_at": "",
    "source_modified_at": "",
    "source_metadata": {},
    "client_id": null,
    "site_id": null,
    "order_id": null
  }]
}
```

`source_id` debe ser el identificador estable del sistema declarado. En un
respaldo procedente de Drive corresponde al ID de Drive, no a un ID inventado
de CG. Las fechas de Drive tampoco equivalen necesariamente a la fecha del
documento en CG. Conservar los datos exportados de CG en `source_metadata`.
No incluir claves, enlaces de descarga firmados ni contraseñas.

```bash
python manage.py import-documents /ruta/privada/export/manifest.json
python manage.py import-documents /ruta/privada/export/manifest.json --commit
python manage.py verify-documents
```

La primera orden previsualiza sin copiar archivos. La segunda valida todo el
lote, copia los originales a almacenamiento privado y registra la importación
en una transacción. Cualquier error de validación rechaza el lote completo.
La aplicación no consulta URLs del manifiesto ni ejecuta los archivos.
Se rechazan rutas fuera de la exportación, enlaces simbólicos, tamaños o
huellas incorrectas. Máximos: 500 MiB por archivo, 10000 registros y 20 MiB de
manifiesto por lote; dividir exportaciones mayores conservando sus IDs.

Reimportar la misma identidad, versión y huella no duplica el registro.
Contenido nuevo conserva una nueva versión, aun cuando el nombre coincida.
Dos registros de origen distintos con los mismos bytes comparten un archivo,
pero conservan sus dos referencias. Cambiar una asociación no modifica bytes
ni metadatos de origen; usar la pantalla **Documentos originales → Asociar**.
No asociar por coincidencia aproximada de nombres: conciliar los identificadores
del maestro CG. Las asociaciones ausentes permanecen pendientes.

Si se interrumpe el proceso después de copiar un blob y antes de confirmar la
transacción, puede quedar un archivo sin referencia. No se publica ni se borra
automáticamente: reintentar el mismo lote es seguro. Verificar el archivo y la
base antes de cualquier mantenimiento manual.

## Ubicación y respaldo

Por defecto los originales van a `documents/` junto a la base configurada.
`QTECH_DOCUMENT_ROOT` permite otro directorio privado persistente. Nunca usar
`frontend/`, un directorio público del servidor, una carpeta compartida ni Git.
La migración SQL de esquema 1 a 2 conserva los registros existentes.

```bash
python manage.py backup-archive /ruta/privada/respaldo-completo.zip
```

Incluye una instantánea coherente de SQLite y cada original referenciado,
verificado. El ZIP contiene datos privados, no está cifrado por la aplicación
y debe guardarse en almacenamiento con acceso restringido y respaldo externo.
El comando anterior `backup` conserva únicamente SQLite y **no alcanza** para
respaldar originales.

Para restaurar un ZIP producido por esta aplicación: detener el servicio,
extraerlo en una carpeta privada vacía, configurar `QTECH_DATABASE` hacia su
`qtech.sqlite3` y `QTECH_DOCUMENT_ROOT` hacia su `documents/`. Ejecutar
`verify-documents` y comprobar los accesos antes de reabrir el servicio. No
sobrescribir una instalación activa ni extraer ZIP de origen desconocido.

## Criterio de cierre

La migración solo termina cuando el inventario completo de CG coincide por
tipo, serie, ID y versión con lo importado; los adjuntos están contabilizados;
los originales verifican sus huellas; las asociaciones están conciliadas; se
prueba una restauración; y se revisan los permisos de acceso. Una muestra de
PDF, una búsqueda sin resultados o una importación exitosa de un lote no
demuestran completitud. Registrar faltantes y errores en un informe privado.

Pendiente: acceso a la fuente CG, exportación completa, conversión de relaciones
con equipos y documentos vinculados a campos operativos, integración automática,
validación visual en navegador y alojamiento de producción.

