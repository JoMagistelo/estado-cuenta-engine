# Visión del proyecto

## Estado Cuenta Engine

## 1. Contexto institucional

Estado Cuenta Engine es un motor en desarrollo para apoyar el procesamiento estructurado de estados de cuenta bancarios dentro de procesos institucionales autorizados de la **Secretaría Anticorrupción y Buen Gobierno (SABG)**, con aplicación prevista en la **Dirección General de Evaluación de Confianza (DGEC)**.

El Reglamento Interior de la SABG atribuye a la DGEC la instrumentación de procesos de evaluación de confianza y su participación con otras unidades administrativas en el diseño de los sistemas tecnológicos requeridos en su materia.

## 2. Objetivo

Convertir documentos financieros en PDF, digitales o escaneados, a una representación estructurada y validable que permita reducir captura manual, mejorar consistencia y facilitar su integración con herramientas institucionales posteriores.

## 3. Alcance funcional actual

El repositorio ya contempla:

- PDF con texto nativo;
- PDF escaneado mediante OCR local con Tesseract;
- detección del método de procesamiento Digital/OCR;
- detección de institución/emisor;
- parsers especializados por institución;
- extracción de datos de cuenta, resumen financiero, movimientos y otros productos cuando el formato lo permite;
- normalización y mapeo a modelos comunes;
- validación de movimientos;
- procesamiento por lotes;
- exportación a Excel;
- interfaces Streamlit y Flet.

## 4. Instituciones/emisores actualmente contemplados

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

La lista describe el código existente y **no constituye una declaración de cobertura total de layouts ni certificación de exactitud para todos los documentos de cada institución**.

## 5. Límites del sistema

El motor:

- no sustituye la revisión humana o institucional;
- no determina por sí mismo la confiabilidad de una persona servidora pública;
- no emite resoluciones administrativas;
- no debe utilizarse como única fuente para decisiones que produzcan efectos jurídicos o afecten significativamente derechos o intereses;
- puede presentar errores de OCR, variaciones de layout, datos parciales o inconsistencias que deben ser detectadas mediante validaciones y revisión.

## 6. Protección de datos desde el diseño

El sistema debe evolucionar bajo un enfoque de privacidad y seguridad desde el diseño y por defecto. En particular:

- recolectar y conservar sólo la información necesaria para la finalidad autorizada;
- limitar accesos según funciones;
- evitar persistencia innecesaria de documentos y temporales;
- mantener trazabilidad de operaciones sin registrar contenido financiero sensible en bitácoras;
- contemplar ciclo de vida, supresión y conservación documental;
- separar ambientes de desarrollo, pruebas y producción;
- evitar el uso de datos reales en repositorios y herramientas de colaboración.

## 7. Evolución prevista

### Corto plazo

- fortalecer parsers y pruebas de regresión;
- formalizar el modelo de errores y trazabilidad;
- completar documentación de arquitectura y seguridad;
- revisar dependencias, binarios y licenciamiento;
- definir clasificación de información y flujos de datos con TIC y protección de datos.

### Camino a producción

- evaluación formal de riesgos;
- Documento de Seguridad de datos personales;
- determinación de procedencia de Evaluación de Impacto en Protección de Datos Personales;
- alineación con el Plan Institucional de Ciberseguridad de la SABG;
- definición de autenticación y autorización;
- despliegue controlado en Windows Server;
- HTTPS con certificado institucional conforme al procedimiento que establezca TIC/Buen Gobierno;
- gestión de secretos;
- monitoreo, bitácoras, respaldos, continuidad y respuesta a incidentes;
- pruebas de seguridad y aceptación antes de liberar.

## 8. Integración futura

Existe una aplicación desarrollada en Angular que **podría** consumir el motor en una etapa posterior. La integración todavía no está definida.

Streamlit existe actualmente como interfaz de aplicación y no debe asumirse automáticamente como una API. Si la integración con Angular requiere una interfaz programática estable, se deberá evaluar una capa de servicios/API dedicada, versionada y protegida, separando la lógica del motor de la presentación.

## 9. Principio rector

La evolución debe preservar una arquitectura modular: agregar o fortalecer un parser no debe obligar a introducir dependencias innecesarias en la interfaz, exportadores o modelos de dominio.

**Fecha de corte documental:** 4 de septiembre de 2026.
