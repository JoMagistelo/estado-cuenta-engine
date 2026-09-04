# Marco normativo TIC, ciberseguridad y datos personales

## Estado Cuenta Engine — APF / SABG / DGEC

**Fecha de corte de investigación:** 4 de septiembre de 2026

> Este documento resume instrumentos relevantes para la revisión técnica del proyecto. No constituye interpretación jurídica vinculante. La vigencia, alcance y aplicación concreta deberán ser confirmados por las unidades competentes de la SABG y por TIC antes de producción.

## 1. Autoridad rectora TIC en la APF

La **Agencia de Transformación Digital y Telecomunicaciones (ATDT)** cuenta, conforme a la Ley Orgánica de la Administración Pública Federal, con atribuciones para formular y conducir políticas de gobierno digital, informática, tecnologías de la información y comunicación, así como para definir protocolos y emitir instrumentos en materia de seguridad de la información y comunicaciones de la APF.

Implicación para el proyecto: las decisiones de arquitectura, seguridad, interoperabilidad y operación productiva deberán alinearse con los instrumentos vigentes emitidos por la ATDT y con las políticas internas que adopte la SABG.

## 2. Política General de Ciberseguridad para la APF

El **Acuerdo por el que se emite la Política General de Ciberseguridad para la Administración Pública Federal** fue publicado en el DOF el **17 de diciembre de 2025**.

El Acuerdo establece a la Dirección General de Ciberseguridad de la ATDT como unidad encargada de seguimiento, vigilancia, evaluaciones y auditorías de cumplimiento de la Política en las dependencias y entidades de la APF.

La Política organiza la ciberseguridad institucional en ejes que abarcan, entre otros:

- gobernanza y cumplimiento;
- gestión de riesgos y resiliencia;
- protección de infraestructura y activos;
- prevención, detección y respuesta a incidentes;
- identidad y accesos;
- cadena de suministro y terceros;
- capacidades y cultura de ciberseguridad;
- innovación, madurez y mejora continua.

También contempla el **Plan Institucional de Ciberseguridad (PIC)** como instrumento de implementación local de las dependencias.

### Aplicación al Estado Cuenta Engine

El proyecto deberá integrarse al PIC de la SABG y no operar como un esquema de seguridad independiente. Como evidencia mínima del proyecto se recomienda mantener:

- inventario de activos;
- clasificación de información;
- análisis de riesgos;
- plan de tratamiento;
- controles de acceso;
- gestión de vulnerabilidades;
- continuidad y recuperación;
- respuesta a incidentes;
- inventario de dependencias/terceros;
- evidencia de capacitación y operación segura.

## 3. Acuerdo TIC de la APF de 2021

El **Acuerdo por el que se emiten las políticas y disposiciones para impulsar el uso y aprovechamiento de la informática, el gobierno digital, las tecnologías de la información y comunicación, y la seguridad de la información en la Administración Pública Federal**, publicado en el DOF el **6 de septiembre de 2021**, establece políticas y disposiciones de observancia obligatoria para la APF, salvo las excepciones previstas en el propio instrumento.

Este Acuerdo continúa siendo una referencia operativa utilizada por dependencias de la APF. No obstante, desde la creación de la ATDT y la emisión de la Política General de Ciberseguridad 2025, cualquier posible concurrencia, actualización o sustitución parcial debe interpretarse conforme a los instrumentos posteriores y a los criterios que emita la ATDT.

### Criterio documental del proyecto

No se utilizará la etiqueta genérica “MAAGTICSI” como sinónimo automático de normativa vigente. Cuando TIC solicite un control concreto deberá registrarse el **instrumento, artículo/lineamiento, versión y fecha** que lo sustenta.

## 4. Ley General de Protección de Datos Personales en Posesión de Sujetos Obligados

El **20 de marzo de 2025** se expidió una nueva Ley General de Protección de Datos Personales en Posesión de Sujetos Obligados (LGPDPPSO), que sustituyó a la ley de 2017. El texto de Cámara de Diputados reporta última reforma DOF **14 de noviembre de 2025**.

Para este sistema son especialmente relevantes:

### Medidas de seguridad

