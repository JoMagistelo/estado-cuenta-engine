# Seguridad y protección de datos personales

## Estado Cuenta Engine — SABG / DGEC

**Fecha de corte:** 4 de septiembre de 2026

> Este documento es una guía técnica de cumplimiento para el proyecto. No sustituye el Documento de Seguridad institucional, avisos de privacidad, evaluaciones de impacto, dictámenes jurídicos ni políticas internas que correspondan.

## 1. Naturaleza de la información

Un estado de cuenta puede contener, entre otros:

- nombre de la persona titular;
- RFC y otros identificadores;
- domicilio;
- número de cliente;
- número de cuenta, tarjeta o CLABE;
- saldos;
- cargos, abonos y fechas;
- referencias y claves de rastreo;
- nombres o cuentas de contrapartes;
- conceptos de movimientos;
- información derivada de SPEI u otros medios de pago.

Estos elementos pueden constituir **datos personales** cuando se relacionan con una persona física identificada o identificable. La información financiera merece un nivel alto de protección por el impacto patrimonial y de privacidad que podría producir un acceso no autorizado.

Además, un concepto de movimiento podría revelar indirectamente información que la ley considera sensible —por ejemplo, aspectos de salud, creencias u otros elementos íntimos— dependiendo del contenido concreto. Por ello no debe asumirse que todos los estados de cuenta tienen el mismo nivel de riesgo.

## 2. Principios de tratamiento para el sistema

El diseño y operación deberán observar, conforme al marco jurídico aplicable y a las instrucciones institucionales, al menos:

- finalidad determinada y legítima;
- proporcionalidad y minimización;
- calidad y exactitud;
- seguridad;
- confidencialidad;
- responsabilidad;
- privacidad desde el diseño y por defecto;
- conservación únicamente por el tiempo autorizado;
- trazabilidad de accesos y operaciones.

## 3. Obligaciones de seguridad relevantes

La Ley General de Protección de Datos Personales en Posesión de Sujetos Obligados vigente exige medidas administrativas, físicas y técnicas para proteger datos personales y preservar confidencialidad, integridad y disponibilidad.

Para establecer esas medidas, el responsable debe contemplar el riesgo inherente, la sensibilidad, el desarrollo tecnológico, las consecuencias de una vulneración, las transferencias, el número de titulares, vulneraciones previas y el valor potencial de los datos para terceros no autorizados.

En el contexto de Estado Cuenta Engine esto se traduce en controles como:

- acceso por necesidad de conocer;
- mínimo privilegio;
- separación de funciones;
- autenticación robusta;
- cifrado en tránsito;
- protección de datos en reposo conforme a la arquitectura aprobada;
- gestión de secretos;
- hardening del servidor;
- parcheo y gestión de vulnerabilidades;
- control de dispositivos y carpetas temporales;
- respaldos protegidos;
- monitoreo de eventos de seguridad;
- procedimientos de respuesta y recuperación.

## 4. Documento de Seguridad

El responsable institucional debe integrar y mantener el **Documento de Seguridad** previsto por la LGPDPPSO. La ley establece como contenido mínimo:

1. inventario de datos personales y sistemas de tratamiento;
2. funciones y obligaciones de quienes tratan datos;
3. análisis de riesgos;
4. análisis de brecha;
5. plan de trabajo;
6. mecanismos de monitoreo y revisión;
7. programa general de capacitación.

Para este sistema se recomienda que el inventario identifique separadamente:

- PDF original;
- texto extraído;
- `spatial_words`;
- salida de OCR;
- objetos/modelos internos;
- resultados de validación;
- archivos Excel;
- temporales;
- bitácoras;
- respaldos;
- posibles bases de datos futuras.

## 5. Evaluación de Impacto en Protección de Datos Personales

La LGPDPPSO vigente prevé una **evaluación de impacto en la protección de datos personales** cuando se pretenda poner en operación o modificar sistemas, plataformas, aplicaciones u otras tecnologías que impliquen tratamiento intensivo o relevante de datos personales.

Por la naturaleza del proyecto, **antes de producción debe realizarse un análisis formal de procedencia** con la unidad competente en protección de datos personales. No se afirma en este documento que la evaluación sea automáticamente obligatoria: la determinación debe efectuarse con base en la ley, el tratamiento real, las finalidades, los flujos, transferencias y nivel de riesgo.

Cuando resulte procedente, la evaluación debe presentarse ante la autoridad competente en el plazo legal aplicable antes de la puesta en operación o modificación.

## 6. Datos de personas servidoras públicas

El hecho de que la persona titular sea servidora pública **no convierte automáticamente toda su información personal o financiera en información pública**. El tratamiento debe fundarse en las atribuciones institucionales, la finalidad autorizada y las reglas aplicables de protección de datos, transparencia y clasificación de información.

El motor no debe reutilizar información para finalidades distintas a las autorizadas ni producir datasets secundarios para pruebas, analítica, IA o desarrollo salvo autorización y fundamento correspondientes.

