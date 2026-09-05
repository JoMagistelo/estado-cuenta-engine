# Control de cambios técnico

## 1. Objetivo

Definir un checklist portable para cualquier cambio al Estado Cuenta Engine, independientemente de la plataforma institucional utilizada para alojar el código o ejecutar CI/CD.

## 2. Identificación

Todo cambio debe registrar como mínimo:

- objetivo y justificación;
- alcance funcional/técnico;
- componentes afectados;
- responsable del cambio;
- evidencia de pruebas;
- riesgos conocidos;
- mecanismo de reversión cuando aplique.

## 3. Impacto funcional

Antes de integrar un cambio debe determinarse explícitamente si modifica:

- detección de banco;
- clasificación Digital/OCR;
- readers;
- parsers;
- regex o geometrías;
- matching SPEI;
- modelos;
- validaciones;
- mapeo/exportación;
- interfaz o flujo de procesamiento.

Si la respuesta es sí, deben existir pruebas de regresión específicas y, para cambios bancarios relevantes, validación con corpus autorizado.

## 4. Seguridad y datos personales

Confirmar que el cambio:

- no incorpora estados de cuenta reales ni datos personales al repositorio;
- no introduce credenciales, secretos, certificados privados o configuraciones productivas;
- no registra información financiera innecesaria en logs;
- no agrega servicios externos sin análisis y autorización;
- no amplía permisos o superficie de red sin justificación;
- documenta nuevas dependencias y terceros.

## 5. Calidad mínima

La línea de CI/CD equivalente debe verificar:

- compilación del código;
- análisis estático crítico;
- pruebas unitarias/sintéticas;
- build del paquete;
- build del artefacto aplicable;
- auditoría de dependencias;
- integridad del artefacto.

Para el contenedor OCI opcional debe verificarse además:

- construcción exitosa;
- arranque;
- health check;
- usuario no privilegiado;
- ausencia de secretos/datos en el contexto de build.

## 6. Revisión técnica

La revisión debe confirmar:

- que el diff corresponde únicamente al objetivo declarado;
- que no existen modificaciones accidentales;
- que las dependencias añadidas son necesarias;
- que los errores se manejan sin ocultar fallas relevantes;
- que el cambio sigue siendo portable y configurable;
- que la documentación se actualizó cuando cambió arquitectura, despliegue o seguridad.

## 7. Criterios especiales para parsers

Los cambios a extracción bancaria son de alto impacto funcional. Deben:

- limitarse al banco/layout objetivo siempre que sea posible;
- conservar casos previamente correctos;
- incluir fixtures sintéticos representativos;
- probar bordes OCR/layout relevantes;
- comparar resultados esperados antes/después;
- evitar refactors cosméticos masivos mezclados con correcciones funcionales.

## 8. Criterio de integración

No integrar cuando:

- CI está en rojo;
- el impacto funcional no está entendido;
- se introducen datos sensibles o secretos;
- existe vulnerabilidad bloqueante sin tratamiento;
- falta evidencia de regresión para cambios de extracción;
- el artefacto no puede construirse;
- no existe forma razonable de revertir un cambio de alto riesgo.

## 9. Evidencia

La evidencia de desarrollo debe conservarse en el sistema institucional definido para control de cambios y liberaciones. El repositorio de código puede contener referencias técnicas, pero no debe convertirse en un expediente paralelo con información sensible.
