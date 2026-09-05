# Seguridad y protección de datos personales

## Estado Cuenta Engine — SABG / DGEC

**Fecha de corte:** 5 de septiembre de 2026

## 1. Naturaleza de la información

Los estados de cuenta pueden contener información financiera y datos personales, entre ellos:

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

La exposición, alteración o pérdida de esta información puede producir afectaciones patrimoniales, de privacidad y de confianza institucional. Por ello el sistema debe operar bajo medidas administrativas, físicas y técnicas acordes con la clasificación y el riesgo determinados por la SABG.

## 2. Principios de tratamiento

El diseño y operación deben observar:

- finalidad determinada y legítima;
- proporcionalidad y minimización;
- calidad y exactitud;
- confidencialidad, integridad y disponibilidad;
- privacidad desde el diseño y por defecto;
- mínimo privilegio;
- necesidad de conocer;
- conservación únicamente por el tiempo autorizado;
- trazabilidad de accesos y operaciones.

## 3. Controles técnicos esperados

En el contexto de Estado Cuenta Engine se consideran relevantes:

- autenticación institucional;
- autorización por roles;
- mínimo privilegio;
- cifrado en tránsito mediante TLS;
- protección de datos en reposo conforme a la arquitectura aprobada;
- gestión segura de secretos y certificados;
- hardening de Windows Server e IIS;
- gestión de vulnerabilidades y parches;
- control de carpetas temporales;
- respaldo y recuperación;
- monitoreo de eventos de seguridad;
- procedimiento de incidentes;
- segregación de ambientes y funciones.

## 4. Documento de Seguridad

El responsable institucional deberá integrar y mantener el Documento de Seguridad aplicable. Para este sistema conviene identificar separadamente:

- PDF original;
- texto extraído;
- palabras/posiciones espaciales;
- salida OCR;
- modelos internos;
- resultados de validación;
- exportaciones;
- temporales;
- bitácoras;
- respaldos;
- persistencias futuras, cuando existan.

El Documento de Seguridad, análisis de riesgos, brecha, plan de trabajo, monitoreo y capacitación corresponden al marco institucional y deben incorporar los controles técnicos del producto.

## 5. Evaluación de Impacto en Protección de Datos Personales

La LGPDPPSO vigente contempla la evaluación de impacto cuando se pretenda poner en operación o modificar sistemas, plataformas, aplicaciones u otras tecnologías que impliquen tratamiento intensivo o relevante de datos personales.

Por la naturaleza del tratamiento, la procedencia debe ser determinada formalmente por el área competente antes de la puesta en producción. La documentación técnica del motor sirve como insumo para esa determinación, particularmente en arquitectura, flujo de datos, temporales, exportaciones y controles de acceso.

## 6. Datos de personas servidoras públicas

La calidad de persona servidora pública no convierte automáticamente toda la información financiera o personal en información pública. El tratamiento debe responder a atribuciones institucionales, finalidad autorizada y reglas aplicables de protección de datos, transparencia y clasificación de información.

El sistema no debe reutilizar información para finalidades distintas a las autorizadas.

## 7. Datos de terceras personas

Los estados de cuenta pueden incluir información de beneficiarios, ordenantes, comercios u otras contrapartes. Estos datos deben permanecer dentro del flujo autorizado y sujetarse a minimización.

Las salidas deben incluir únicamente los campos necesarios para la finalidad institucional y evitar duplicaciones innecesarias.

## 8. Desarrollo y pruebas

No deben incorporarse al repositorio ni a herramientas de desarrollo no autorizadas:

- estados de cuenta reales;
- imágenes o capturas identificables;
- OCR, JSON o datos derivados de documentos reales;
- Excel con resultados reales;
- bases de datos o volcados;
- logs con PII;
- RFC, CURP, CLABE, cuentas o referencias reales en fixtures;
- secretos o certificados privados.

Se permiten:

- fixtures sintéticos;
- datos anonimizados/disociados conforme al procedimiento aprobado;
- ejemplos completamente ficticios;
- estructuras de layout sin contenido personal.

## 9. Logs y observabilidad

Los logs productivos deben limitarse a información técnica necesaria, por ejemplo:

- identificador de procesamiento;
- fecha/hora;
- versión del motor;
- método Digital/OCR;
- parser aplicado;
- estado de la operación;
- código de error;
- duración;
- identidad técnica o institucional cuando proceda.

No registrar por defecto:

- texto completo del PDF;
- conceptos de movimientos;
- cuentas o CLABE completas;
- RFC/CURP completos;
- nombres completos;
- saldos o movimientos completos;
- claves de rastreo completas;
- secretos o tokens.

## 10. Temporales

Antes de producción deben definirse y probarse:

- ubicaciones temporales;
- ACL de las carpetas;
- nombres de archivo sin datos personales innecesarios;
- limpieza posterior al procesamiento;
- limpieza ante error o reinicio;
- comportamiento ante cierre inesperado;
- aislamiento entre procesos/sesiones;
- política de retención.

## 11. Vulneraciones e incidentes

El sistema debe integrarse al procedimiento institucional de incidentes y vulneraciones de datos personales.

La evidencia técnica útil incluye:

- versión desplegada;
- ventana temporal del incidente;
- logs de acceso/error autorizados;
- activos afectados;
- hashes de artefactos;
- cambios recientes;
- cuentas o identidades involucradas;
- acciones de contención y recuperación.

La conservación de evidencia debe evitar replicar datos personales innecesarios.

## 12. Servicios externos y terceros

No deben enviarse documentos, texto extraído o resultados financieros a servicios externos sin revisión y autorización institucional previa.

Si se incorpora un tercero o encargado, deberán revisarse al menos:

- fundamento y contrato/instrumento aplicable;
- medidas de seguridad;
- ubicación del tratamiento;
- transferencias;
- subencargados;
- retención;
- devolución o supresión de información;
- continuidad y respuesta a incidentes.

## 13. Checklist mínimo de privacidad

- [ ] finalidad y fundamento documentados;
- [ ] responsable funcional identificado;
- [ ] inventario de datos y sistemas de tratamiento;
- [ ] flujos de datos documentados;
- [ ] análisis de riesgos;
- [ ] análisis de brecha;
- [ ] Documento de Seguridad actualizado;
- [ ] instrumentos de privacidad aplicables revisados;
- [ ] análisis de procedencia de EIPDP;
- [ ] reglas de retención y supresión;
- [ ] roles y accesos autorizados;
- [ ] procedimiento de incidentes/vulneraciones;
- [ ] logs minimizados;
- [ ] pruebas con datos sintéticos o autorizados;
- [ ] revisión de terceros/transferencias;
- [ ] capacitación del personal involucrado.

## 14. Fuentes oficiales

- Ley General de Protección de Datos Personales en Posesión de Sujetos Obligados, Cámara de Diputados: https://www.diputados.gob.mx/LeyesBiblio/pdf/LGPDPPSO.pdf
- Decreto de expedición de la LGPDPPSO, DOF 20/03/2025: https://sidof.segob.gob.mx/notas/docFuente/5752569
- Reglamento Interior de la Secretaría Anticorrupción y Buen Gobierno, DOF 31/12/2024: https://www.dof.gob.mx/nota_detalle.php?codigo=5746534&fecha=31/12/2024
- Reforma al Reglamento Interior de la SABG, DOF 21/03/2025: https://www.dof.gob.mx/nota_detalle.php?codigo=5752650&fecha=21/03/2025