## 7. Datos de terceras personas

Los estados de cuenta pueden incluir información de beneficiarios, ordenantes, comercios u otras contrapartes. El sistema debe tratar estos datos bajo el mismo principio de minimización y evitar replicarlos fuera del flujo autorizado.

Las salidas para análisis deberían incluir únicamente los campos requeridos por la finalidad institucional. Si un dato no es necesario para el proceso, deberá evaluarse su exclusión o disociación.

## 8. Desarrollo, pruebas y repositorio

### Prohibido

No se deben subir a GitHub:

- estados de cuenta reales;
- imágenes/capturas identificables;
- OCR o JSON derivado de documentos reales;
- Excel con resultados reales;
- bases de datos o dumps;
- logs con PII;
- RFC, CURP, CLABE, cuentas o referencias reales en fixtures;
- secretos o certificados privados.

### Permitido

- fixtures sintéticos;
- datos anonimizados/disociados mediante procedimiento aprobado;
- ejemplos con valores completamente ficticios;
- estructuras de layout sin contenido personal.

## 9. Logs y observabilidad

Los logs productivos deben evitar el contenido financiero. Se recomienda registrar identificadores técnicos no sensibles, por ejemplo:

- ID interno de procesamiento;
- timestamp;
- versión del motor;
- método Digital/OCR;
- parser aplicado;
- estado de la operación;
- códigos de error;
- duración;
- usuario o cuenta técnica cuando proceda, mediante identificador institucional controlado.

No registrar por defecto:

- texto completo del PDF;
- conceptos de movimientos;
- números de cuenta completos;
- CLABE completa;
- RFC completo;
- nombre completo;
- saldo o movimientos completos;
- claves de rastreo completas.

## 10. Temporales

El pipeline puede generar datos intermedios en memoria y, dependiendo de las librerías o interfaces, archivos temporales.

Antes de producción se deberá:

- identificar todas las ubicaciones temporales;
- restringir permisos de carpeta;
- evitar nombres de archivo con datos personales;
- limpiar temporales después del procesamiento;
- limpiar temporales después de errores y reinicios;
- definir el comportamiento ante cierre inesperado;
- impedir que un usuario acceda a temporales de otro proceso.

## 11. Vulneraciones e incidentes

La ley exige bitácora de vulneraciones de seguridad y contempla notificación cuando una vulneración afecte significativamente derechos patrimoniales o morales.

El sistema debe integrarse al procedimiento institucional de incidentes. El equipo del proyecto no debe crear un canal paralelo de notificación fuera del esquema de la SABG.

Evidencia técnica útil para una investigación:

- versión desplegada;
- logs de acceso y errores;
- ventana temporal del incidente;
- activos afectados;
- hashes de artefactos;
- cambios recientes;
- lista de cuentas involucradas;
- acciones de contención.

## 12. Transferencias, terceros y nube

No se debe enviar información a servicios externos sin revisión institucional previa.

Esto incluye:

- OCR en nube;
- almacenamiento en nube;
- APIs de IA;
- servicios de analítica/telemetría;
- correo no institucional;
- repositorios públicos o personales;
- plataformas de colaboración externas.

Si en el futuro se incorpora un tercero o encargado, deberán revisarse el instrumento jurídico, medidas de seguridad, ubicación del tratamiento, transferencias, subencargados, retención y devolución/supresión de información.

## 13. Checklist mínimo de privacidad antes de producción

- [ ] finalidad y fundamento documentados;
- [ ] responsable funcional identificado;
- [ ] inventario de datos y sistemas de tratamiento;
- [ ] flujos de datos documentados;
- [ ] análisis de riesgos;
- [ ] análisis de brecha;
- [ ] Documento de Seguridad actualizado;
- [ ] aviso(s) de privacidad aplicables revisados;
- [ ] análisis de procedencia de EIPDP;
- [ ] reglas de retención y supresión;
- [ ] roles y accesos autorizados;
- [ ] procedimiento de incidentes/vulneraciones;
- [ ] logs minimizados;
- [ ] pruebas con datos sintéticos o autorizados;
- [ ] revisión de transferencias/terceros;
- [ ] evidencia de capacitación de personal involucrado.

## 14. Fuentes oficiales

- Ley General de Protección de Datos Personales en Posesión de Sujetos Obligados, texto vigente, Cámara de Diputados: https://www.diputados.gob.mx/LeyesBiblio/pdf/LGPDPPSO.pdf
- Decreto de expedición de la LGPDPPSO, DOF 20/03/2025: https://sidof.segob.gob.mx/notas/docFuente/5752569
- Reglamento Interior de la Secretaría Anticorrupción y Buen Gobierno, DOF 31/12/2024: https://www.dof.gob.mx/nota_detalle.php?codigo=5746534&fecha=31/12/2024
- Reforma al Reglamento Interior de la SABG, DOF 21/03/2025: https://www.dof.gob.mx/nota_detalle.php?codigo=5752650&fecha=21/03/2025
