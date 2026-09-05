# Visión y alcance

## Estado Cuenta Engine — SABG / DGEC

## 1. Contexto institucional

Estado Cuenta Engine es un motor de procesamiento documental orientado a apoyar procesos institucionales autorizados de la Secretaría Anticorrupción y Buen Gobierno (SABG), con aplicación funcional en la Dirección General de Evaluación de Confianza (DGEC).

Su propósito es reducir captura manual, estandarizar información financiera y facilitar validaciones y flujos posteriores dentro de la infraestructura institucional.

## 2. Objetivo

Convertir estados de cuenta bancarios en PDF, digitales o escaneados, a una representación estructurada, validable y exportable.

## 3. Alcance funcional

La versión contempla:

- PDF con texto nativo;
- PDF escaneado mediante OCR local con Tesseract;
- clasificación Digital/OCR;
- detección de institución/emisor;
- parsers especializados;
- extracción de datos de cuenta;
- extracción de resumen financiero;
- extracción de movimientos;
- enriquecimientos específicos cuando el layout lo permite;
- normalización a modelos comunes;
- validaciones de consistencia;
- procesamiento por lotes;
- exportación a Excel;
- interfaces Flet y Streamlit.

## 4. Instituciones/emisores contemplados

La estructura actual incluye parsers para:

- BBVA;
- Banamex;
- Banorte;
- Banorte OCR;
- HSBC;
- Scotiabank;
- Mifel;
- Mercado Pago;
- CETES.

La cobertura depende del layout y de la calidad del documento. La aceptación funcional de una versión se determina mediante los casos de prueba y corpus autorizados correspondientes.

## 5. Límites funcionales

El motor:

- produce datos derivados de documentos fuente;
- no emite resoluciones administrativas;
- no sustituye la validación institucional cuando ésta sea requerida;
- puede recibir documentos con variaciones de layout, OCR deficiente o información parcial;
- debe conservar señales de validación y error suficientes para detectar resultados que requieren revisión.

## 6. Principios de diseño

- arquitectura modular;
- separación entre interfaz y lógica bancaria;
- OCR local;
- regresión controlada de parsers;
- dependencias explícitas;
- tratamiento mínimo de datos;
- configuración de infraestructura fuera del motor;
- trazabilidad técnica sin duplicar información financiera en logs;
- capacidad de integración con otros sistemas mediante contratos explícitos.

## 7. Integración institucional

La interfaz Streamlit puede operar como aplicación web interna detrás de IIS.

Si SIEC requiere integración programática, se recomienda una capa API dedicada sobre el motor. Esta separación permite incorporar autenticación, autorización, límites, trazabilidad y versionado sin trasladar esas responsabilidades a los parsers.

## 8. Seguridad y privacidad

La operación debe mantener:

- mínimo privilegio;
- autenticación y autorización institucional;
- HTTPS/TLS en la publicación web;
- secretos fuera del código;
- protección de temporales y salidas;
- minimización de logs;
- gestión de vulnerabilidades;
- respaldo y recuperación;
- cumplimiento de las reglas institucionales de conservación y protección de datos personales.

## 9. Criterio de evolución

La incorporación o fortalecimiento de un parser no debe obligar a modificar de forma innecesaria interfaces, exportadores, readers o modelos transversales.

Los cambios funcionales deben preservar layouts previamente correctos y acompañarse de pruebas de regresión específicas.

**Fecha de corte documental:** 5 de septiembre de 2026.
