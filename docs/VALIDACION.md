# Validación de la versión 0.2.0

Entorno de prueba: Python 3.12.14, Flask 3.1.3, SQLite, Node 24.

Comandos ejecutados:

```bash
.venv/bin/python -m unittest discover -s tests -v
node --check frontend/app.js
node --check frontend/report.js
```

Las pruebas cubren autenticación, CSRF y origen, aislamiento por cliente,
asignación de técnicos, transiciones de órdenes, requisitos de cierre,
generación/publicación de reportes, filtrado servidor de valor cero/notas,
instantáneas inmutables, vista de cliente, revocación de sesiones,
desactivación de usuarios, cambio de contraseña, entradas inválidas,
escape HTML, persistencia, límite de intentos y resolución de observaciones.
Incluyen un circuito completo creando registros nuevos y verificación de assets.

29 pruebas automatizadas aprobadas. El archivo de originales agrega pruebas de
previsualización sin escritura, rechazo atómico de lotes, huellas/tamaños,
conservación de versiones, deduplicación sin perder referencias, reimportación,
rutas y enlaces simbólicos, acceso exclusivo de administración, vista cliente,
CSRF, asociaciones incompatibles, descarga como adjunto, detección de corrupción,
migración de esquema 1 a 2 sin perder datos y restauración de base más originales.

Limitación visual: el arranque de Chromium headless fue bloqueado por el
aislamiento del ejecutor (`socket() failed: Operation not permitted`). El
navegador remoto disponible no alcanzó este servidor local. Por eso el script
de interfaz queda preparado, pero la revisión de escritorio/móvil y el circuito
con clics no se presentan como aprobados. Verificarlos antes de publicar la app.

La prueba usa datos ficticios. No valida una integración con Cloud Gestión ni
la exactitud de datos operativos reales. No se verificó un despliegue público.
