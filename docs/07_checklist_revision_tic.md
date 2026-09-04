# Checklist de revisión TIC y preparación a producción

## Estado Cuenta Engine — SABG / DGEC

**Fecha de corte:** 4 de septiembre de 2026

Estados utilizados:

- ✅ observado/implementado en el repositorio;
- 🟡 parcial o requiere evidencia adicional;
- ❌ pendiente antes de producción;
- N/A no determinado todavía.

> Esta lista es un instrumento de trabajo. El estatus final debe ser validado por TIC, seguridad de la información, protección de datos, área jurídica, archivo y la unidad funcional competente.

## 1. Gobierno del proyecto

| Control | Estado | Evidencia / pendiente |
|---|---:|---|
| Responsable funcional | 🟡 | Contexto DGEC identificado; formalizar propietario funcional |
| Responsable técnico | ❌ | Designar formalmente |
| Responsable de seguridad | ❌ | Alinear con RIC/PIC de SABG |
| Responsable de datos personales | ❌ | Coordinar con unidad competente |
| Inventario de activos | ❌ | Incluir servidor, código, Tesseract, PDFs, temporales, salidas |
| Gestión de cambios | 🟡 | Git/PR existe; falta procedimiento institucional |
| Versionado de liberaciones | 🟡 | Git existe; definir tags/releases y evidencia |
| Segregación de ambientes | ❌ | Definir Dev/UAT/Prod |

## 2. Repositorio y código fuente

| Control | Estado | Evidencia / pendiente |
|---|---:|---|
| Repositorio Git | ✅ | GitHub |
| Visibilidad adecuada para producción | ❌ | Repositorio actual observado como público; revisar con TIC |
| `.gitignore` básico | ✅ | excluye `.venv/`, `data/`, `logs/`, `output/` |
| Bloqueo explícito de PDFs/Excel/JSON reales | 🟡 | Documentado; endurecer controles técnicos si TIC lo aprueba |
| Revisión de historial por datos personales | ❌ | Ejecutar escaneo de todo el historial Git |
| Secret scanning | ❌ | Habilitar/verificar herramienta institucional/GitHub |
| Branch protection | ❌ | Verificar/configurar para rama productiva |
| Revisión obligatoria de PR | ❌ | Definir regla de aprobación |
| Firma/identidad de releases | ❌ | Definir |

## 3. Arquitectura

| Control | Estado | Evidencia / pendiente |
|---|---:|---|
| Pipeline modular | ✅ | readers → detectors → engine → parsers → validators/exporters |
| PDF digital | ✅ | ReaderManager/PDF readers |
| OCR local | ✅ | TesseractPDFReader |
| Parsers especializados | ✅ | múltiples instituciones/emisores |
| Procesamiento concurrente/incremental | ✅ | `process_bank_statements_incremental` |
| Separación motor/UI | 🟡 | existe conceptualmente; revisar acoplamientos en `app/` |
| API estable | ❌ | no definida |
| Integración Angular | N/A | posible, decisión abierta |
| Diagrama productivo aprobado | ❌ | elaborar con TIC |
| Flujo de datos aprobado | ❌ | elaborar incluyendo temporales y salidas |

## 4. Protección de datos personales

| Control | Estado | Evidencia / pendiente |
|---|---:|---|
| Inventario de datos personales | ❌ | integrar en Documento de Seguridad |
| Finalidad y fundamento documentados | 🟡 | contexto funcional identificado; formalizar jurídicamente |
| Aviso(s) de privacidad | ❌ | revisar aplicabilidad y versión |
| Privacidad desde diseño | 🟡 | criterios documentados; falta evidencia técnica integral |
| Minimización | 🟡 | revisar cada campo de salida |
| Reglas de retención | ❌ | coordinar privacidad + archivo |
| Supresión de temporales | ❌ | probar y documentar |
| Documento de Seguridad | ❌ | obligación institucional a integrar |
| Análisis de riesgos de datos | ❌ | requerido |
| Análisis de brecha | ❌ | requerido |
| Análisis de procedencia de EIPDP | ❌ | realizar antes de producción |
| Derechos ARCO / atención institucional | ❌ | integrar al proceso institucional, no resolver sólo en app |
| Procedimiento de vulneraciones | ❌ | integrar al institucional |

## 5. Seguridad de aplicación

| Control | Estado | Evidencia / pendiente |
|---|---:|---|
| Autenticación | ❌ | no definida para producción |
| Autorización por roles | ❌ | diseñar |
| MFA | N/A | TIC debe determinar aplicabilidad |
| Sesiones seguras | ❌ | revisar especialmente si Streamlit sigue productivo |
| Aislamiento de archivos entre usuarios | ❌ | probar |
| Límites de carga | ❌ | definir |
| Validación de tipo/tamaño de PDF | ❌ | revisar interfaz/capa API |
| Protección path traversal | ❌ | pruebas de seguridad |
| Antimalware de uploads | ❌ | integrar infraestructura institucional si aplica |
| Gestión de errores sin PII | ❌ | revisar código/UI |
| Cabeceras HTTP de seguridad | ❌ | definir en reverse proxy/web server |
| CSRF/CORS | N/A | depende de arquitectura final |
| Rate limiting | N/A | obligatorio evaluar si existe API |

## 6. Dependencias y cadena de suministro

