# QTECH Gestión

Primera versión funcional de una aplicación propia de gestión de mantenimiento.
Permite administrar clientes e instalaciones, asignar órdenes, registrar hallazgos
y publicar reportes en un portal con permisos por cliente.

Es una implementación nueva, inspirada en los procesos de mantenimiento de QTECH.
No contiene código de Cloud Gestión ni se conecta todavía con ese servicio.

## Inicio rápido

Requisitos: Python 3.11 o superior. Funciona en macOS, Linux y Windows.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py init-admin
python manage.py seed-demo  # opcional; requiere una base sin clientes
python manage.py serve
```

En Windows: `py -m venv .venv` y `.venv\Scripts\activate`.
Abrir http://127.0.0.1:8000. Usuario inicial: `admin`. La contraseña se elige
en `init-admin`, que la pide sin mostrarla. No hay una clave predeterminada.

`seed-demo` carga tres clientes claramente ficticios y tres órdenes. No crea
cuentas de clientes ni descarga información real. Se puede omitir para trabajar
con una base vacía. Una base que recibió ejemplos muestra siempre el aviso DEMO.

## Lo que está implementado

- Inicio y cierre de sesión, cambio de contraseña, limitación de intentos.
- Usuarios administrador, técnico y cliente; activación/desactivación de accesos.
- Alta y edición de clientes, con marca del grupo y contacto.
- Alta de instalaciones, dirección y sistema asociado.
- Órdenes con programación, prioridad, responsable, notas internas y resultado.
- Flujo programada → en curso → completada; cancelación y reapertura por administración.
- Observaciones con riesgo ingresado por el operador, valor opcional y resolución.
- Reportes versionados como instantáneas de una orden completada.
- Publicación explícita para el cliente; los borradores son internos.
- Portal de cliente y vista de cliente para administración.
- Ocultamiento de valores cero y notas internas **en el servidor**, para clientes.
- Vista imprimible de reportes; guardar PDF mediante la impresión del navegador.
- Búsqueda, filtros, indicadores y registro de actividad.
- Persistencia SQLite, comando de respaldo y pruebas automatizadas.

Publicar al cliente significa habilitar la revisión en esta aplicación. No envía
correos, no otorga permisos en Drive y no publica archivos en otros sistemas.

## Permisos

| Acción | Administración | Técnico | Cliente |
|---|---|---|---|
| Clientes e instalaciones | Todos; alta/edición de cliente | Solo relacionados con sus órdenes; lectura | Solo propios; lectura |
| Crear/asignar/reabrir órdenes | Sí | No | No |
| Registrar intervención y hallazgos | Todas las órdenes abiertas | Órdenes asignadas abiertas | No |
| Generar borrador de reporte | Sí | De sus órdenes completadas | No |
| Publicar reporte | Sí | No | No |
| Ver reportes | Todos | De órdenes asignadas | Solo propios y publicados |
| Gestionar usuarios / vista de cliente | Sí | No | No |

El cierre de una intervención puede conservar hallazgos pendientes. No equivale
a certificar que la instalación está libre de riesgos. Las alertas del cliente
se calculan con la última revisión publicada por orden. El historial conserva
las revisiones anteriores. No se aplica una matriz normativa automática.

## Continuar desde Codex

Abrir este repositorio. Leer `AGENTS.md`, `docs/ESTADO.md` y
`docs/SIGUIENTE_TAREA.md`. La preparación del entorno es:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

El entorno de Codex sirve para desarrollar y probar. No reemplaza el alojamiento
persistente de la aplicación ni es el servidor de producción.

También se puede ejecutar `bash scripts/setup.sh` como comando de preparación
del entorno en Linux/macOS. Instala y verifica; no crea usuarios ni ejemplos.

La prueba opcional de interfaz está en `tests/browser_smoke.py`. Requiere el
paquete Playwright y un Chromium disponible (`CHROMIUM_PATH` si corresponde).
Ejecutar `python tests/browser_smoke.py` en un entorno que permita iniciar el
navegador. Trabaja con una base temporal y nunca controla el navegador del usuario.

## Estructura

- `backend/app.py`: API, validaciones, autorización y reportes.
- `backend/auth.py`: contraseñas, sesiones revocables y CSRF.
- `backend/db.py` y `schema.sql`: persistencia y esquema inicial.
- `frontend/`: interfaz responsive sin compilador ni servicios externos.
- `backend/templates/report.html`: documento imprimible con escape automático.
- `tests/test_app.py`: pruebas de negocio y aislamiento entre usuarios.
- `manage.py`: arranque, administrador, demostración y copias de seguridad.

## Datos y operación

Por defecto, la base se crea en `instance/qtech.sqlite3`, excluida de Git.
`QTECH_DATABASE` permite indicar otra ruta. No subir bases, contraseñas,
reportes reales ni archivos de clientes al repositorio público.

Crear una copia consistente mientras el servidor está abierto:

```bash
python manage.py backup /ruta/privada/respaldo-qtech.sqlite3
```

Para restaurar: detener el servidor, verificar la copia y configurar
`QTECH_DATABASE` apuntando al respaldo en un directorio privado. No sobrescribir
una base activa. Probar la restauración antes de depender de los respaldos.

Restablecer una contraseña desde el servidor:

```bash
python manage.py reset-password nombre-de-usuario
```

El cambio revoca todas las sesiones de ese usuario. Las claves se guardan como
hash scrypt; las cookies contienen tokens aleatorios, cuyo hash se conserva
en la base. Las sesiones vencen a las ocho horas. Las operaciones de escritura
requieren JSON, encabezado propio y token CSRF.

## Publicación en un servidor

Este repositorio aún no tiene un alojamiento configurado. El comando `serve`
usa Waitress y escucha solo en 127.0.0.1. Para acceso externo: configurar HTTPS
con proxy inverso, almacenamiento persistente, copias y monitorización; establecer
`QTECH_HTTPS=1` y `QTECH_HOSTS=dominio-real` (sin protocolo ni puerto).
El proxy debe preservar Host y acceder con un origen coherente. La aplicación
no confía en X-Forwarded-* por defecto: si se termina TLS en un proxy, adaptar
esa frontera explícitamente antes de producción y probar la validación de Origin.

Antes de uso operativo, revisar alcance y permisos con usuarios reales y probar
el despliegue. SQLite cubre este piloto de una sola organización; no hay todavía
separación multitenant, alta concurrencia ni acuerdos de disponibilidad.

## Pendiente

Integración real con Cloud Gestión, importación de PDFs de servicio, fotos y
adjuntos, catálogo de equipos/checklists, recurrencias, agenda por cuadrilla,
notificaciones, facturación, stock y funcionamiento móvil sin conexión.
Ver `docs/SIGUIENTE_TAREA.md` para el próximo incremento propuesto.
