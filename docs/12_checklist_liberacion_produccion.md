# Checklist de liberación a producción

## Estado Cuenta Engine — SABG / DGEC

Este documento concentra los puntos técnicos que deben verificarse antes de promover una versión a producción institucional.

## 1. Identificación de la versión

- [ ] versión definida;
- [ ] referencia exacta del código fuente registrada;
- [ ] notas de cambio disponibles;
- [ ] responsable funcional identificado;
- [ ] responsable técnico identificado;
- [ ] ventana de liberación autorizada.

## 2. Calidad y equivalencia funcional

- [ ] compilación completa en verde;
- [ ] análisis estático en verde;
- [ ] suite Pytest sintética en verde;
- [ ] build del paquete Python en verde;
- [ ] smoke de dependencias Flet/Streamlit en verde;
- [ ] import del runtime PaddleOCR/PaddlePaddle en Windows validado cuando forme parte de la versión;
- [ ] build PyInstaller Windows en verde;
- [ ] UAT ejecutada con corpus autorizado cuando corresponda;
- [ ] resultados esperados de extracción comparados para cambios funcionales;
- [ ] cambios en parsers identificados explícitamente;
- [ ] revisión final del diff sin modificaciones accidentales.

## 3. Seguridad de software y cadena de suministro

- [ ] auditoría de dependencias sin vulnerabilidades bloqueantes;
- [ ] inventario exacto de dependencias conservado;
- [ ] dependencias nuevas justificadas y revisadas;
- [ ] runtime Tesseract identificado;
- [ ] versión/procedencia/licencia de Tesseract verificadas;
- [ ] vulnerabilidades conocidas de Tesseract evaluadas;
- [ ] si PaddleOCR está habilitado, versiones de PaddleOCR/PaddlePaddle registradas;
- [ ] si PaddleOCR está habilitado, modelos locales identificados por nombre, procedencia, licencia y hash SHA-256;
- [ ] modelos PaddleOCR almacenados fuera del código fuente y bajo ACL institucional;
- [ ] hash SHA-256 del ejecutable registrado;
- [ ] hash de Tesseract registrado;
- [ ] mecanismo institucional de distribución definido;
- [ ] firma de código aplicada si TIC la requiere.

## 4. Fallback OCR PaddleOCR

Aplicar esta sección únicamente cuando el fallback vaya a habilitarse en el ambiente objetivo.

- [ ] `PADDLEOCR_FALLBACK_ENABLED` habilitado únicamente después de UAT;
- [ ] bancos/layouts autorizados definidos en `PADDLEOCR_FALLBACK_BANKS`;
- [ ] `PADDLEOCR_TEXT_DETECTION_MODEL_DIR` apunta al modelo aprobado;
- [ ] `PADDLEOCR_TEXT_RECOGNITION_MODEL_DIR` apunta al modelo aprobado;
- [ ] inferencia local confirmada;
- [ ] no existe descarga de modelos durante una solicitud de procesamiento;
- [ ] no se utiliza API OCR alojada;
- [ ] egress del servidor no es necesario para procesar documentos;
- [ ] fallback sólo se activa ante falla explícita de validación de Tesseract;
- [ ] Paddle sólo se selecciona cuando mejora fallas sin reducir cobertura de validación;
- [ ] casos donde Tesseract valida correctamente permanecen sin cambios;
- [ ] CPU/memoria/tiempo medidos con corpus autorizado;
- [ ] rollback mediante `PADDLEOCR_FALLBACK_ENABLED=0` probado;
- [ ] logs del fallback revisados sin importes ni PII.

## 5. Protección de datos personales

- [ ] clasificación institucional de la información definida;
- [ ] finalidades y usuarios autorizados identificados;
- [ ] principio de minimización revisado;
- [ ] Documento de Seguridad aplicable actualizado;
- [ ] análisis de riesgos y brecha actualizado;
- [ ] procedencia de Evaluación de Impacto determinada;
- [ ] instrumentos de privacidad aplicables revisados;
- [ ] retención y eliminación definidas conforme a archivo y protección de datos;
- [ ] pruebas y evidencias no contienen información real fuera de entornos autorizados.

