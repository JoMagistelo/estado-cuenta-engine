# Matriz de evidencias TIC y ciberseguridad

## Estado Cuenta Engine — SABG / DGEC

**Fecha de corte:** 5 de septiembre de 2026

## 1. Propósito

Esta matriz identifica qué controles aporta directamente el producto y cuáles requieren configuración, validación o aprobación institucional. Su objetivo es facilitar la revisión de TIC y evitar que responsabilidades de infraestructura o protección de datos se confundan con responsabilidades del código.

## 2. Criterios de estado

- **Implementado:** existe evidencia técnica verificable en el código o automatización.
- **Parcial:** existe evidencia técnica, pero requiere completar controles institucionales.
- **Institucional:** corresponde principalmente a TIC u otra área competente.

## 3. Matriz

| Dominio | Estado | Evidencia del producto | Complemento institucional |
|---|---|---|---|
| Control de cambios | Parcial | historial Git, CI y criterios documentados de revisión | protección de línea base, revisores y permisos en plataforma institucional |
| Equivalencia funcional | Parcial | suite sintética, compilación, análisis estático y build | UAT con corpus autorizado y aceptación funcional |
| Dependencias Python | Implementado | `pyproject.toml` como fuente canónica y extras opcionales explícitos | política institucional de actualización y repositorio de paquetes si aplica |
| Vulnerabilidades de dependencias | Implementado | `pip-audit` en CI sobre runtime evaluado | tratamiento/aceptación institucional de hallazgos |
| Inventario de software | Implementado/Parcial | inventario de paquetes generado por CI | integración al inventario/CMDB/SBOM institucional si aplica |
| Build Windows | Implementado | PyInstaller validado automáticamente | canal de distribución y firma de código si TIC la requiere |
| Integridad del artefacto | Implementado | SHA-256 del ejecutable | custodia y registro de liberación institucional |
| Tesseract / terceros | Parcial | runtime identificado y hash SHA-256 | versión, procedencia, licencia, CVE y ciclo de actualización aprobado |
| PaddleOCR/PaddlePaddle | Parcial | extra opcional versionado, import validado en Windows y dependencias auditadas | aprobación del runtime, inventario, licencias, recursos y ciclo de actualización |
| Modelos PaddleOCR | Institucional/Parcial | aplicación exige rutas locales y bloquea descarga automática en runtime | adquisición autorizada, procedencia, licencia, SHA-256, ACL y custodia de modelos |
| Revisión OCR dual | Implementado/Parcial | Tesseract primario; Paddle ante señales objetivas de revisión; ambos candidatos se conservan y Flet/Streamlit permiten seleccionar el resultado visible/exportable | UAT con corpus autorizado antes de habilitar por banco y aceptación del criterio de recomendación/selección |
| Salida de red del OCR | Implementado/Parcial | Paddle usa modelos locales; se deshabilita comprobación de proveedores; no se usa API OCR alojada | reglas de egress/firewall y verificación operativa por TIC |
| Datos personales en código | Implementado | reglas de exclusión, pruebas opt-in y política de seguridad | supervisión y procedimiento institucional de manejo de información |
| Clasificación de información | Institucional | sensibilidad documentada | clasificación formal SABG |
| Documento de Seguridad | Institucional | insumos técnicos disponibles | integración/actualización por área competente |
| Análisis de riesgos y brecha | Parcial | riesgos técnicos identificados | análisis institucional y plan de tratamiento |
| Evaluación de impacto en datos personales | Institucional | necesidad de determinar procedencia documentada | resolución por área competente |
| Identidad y autenticación | Institucional | separación entre motor e identidad | mecanismo SIEC/SSO/API aprobado |
| Autorización y roles | Institucional | motor desacoplado de directorio propio | matriz de roles y mínimo privilegio |
| TLS y certificados | Institucional | arquitectura compatible con reverse proxy | configuración IIS/certificado institucional |
| Red y firewall | Institucional | no se requiere salida de documentos a servicios externos | segmentación, reglas y puertos definidos por TIC |
| Cuenta de servicio | Institucional | requisitos de mínimo privilegio documentados | alta, permisos y operación por TIC |
| Logs y monitoreo | Parcial | criterios de minimización de PII; revisión OCR registra estados/conteos, recomendación y selección sin valores financieros | SIEM, retención, acceso y alertamiento institucional |
| Gestión de incidentes | Parcial | política y guía técnica de respuesta | canal, responsables y procedimiento institucional |
| Vulneraciones de datos personales | Institucional | criterio de escalamiento documentado | bitácora, notificación y procedimiento aplicable |
| Respaldo/recuperación | Institucional | requisitos técnicos documentados | RPO/RTO, backup, restore y pruebas |
| Continuidad operativa | Institucional | rollback de aplicación y desactivación del segundo OCR contemplados | integración al esquema institucional de continuidad |
| Gestión de parches | Parcial | dependencias Python auditadas | Windows Server, IIS, Python, Tesseract, PaddlePaddle y modelos bajo proceso TIC |
| Retención y archivo | Institucional | separación entre temporales y documentos de archivo; candidatos OCR alternos no se persisten automáticamente | reglas SABG de conservación/disposición |

