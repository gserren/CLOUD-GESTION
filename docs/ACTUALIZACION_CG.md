# Copia incremental de la base y los reportes

La instrucción vigente es copiar la **base de datos de CG y sus reportes**,
conservar todos los originales y mantener la copia actualizada hasta finalizar
la transición. No borrar ni modificar registros, documentos ni adjuntos en CG.
Las bajas detectadas en origen se registran como eventos; no eliminan la copia.
Una versión nueva se agrega al historial sin sustituir los bytes anteriores.

La SQLite de QTECH y los metadatos extraídos de PDFs son una recuperación parcial;
no equivalen a una exportación nativa de la base de CG. Para cerrar, obtener el
esquema y la exportación oficial, preservar IDs y relaciones de cada entidad y
conciliar conteos e inventarios con esa fuente, además de los documentos. No
inventar columnas, endpoints, asociaciones, estados ni información faltante.

Cada actualización debe trabajar sobre una restauración de la última copia
verificada. Descargar únicamente fuentes nuevas o modificadas, con una ventana
de solapamiento para no perder adjuntos tardíos. No avanzar una marca de éxito
si alguna página, descarga, importación, verificación o guardado falló.

Antes de guardar una nueva versión del respaldo, ejecutar:

```bash
python3 scripts/check_migration.py /privado/candidato.zip --previous /privado/respaldo-anterior.zip
```

El verificador no requiere Flask. Comprueba integridad y relaciones de SQLite,
SHA-256 y tamaños de originales, conservación de IDs previamente copiados,
metadatos inmutables de originales e instantáneas históricas de reportes.
Rechaza un candidato que pierda registros o cambie originales anteriores.
No importa, no borra y no confirma completitud del origen. Conservar ambos
respaldos hasta comprobar el guardado y la restauración del candidato.

El estado privado de ejecución debe guardar fecha de intento y último éxito
por fuente, cantidades, faltantes, conflictos, errores y versión verificada
del respaldo. No publicar ese inventario ni datos privados en Git. El seguimiento
de migración es independiente del control de envíos: no envía correos ni
considera un reporte enviado por estar copiado.

Si el origen resulta inaccesible, mantener la copia previa intacta, registrar
el bloqueo y continuar solo con fuentes autorizadas accesibles. No declarar
que la base de CG está sincronizada por haber programado una tarea.
