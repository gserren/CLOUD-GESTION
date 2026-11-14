# Estado de continuidad

Versión 0.2.0. Preparada el 14 de noviembre de 2026.

Al retomar se verificó mediante GitHub que `gserren/CLOUD-GESTION` existía,
era público, tenía permiso de escritura y no tenía ramas ni solicitudes de
cambio. No se encontró una aplicación anterior que hubiera que conservar.

Se implementó el circuito clientes → instalaciones → órdenes → observaciones →
reportes → portal de cliente, con persistencia y controles de acceso.
El alcance implementado y los comandos están en README.md.

La conexión directa con Cloud Gestión no está disponible desde el entorno
usado. Se agregó un archivo privado de originales y se validó una importación
parcial de respaldos en una base separada, sin incorporar esos datos a Git.
Esto no acredita una migración completa de CG ni asociaciones conciliadas.
No se enviaron correos, no se cambiaron permisos de Drive y no se operó sobre
la PC del usuario.
El código incluye una carga opcional de datos ficticios, sin cuentas o claves
predeterminadas de clientes.

Esta entrega deja el repositorio listo para continuar en Codex. No certifica
que el entorno de Codex anterior estuviera bien configurado y no publica un
servidor para uso de clientes. La persistencia operativa requiere alojamiento.

La versión permite generar reportes propios imprimibles. No es aún un reemplazo
completo de Cloud Gestión: equipos, fotos operativas, conversión estructurada,
automatizaciones, facturación y stock siguen pendientes.

El archivo acepta originales de cualquier categoría mediante manifiestos
locales. Incluye SHA-256, versiones, permisos, asociaciones validadas, auditoría
y respaldo de base más originales. Esquema 2 con migración conservadora.
Se verificaron 29 pruebas automatizadas y sintaxis JavaScript. La prueba visual
en navegador sigue pendiente por la restricción del entorno, como se detalla
en docs/VALIDACION.md. Ver docs/MIGRACION_CG.md antes de continuar.