## 6. Windows Server e IIS

- [ ] servidor Windows definido por TIC;
- [ ] IIS configurado como punto de publicación HTTPS;
- [ ] certificado TLS institucional instalado;
- [ ] nombre DNS institucional configurado;
- [ ] reverse proxy hacia Streamlit configurado;
- [ ] soporte de WebSocket validado;
- [ ] puerto interno de Streamlit no expuesto a usuarios;
- [ ] límites de tamaño y timeouts revisados;
- [ ] cuenta de servicio de mínimo privilegio configurada;
- [ ] ACL de carpetas revisadas, incluyendo modelos OCR locales cuando apliquen;
- [ ] firewall/segmentación aplicados;
- [ ] hardening de servidor aplicado conforme al estándar TIC;
- [ ] antimalware/EDR activo según política institucional.

## 7. Identidad e integración

- [ ] mecanismo de acceso desde SIEC definido;
- [ ] autenticación institucional configurada;
- [ ] autorización/RBAC definida;
- [ ] identidad de servicio definida cuando aplique;
- [ ] MFA aplicado cuando corresponda;
- [ ] si existe integración programática, contrato API documentado;
- [ ] secretos y certificados administrados fuera del código.

## 8. Operación

- [ ] monitoreo y alertamiento configurados;
- [ ] logs minimizados y sin PII innecesaria;
- [ ] retención y acceso a logs definidos;
- [ ] procedimiento de incidentes activo;
- [ ] responsables de escalamiento confirmados;
- [ ] respaldos configurados;
- [ ] restauración probada;
- [ ] RPO/RTO definidos cuando aplique;
- [ ] rollback técnico documentado;
- [ ] capacidad de CPU/memoria/almacenamiento validada para carga OCR esperada.

## 9. Verificación posterior al despliegue

- [ ] HTTPS disponible y certificado válido;
- [ ] acceso al puerto interno bloqueado desde red de usuarios;
- [ ] carga de PDF funcional;
- [ ] procesamiento Digital validado;
- [ ] procesamiento OCR Tesseract validado;
- [ ] fallback PaddleOCR validado si está habilitado;
- [ ] exportación validada;
- [ ] reinicio controlado del servicio validado;
- [ ] logs revisados;
- [ ] rollback disponible.

## 10. Aprobaciones

- [ ] validación funcional DGEC;
- [ ] aprobación TIC/infraestructura;
- [ ] revisión de ciberseguridad cuando aplique;
- [ ] revisión de protección de datos cuando aplique;
- [ ] revisión jurídica/archivo cuando aplique;
- [ ] excepciones de riesgo formalmente documentadas cuando existan.

## 11. Evidencia mínima de la liberación

Conservar en el sistema institucional correspondiente:

- versión y referencia exacta del código;
- resultado de CI/pruebas;
- inventario de dependencias;
- resultado de auditoría de vulnerabilidades;
- hash del ejecutable;
- información del runtime Tesseract;
- cuando aplique, inventario/hashes/licencias de PaddleOCR, PaddlePaddle y modelos autorizados;
- evidencia UAT, incluyendo fallback OCR cuando esté habilitado;
- autorización de cambio;
- aprobaciones aplicables;
- procedimiento de rollback.

## 12. Criterio GO / NO-GO

La versión es **NO-GO** mientras exista un punto clasificado como bloqueante por TIC, seguridad, protección de datos o el responsable funcional.

Una versión técnicamente correcta debe compilar, pasar pruebas, construir su artefacto y contar con evidencia de integridad. La autorización de producción se completa con los controles institucionales de infraestructura, identidad, seguridad, operación y protección de datos.