La ley exige mantener medidas administrativas, físicas y técnicas que protejan los datos y garanticen confidencialidad, integridad y disponibilidad.

### Gestión de riesgos

Las medidas deben considerar riesgo inherente, sensibilidad, desarrollo tecnológico, consecuencias de vulneración, transferencias, número de titulares, incidentes previos y valor potencial de la información para terceros.

### Ciclo de vida y privacidad por diseño

El responsable debe crear políticas internas de gestión considerando obtención, uso y supresión, definir funciones, inventariar datos/sistemas y efectuar análisis de riesgo y brecha.

### Documento de Seguridad

Debe incluir al menos:

- inventario de datos personales y sistemas de tratamiento;
- funciones y obligaciones;
- análisis de riesgos;
- análisis de brecha;
- plan de trabajo;
- monitoreo y revisión;
- programa general de capacitación.

### Vulneraciones

Debe existir bitácora de vulneraciones. La ley contempla notificación a titulares y autoridades cuando una vulneración afecte significativamente derechos patrimoniales o morales.

### Evaluación de Impacto

Cuando un sistema o tecnología implique tratamiento intensivo o relevante de datos personales, la ley prevé la evaluación de impacto en protección de datos personales y su presentación previa ante la autoridad competente.

Para Estado Cuenta Engine deberá documentarse formalmente el análisis de procedencia antes de producción.

## 5. Reglamento Interior de la SABG

El **Reglamento Interior de la Secretaría Anticorrupción y Buen Gobierno**, publicado el **31 de diciembre de 2024** y reformado el **21 de marzo de 2025**, ubica a la **Dirección General de Evaluación de Confianza** dentro de la estructura de la Subsecretaría de Buen Gobierno / Unidad de Políticas para el Servicio Público.

Entre las atribuciones de la DGEC se encuentran:

- instrumentar el proceso de evaluación de confianza para cargos estratégicos, de riesgo o de alto nivel;
- aplicar las evaluaciones previstas por las disposiciones jurídicas;
- emitir el resultado integral y único de la evaluación;
- requerir información y documentación necesaria para el ejercicio de sus atribuciones;
- participar con otras unidades administrativas de la Secretaría en el diseño de los sistemas tecnológicos requeridos en su materia.

Esto sustenta la necesidad de que el sistema sea tratado como una herramienta institucional de apoyo a un proceso regulado y no como una aplicación aislada.

La reforma de marzo de 2025 también establece unidades de la SABG con atribuciones específicas en materia de protección de datos personales, incluyendo elaboración de políticas, seguridad de datos, dictamen de evaluaciones de impacto y auditorías.

## 6. Ley General de Archivos

La **Ley General de Archivos** es aplicable a la gestión documental de los sujetos obligados y exige principios de conservación, procedencia, integridad, disponibilidad y organización documental conforme a instrumentos archivísticos.

### Aplicación al sistema

No debe confundirse “borrar temporales técnicos” con “eliminar documentos de archivo”. Antes de definir retención o eliminación de PDFs y resultados deberá identificarse:

- qué documentos forman parte de un expediente institucional;
- qué unidad es responsable del expediente;
- qué serie documental aplica;
- plazo de conservación;
- transferencia o baja documental;
- tratamiento de copias de trabajo y temporales.

El motor debe permitir cumplir estas reglas, no definirlas unilateralmente.

## 7. Ley General de Responsabilidades Administrativas

La LGRA establece principios y directrices de actuación de las personas servidoras públicas, entre ellos legalidad, profesionalismo, honradez, integridad, rendición de cuentas, eficacia, eficiencia y racionalidad en el uso de recursos públicos.

Para el proyecto esto refuerza la necesidad de:

- segregación de funciones;
- trazabilidad;
- control de cambios;
- uso autorizado de información;
- prevención de accesos indebidos;
- evidencia suficiente para auditoría.

## 8. Normativa interna SABG pendiente de incorporar

Esta documentación pública no sustituye los instrumentos internos que TIC y otras unidades de la SABG determinen. Antes de producción debe solicitarse y mapearse, cuando exista:

- política institucional de seguridad de la información;
- Plan Institucional de Ciberseguridad;
- estándar de hardening de Windows Server;
- política de cuentas privilegiadas;
- política de contraseñas/MFA;
- procedimiento institucional de certificados TLS;
- procedimiento de gestión de vulnerabilidades/parches;
- lineamientos de desarrollo seguro;
- procedimiento de cambios y liberaciones;
- procedimiento de respaldo/recuperación;
- política de bitácoras y monitoreo;
- procedimiento de incidentes;
- política de clasificación de información;
- instrumentos archivísticos;
- Documento de Seguridad y avisos de privacidad aplicables.

Una vez entregados por TIC, deberán incorporarse a la matriz de cumplimiento del repositorio por **nombre, versión y fecha**, evitando copiar documentos internos sensibles al repositorio si su clasificación no lo permite.

## 9. Buenas prácticas técnicas no equivalentes a norma jurídica

Los siguientes marcos pueden ser útiles como apoyo técnico si TIC los adopta o acepta, pero **no se presentan como obligaciones legales automáticas**:

- ISO/IEC 27001;
- ISO/IEC 27002;
- NIST Cybersecurity Framework;
- NIST SP 800-53;
- CIS Controls;
- OWASP ASVS / OWASP Top 10;
- guías de hardening de Microsoft para Windows Server.

## 10. Matriz resumida

| Instrumento | Tipo | Relevancia para el motor | Evidencia esperada |
|---|---|---|---|
| LGPDPPSO vigente | Ley | datos personales, seguridad, EIPDP, vulneraciones | Documento de Seguridad, análisis, controles |
| Política General de Ciberseguridad APF 2025 | Política APF | gobierno, riesgos, identidad, incidentes, terceros | alineación con PIC y controles TIC |
| Acuerdo TIC APF 06/09/2021 | Acuerdo APF | gobierno digital, TIC y seguridad | revisión de arquitectura/proyecto |
| Reglamento Interior SABG | Reglamento | atribuciones DGEC y unidades de datos personales | responsable funcional y coordinación institucional |
| Ley General de Archivos | Ley | conservación y disposición | reglas de expediente/retención |
| LGRA | Ley | integridad, responsabilidad, trazabilidad | controles de acceso/cambios/auditoría |
| Normativa interna TIC SABG | Institucional | operación real | evidencias específicas de TIC |

## 11. Fuentes oficiales consultadas

1. DOF — Política General de Ciberseguridad para la APF, 17/12/2025: https://dof.gob.mx/nota_detalle.php?codigo=5776454&fecha=17/12/2025
2. ATDT — documento de la Política General de Ciberseguridad: https://www.archivos.atdt.gob.mx/storage/app/media/Politica_de_Ciberseguridad_APF.pdf
3. DOF — Acuerdo TIC APF, 06/09/2021: https://www.dof.gob.mx/nota_detalle.php?codigo=5628885&fecha=06/09/2021
4. Cámara de Diputados — LGPDPPSO vigente: https://www.diputados.gob.mx/LeyesBiblio/pdf/LGPDPPSO.pdf
5. DOF/SIDOF — Decreto de nuevas leyes de transparencia y datos personales, 20/03/2025: https://sidof.segob.gob.mx/notas/docFuente/5752569
6. DOF — Reglamento Interior SABG, 31/12/2024: https://www.dof.gob.mx/nota_detalle.php?codigo=5746534&fecha=31/12/2024
7. DOF — reforma al Reglamento Interior SABG, 21/03/2025: https://www.dof.gob.mx/nota_detalle.php?codigo=5752650&fecha=21/03/2025
8. Cámara de Diputados — Ley General de Archivos: https://www.diputados.gob.mx/LeyesBiblio/ref/lga.htm
9. Cámara de Diputados — Ley General de Responsabilidades Administrativas: https://www.diputados.gob.mx/LeyesBiblio/pdf/LGRA.pdf

## 12. Regla de mantenimiento

Esta matriz deberá revisarse:

- antes de cada liberación mayor;
- cuando ATDT emita nuevos lineamientos;
- cuando cambie la LGPDPPSO o normativa de archivos;
- cuando TIC/SABG entregue una nueva política interna;
- cuando cambie la arquitectura de despliegue o se incorpore un tercero/servicio externo.