## 4. Evidencia automática de la versión

La automatización de calidad debe producir, como mínimo:

- compilación de `app/`, `src/` y `tests/`;
- análisis estático de errores críticos;
- suite sintética/autocontenida;
- build del paquete Python;
- validación de dependencias de interfaces;
- instalación/import del runtime PaddleOCR/PaddlePaddle opcional en Windows;
- build del ejecutable Windows;
- inventario de paquetes instalados;
- auditoría de vulnerabilidades Python del runtime evaluado;
- hash SHA-256 de Tesseract;
- hash SHA-256 del ejecutable.

Los modelos PaddleOCR no se descargan durante CI ni durante el procesamiento productivo. Su inventario, hash y aprobación forman parte del expediente institucional de liberación cuando la capacidad se habilite.

## 5. Evidencia mínima por liberación

La versión entregada a TIC debería estar acompañada por:

- identificador de versión;
- referencia exacta del código fuente;
- resultado de pruebas automatizadas;
- inventario de dependencias;
- resultado de auditoría de vulnerabilidades;
- hash del ejecutable entregado;
- información del runtime Tesseract;
- cuando PaddleOCR esté habilitado: versiones de PaddleOCR/PaddlePaddle, nombres de modelos, procedencia, licencia y hashes de los modelos autorizados;
- evidencia de UAT de activación, comparación, selección y exportación OCR por banco/layout habilitado;
- evidencia de UAT general cuando corresponda;
- notas de cambio;
- procedimiento de despliegue/rollback;
- aceptación funcional y técnica conforme al proceso institucional.

## 6. Criterios de no liberación

No debe promoverse una versión cuando exista alguno de los siguientes supuestos sin tratamiento formal:

- pruebas automáticas fallidas;
- vulnerabilidad bloqueante conocida;
- cambio de parser sin regresión suficiente;
- dependencia o binario de origen no trazable;
- modelos PaddleOCR sin procedencia/licencia/hash cuando la capacidad esté habilitada;
- segundo OCR activado sin UAT representativa;
- comparación/selección OCR no validada cuando forme parte de la liberación;
- artefacto sin identificación/hash;
- exposición de datos reales en repositorios o evidencias no autorizadas;
- falta de controles de identidad/TLS para un servicio expuesto;
- ausencia de rollback aplicable;
- rechazo funcional o técnico de la versión.

## 7. Configuración de la plataforma institucional

La plataforma de desarrollo y liberación aprobada por TIC debe aplicar, según corresponda:

- acceso por roles;
- revisión obligatoria de cambios;
- protección de la línea base productiva;
- checks de CI obligatorios;
- protección contra reescritura no autorizada;
- administración restringida de secretos y entornos;
- trazabilidad de versiones y liberaciones.

La documentación del motor no depende de un proveedor específico para implementar estos controles.

## 8. Referencias

El marco normativo y sus fuentes oficiales se mantienen en [`05_normativa_tic_apf.md`](05_normativa_tic_apf.md). La guía de despliegue institucional se encuentra en [`06_despliegue_produccion_windows.md`](06_despliegue_produccion_windows.md). La política de revisión OCR se documenta en [`14_paddleocr_fallback.md`](14_paddleocr_fallback.md).
