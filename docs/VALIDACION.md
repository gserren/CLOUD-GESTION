# Validación de la versión 0.1.0

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

Limitación visual: el arranque de Chromium headless fue bloqueado por el
aislamiento del ejecutor (`socket() failed: Operation not permitted`). El
navegador remoto disponible no alcanzó este servidor local. Por eso el script
de interfaz queda preparado, pero la revisión de escritorio/móvil y el circuito
con clics no se presentan como aprobados. Verificarlos antes de publicar la app.

La prueba usa datos ficticios. No valida una integración con Cloud Gestión ni
la exactitud de datos operativos reales. No se verificó un despliegue público.
