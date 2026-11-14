# QTECH Gestión — instrucciones para desarrollo

## Contexto
Aplicación propia de mantenimiento para QTECH. Repo: gserren/CLOUD-GESTION.
Continuar la implementación existente y leer README.md y docs/ESTADO.md.
No confundir este sistema con el portal PCI en Sites ni con Cloud Gestión real.

## Trabajar con autonomía
- Resolver decisiones rutinarias y ejecutar cambios reversibles, verificaciones y reparaciones.
- Trabajar en el entorno de desarrollo sin tomar control del equipo del usuario.
- Conservar los cambios existentes y registrar límites reales, sin simular integraciones.
- No interpretar una demo como información operativa verificada.

## Convenciones
- Python 3.11+, Flask, SQLite y JavaScript sin compilación para este MVP.
- Interfaz y documentación en español. Fechas operativas: America/Montevideo.
- Autorizar en servidor cada lectura, escritura y descarga; ocultar botones no es un control.
- Técnicos limitados a órdenes asignadas. Clientes limitados a sus reportes publicados.
- En vista cliente excluir observaciones con valor numérico cero y notas internas.
- Preservar snapshots de reportes. Las correcciones requieren nueva revisión.
- No agregar dependencias ni migrar de stack sin una necesidad concreta.
- No incluir claves, bases, sesiones, archivos reales ni datos personales en Git.
- Mantener el esquema versionado; futuras migraciones deben conservar datos.

## Validación
```bash
.venv/bin/python -m unittest discover -s tests -v
node --check frontend/app.js
```
Probar especialmente aislamiento de clientes, asignación de técnicos, CSRF,
sesiones revocadas, filtros de valor cero y estabilidad de reportes históricos.
Actualizar documentación cuando se modifique el comportamiento.

## Integraciones
No inventar endpoints de Cloud Gestión ni inferir conexión por tener credenciales.
Preparar importaciones con previsualización y conciliación de identificadores.
Los envíos de correo y cambios de permisos externos requieren una instrucción
específica para esa acción, sus destinatarios y sus archivos.
