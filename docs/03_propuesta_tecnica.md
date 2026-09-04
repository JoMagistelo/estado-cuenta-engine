# Propuesta técnica y ruta a producción

## Estado Cuenta Engine

**Estado:** desarrollo activo  
**Fecha de corte:** 4 de septiembre de 2026

## 1. Resumen ejecutivo

Estado Cuenta Engine automatiza la lectura, clasificación, extracción, normalización, validación y exportación de información contenida en estados de cuenta bancarios. El motor está diseñado para apoyar procesos institucionales autorizados de la Secretaría Anticorrupción y Buen Gobierno, con aplicación prevista en la Dirección General de Evaluación de Confianza (DGEC).

La solución ya soporta PDFs digitales y OCR local con Tesseract, varios parsers especializados, procesamiento por lotes y exportación a Excel. Sin embargo, **todavía no debe considerarse lista para producción**: faltan definiciones y evidencias de seguridad, protección de datos, despliegue, continuidad, operación y gobierno de cambios.

## 2. Arquitectura funcional actual

| Etapa | Componente | Función |
|---|---|---|
| 1 | `ReaderManager` | lectura inicial y selección de camino Digital/OCR |
| 2 | `document_type_detector` | clasificación del documento |
| 3 | `bank_detector` | identificación de institución |
| 4 | `statement_processor` | resolución de parser base/OCR/normalizador |
| 5 | `parsers/*` | extracción especializada |
| 6 | `models/*` | representación unificada |
| 7 | `validators/*` | validaciones de consistencia |
| 8 | `mappers/*` / `exporters/*` | transformación y salida |

## 3. Principios para una liberación institucional

La liberación debe basarse en evidencia y no solamente en funcionamiento técnico. Cada versión candidata debe poder responder:

1. ¿Qué versión exacta se está desplegando?
2. ¿Qué dependencias y binarios contiene?
3. ¿Qué datos personales procesa y con qué finalidad?
4. ¿Dónde se almacenan los originales, temporales y resultados?
5. ¿Quién puede acceder a cada etapa?
6. ¿Qué eventos se registran y durante cuánto tiempo?
7. ¿Cómo se detecta y atiende un incidente?
8. ¿Cómo se recupera el servicio ante falla?
9. ¿Qué pruebas funcionales, de regresión y de seguridad fueron aprobadas?
10. ¿Qué unidad autoriza la puesta en producción?

## 4. Brechas principales identificadas

### 4.1 Gobierno y cumplimiento

Pendiente formalizar con las áreas competentes:

- responsable funcional del sistema;
- responsable técnico/operativo;
- propietario de la información;
- clasificación de activos e información;
- matriz de roles y accesos;
- proceso de alta, cambio y baja de usuarios;
- proceso de gestión de cambios y versiones;
- tratamiento de incidentes y vulneraciones de datos;
- conservación y disposición documental.

### 4.2 Protección de datos personales

Por la naturaleza de los estados de cuenta, el sistema puede tratar nombres, identificadores fiscales, números de cuenta/CLABE, saldos, movimientos, contrapartes, conceptos y otra información financiera vinculada a personas físicas.

Antes de producción deben integrarse, como mínimo:

- inventario de datos personales y sistemas de tratamiento;
- análisis de riesgos de privacidad;
- análisis de brecha;
- plan de trabajo de controles;
- reglas de conservación/supresión;
- procedimiento de ejercicio de derechos aplicable al proceso institucional;
- aviso(s) de privacidad que correspondan al tratamiento;
- Documento de Seguridad;
- análisis de procedencia y, en su caso, Evaluación de Impacto en Protección de Datos Personales.

## 5. Ciberseguridad

La Política General de Ciberseguridad para la Administración Pública Federal publicada el 17 de diciembre de 2025 establece un marco común para dependencias y entidades de la APF. La incorporación de este sistema a producción debe alinearse al Plan Institucional de Ciberseguridad de la SABG y a los lineamientos técnicos que emita la Agencia de Transformación Digital y Telecomunicaciones (ATDT).

Para este proyecto se consideran prioritarios:

- inventario y clasificación de activos;
- gestión de riesgos;
- identidad y control de acceso;
- mínimo privilegio;
- endurecimiento del servidor;
- gestión de vulnerabilidades y parches;
- seguridad de dependencias/cadena de suministro;
- respaldo y recuperación;
- monitoreo y detección;
- respuesta a incidentes;
- capacitación y operación segura.

## 6. Arquitectura productiva prevista

### Decisiones conocidas

- plataforma prevista: **Windows Server** institucional;
- comunicaciones: **HTTPS/TLS**;
- certificado: institucional, conforme al procedimiento y autoridad que determine TIC/SABG;
- motor Python desplegado en infraestructura controlada;
- repositorio productivo y artefactos bajo control institucional.

### Decisiones abiertas

- Streamlit como interfaz operativa, prototipo o componente interno;
- uso o retiro de Flet en producción;
- exposición de una API dedicada;
- integración con la aplicación Angular existente;
- servidor web/reverse proxy y terminación TLS;
- mecanismo de autenticación institucional;
- persistencia de resultados y base de datos;
- integración con directorio institucional;
- estrategia de alta disponibilidad.

Estas decisiones deben cerrarse mediante revisión de arquitectura con TIC antes de comprometer interfaces productivas.

## 7. Recomendación para integración Angular

Si Angular consume el motor, la opción arquitectónica preferible es separar:

```text
Angular
  │
  ▼
API / servicio institucional autenticado
  │
  ▼
Estado Cuenta Engine
  │
  ├─ procesamiento Digital
  ├─ OCR
  ├─ parsers
  └─ validadores
```

Esto permite versionar contratos, aplicar autenticación/autorización, límites de tamaño, trazabilidad, control de concurrencia y políticas de seguridad sin exponer directamente internals de Streamlit.

La decisión definitiva queda pendiente.

## 8. Entregables sugeridos para revisión TIC

Antes de producción se propone contar con:

- README y arquitectura actualizados;
- matriz normativa y de cumplimiento;
- diagrama de contexto y flujo de datos;
- inventario de activos y dependencias;
- Documento de Seguridad de datos personales;
- análisis de riesgos y brecha;
- análisis de procedencia de evaluación de impacto;
- matriz de accesos/roles;
- guía de instalación productiva;
- guía de respaldo/restauración;
- procedimiento de incidentes;
- evidencia de pruebas funcionales y de regresión;
- evidencia de revisión de vulnerabilidades;
- bitácora de versiones y cambios;
- plan de reversa/rollback;
- acta o evidencia de aceptación técnica y funcional.

## 9. Criterio de salida a producción

Una versión sólo debe promoverse a producción cuando:

- el código candidato esté identificado y congelado para revisión;
- las pruebas de regresión estén aprobadas;
- las vulnerabilidades críticas/altas estén tratadas conforme al criterio institucional;
- la arquitectura y controles hayan sido revisados por TIC;
- protección de datos haya validado los instrumentos que correspondan;
- exista respaldo y procedimiento de recuperación probado;
- HTTPS/TLS y el certificado institucional estén instalados correctamente;
- exista una ruta de rollback;
- la operación tenga responsables y procedimiento de soporte definidos.

## 10. Referencias

Consultar:

- [`04_seguridad_datos_personales.md`](04_seguridad_datos_personales.md)
- [`05_normativa_tic_apf.md`](05_normativa_tic_apf.md)
- [`06_despliegue_produccion_windows.md`](06_despliegue_produccion_windows.md)
- [`07_checklist_revision_tic.md`](07_checklist_revision_tic.md)