| Control | Estado | Evidencia / pendiente |
|---|---:|---|
| `requirements.txt` | ✅ | existe |
| `pyproject.toml` | ✅ | existe |
| SBOM | ❌ | generar para release |
| Escaneo de CVE Python | ❌ | automatizar |
| Licencias Python | ❌ | inventariar |
| Tesseract incluido localmente | ✅ | `vendor/tesseract/` |
| Procedencia/integridad de Tesseract | ❌ | verificar versión, hashes y origen |
| CVE de Tesseract/libs | ❌ | revisar antes de release |
| Licencias de binarios/modelos | ❌ | revisión legal/TIC |
| Política de actualización | ❌ | definir |

## 7. Pruebas y calidad

| Control | Estado | Evidencia / pendiente |
|---|---:|---|
| Directorio `tests/` | ✅ | existe |
| Pruebas de parsers | ✅ | múltiples extractores cuentan con tests/utilidades |
| Pruebas de readers | ✅ | existen |
| Pruebas de validadores | ✅ | existen |
| Cobertura medida | ❌ | establecer umbral |
| Suite de regresión con layouts sintéticos | 🟡 | fortalecer y formalizar |
| CI automatizado | ❌ | no observado en estructura actual |
| SAST | ❌ | incorporar |
| DAST | ❌ | incorporar cuando exista servicio desplegado |
| Pruebas de carga | ❌ | especialmente OCR/batch |
| Pruebas de PDFs malformados | ❌ | incorporar |
| Pruebas de rollback | ❌ | previo a producción |

## 8. Windows Server

| Control | Estado | Evidencia / pendiente |
|---|---:|---|
| Windows Server definido como objetivo | 🟡 | versión exacta pendiente |
| Baseline de hardening | ❌ | aplicar estándar TIC |
| Cuenta de servicio | ❌ | crear con mínimo privilegio |
| ACL NTFS | ❌ | diseñar/probar |
| Firewall | ❌ | reglas TIC |
| EDR/antimalware | ❌ | integrar estándar institucional |
| Parches | ❌ | calendario y responsable |
| Sin acceso administrativo compartido | ❌ | verificar |
| Sin debug en producción | ❌ | configurar release |

## 9. HTTPS/TLS

| Control | Estado | Evidencia / pendiente |
|---|---:|---|
| DNS institucional | ❌ | solicitar/definir |
| Certificado TLS institucional | ❌ | tramitar mediante procedimiento SABG/TIC |
| Llave privada fuera de Git | 🟡 | regla documentada; verificar técnicamente |
| Renovación del certificado | ❌ | responsable/alertas |
| TLS baseline | ❌ | aplicar configuración TIC |
| HTTP plano bloqueado/redirect | ❌ | definir |
| Prueba de cadena/nombre | ❌ | antes de aceptación |

## 10. Logs, monitoreo e incidentes

| Control | Estado | Evidencia / pendiente |
|---|---:|---|
| Logging técnico definido | ❌ | diseñar esquema minimizado |
| Logs sin PII | ❌ | auditoría de código requerida |
| Correlation/request ID | ❌ | implementar si existe servicio/API |
| Rotación/retención | ❌ | definir |
| Sincronización de hora | ❌ | infraestructura TIC |
| Integración SIEM/monitor | N/A | TIC debe definir |
| Alertas operativas | ❌ | definir |
| Procedimiento de incidentes | ❌ | integrar con SABG |
| Evidencia forense mínima | ❌ | definir |

## 11. Continuidad

| Control | Estado | Evidencia / pendiente |
|---|---:|---|
| Backup | ❌ | definir alcance |
| Restore probado | ❌ | prueba obligatoria |
| RTO | ❌ | definir con negocio/TIC |
| RPO | ❌ | definir con negocio/TIC |
| Recuperación ante desastre | ❌ | integrar a continuidad institucional |
| Rollback de aplicación | ❌ | diseñar/probar |
| Capacidad ante caída de OCR | ❌ | definir tratamiento de cola/error |

## 12. Archivo y conservación

| Control | Estado | Evidencia / pendiente |
|---|---:|---|
| Identificación de expediente/serie | ❌ | coordinar Archivo |
| Plazos de conservación | ❌ | determinar institucionalmente |
| Copias de trabajo vs documento de archivo | ❌ | clasificar |
| Eliminación autorizada | ❌ | procedimiento |
| Backups alineados a conservación | ❌ | evitar copias indefinidas |

## 13. Criterios de NO GO

No liberar a producción si se presenta cualquiera de los siguientes:

- repositorio/artefacto productivo sin control institucional;
- datos reales en repositorio o herramientas públicas;
- ausencia de autenticación cuando exista acceso multiusuario;
- HTTP sin TLS para tráfico con datos personales;
- llave privada/certificado o secretos en código;
- vulnerabilidades críticas sin tratamiento autorizado;
- ausencia de análisis de riesgos y Documento de Seguridad;
- ausencia de política de temporales/retención;
- imposibilidad de restaurar o hacer rollback;
- arquitectura no aprobada por TIC;
- tratamiento intensivo/relevante sin resolver la procedencia de evaluación de impacto;
- pruebas de regresión fallidas.

## 14. Próxima auditoría sugerida

En la siguiente revisión técnica del repositorio conviene auditar código específicamente en:

1. manejo de uploads y temporales en Streamlit/Flet;
2. persistencia accidental de PDFs/OCR;
3. logging y excepciones;
4. dependencias y CVE;
5. historial Git y secretos;
6. seguridad de Tesseract vendorizado;
7. cobertura real de tests;
8. separación `app` ↔ `engine`;
9. diseño de API si se confirma Angular;
10. configuración de despliegue Windows Server.
