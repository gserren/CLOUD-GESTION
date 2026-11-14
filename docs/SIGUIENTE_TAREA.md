# Próximo incremento propuesto: equipos y partes de servicio

Continuar QTECH Gestión desde el código existente. Antes de editar, ejecutar las
pruebas y revisar README.md y AGENTS.md.

1. Agregar equipos por instalación: código, tipo, marca/modelo, ubicación y estado.
2. Definir checklists por tipo de servicio y guardar una copia de su versión en
   cada intervención. No presentar criterios internos como normativa oficial.
3. Incorporar evidencias fotográficas con almacenamiento privado, límites de
   formato/tamaño y descarga autorizada por rol. No almacenar imágenes en Git.
4. Adjuntar el PDF original de servicio como un objeto distinto del reporte
   generado. Preservar nombre, hash, fuente, cliente, instalación, fecha y parte.
5. Diseñar una importación con vista previa: detectar duplicados por parte +
   cliente + instalación y por hash; no asumir que todo PDF es un reporte.
6. Mostrar reportes por año y mes en el portal de cliente.

Para conectar Cloud Gestión, primero verificar documentación o una exportación
real autorizada y confirmar el mapeo. No reutilizar contraseñas de otros sistemas.
Los datos existentes en Drive/Space no están disponibles automáticamente en
este repositorio: recuperarlos mediante una conexión autorizada cuando se
trabaje en la importación.

Criterios de aceptación: migración sin pérdida, autorizaciones en servidor,
cliente sin acceso a archivos de otro, valor cero oculto en su vista, fuentes
trazables y prueba de una intervención completa con reporte y evidencia.
