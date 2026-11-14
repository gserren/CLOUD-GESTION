# Prioridad: completar la migración de CG y el circuito de servicio

Continuar QTECH Gestión desde el código existente. Antes de editar, ejecutar las
pruebas y revisar README.md y AGENTS.md.

Antes de nuevos módulos, obtener y conciliar el inventario completo de CG real
con los originales importados. La búsqueda de respaldos solo acredita un lote
parcial. Seguir docs/MIGRACION_CG.md. Mantener archivos e inventarios privados.

1. Agregar equipos por instalación: código, tipo, marca/modelo, ubicación y estado.
2. Definir checklists por tipo de servicio y guardar una copia de su versión en
   cada intervención. No presentar criterios internos como normativa oficial.
3. Incorporar evidencias fotográficas con almacenamiento privado, límites de
   formato/tamaño y descarga autorizada por rol. No almacenar imágenes en Git.
4. Usar el archivo privado de originales ya implementado como objeto distinto
   del reporte generado. Conciliar relaciones con los maestros del origen.
5. Extender la importación local con un adaptador basado en una exportación
   real de CG; no inventar endpoints ni marcar completo un respaldo parcial.
6. Mostrar reportes por año y mes en el portal de cliente.

Para conectar Cloud Gestión, primero verificar documentación o una exportación
real autorizada y confirmar el mapeo. No reutilizar contraseñas de otros sistemas.
Los datos existentes en Drive/Space no están disponibles automáticamente en
este repositorio: recuperarlos mediante una conexión autorizada cuando se
trabaje en la importación.

Criterios de aceptación: migración sin pérdida, autorizaciones en servidor,
cliente sin acceso a archivos de otro, valor cero oculto en su vista, fuentes
trazables y prueba de una intervención completa con reporte y evidencia.
