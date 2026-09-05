# Control de cambios técnico

## Estado Cuenta Engine — SABG / DGEC

## 1. Objetivo

Definir criterios mínimos para modificar el sistema sin degradar resultados, seguridad ni mantenibilidad. El procedimiento se expresa de forma independiente de la plataforma utilizada para control de versiones o CI/CD.

## 2. Identificación del cambio

Cada cambio debe registrar:

- objetivo y justificación;
- alcance funcional y técnico;
- componentes afectados;
- responsable técnico;
- evidencia de pruebas;
- riesgos conocidos;
- mecanismo de reversión cuando aplique.

## 3. Impacto funcional

Debe determinarse expresamente si el cambio afecta:

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

Los cambios de extracción bancaria requieren pruebas de regresión específicas y, cuando corresponda, validación con corpus autorizado.

## 4. Seguridad y datos personales

Verificar que el cambio:

- no incorpora estados de cuenta reales ni datos personales al repositorio;
- no introduce credenciales, secretos o certificados privados;
- no registra información financiera innecesaria;
- no incorpora servicios externos sin análisis y autorización;
- no amplía permisos o exposición de red sin justificación;
- documenta nuevas dependencias y componentes de terceros.

## 5. Calidad mínima

La automatización de calidad debe verificar, como mínimo:

- compilación del código;
- análisis estático de errores críticos;
- pruebas unitarias y sintéticas;
- build del paquete;
- build del artefacto distribuible;
- auditoría de dependencias;
- integridad del artefacto.

## 6. Revisión técnica

La revisión debe confirmar:

- que el diff corresponde al objetivo declarado;
- que no existen modificaciones accidentales;
- que las dependencias añadidas son necesarias;
- que los errores no quedan ocultos de forma insegura;
- que la configuración operativa permanece separada del código;
- que la documentación se actualizó cuando cambió arquitectura, despliegue o seguridad.

## 7. Criterios especiales para parsers

Los parsers constituyen lógica crítica de negocio. Sus cambios deben:

- limitarse al banco/layout objetivo siempre que sea posible;
- conservar casos previamente correctos;
- incluir fixtures sintéticos representativos;
- cubrir bordes OCR/layout relevantes;
- comparar resultados esperados antes y después;
- evitar refactors cosméticos masivos mezclados con correcciones funcionales.

## 8. Criterio de integración

No integrar cuando:

- la automatización de calidad está en rojo;
- el impacto funcional no está entendido;
- se introducen datos sensibles o secretos;
- existe una vulnerabilidad bloqueante sin tratamiento;
- falta evidencia de regresión para cambios de extracción;
- el artefacto no puede construirse;
- no existe una estrategia razonable de reversión para un cambio de alto riesgo.

## 9. Evidencia

La evidencia de desarrollo y liberación debe conservarse en el sistema institucional definido para gestión de cambios. El repositorio de código debe contener únicamente la información técnica necesaria para mantener y operar el producto, sin duplicar expedientes ni información sensible.
