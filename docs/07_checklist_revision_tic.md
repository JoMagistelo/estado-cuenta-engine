# Checklist de revisión TIC

## Estado Cuenta Engine — SABG / DGEC

**Fecha de corte:** 5 de septiembre de 2026

## 1. Objetivo

Facilitar la revisión técnica de la solución y distinguir entre controles incluidos en el producto y controles que deben completarse en infraestructura institucional.

## 2. Producto y código fuente

- [x] arquitectura modular por readers, detectors, engine, parsers, validators y exporters;
- [x] soporte para PDF digital y OCR local con Tesseract;
- [x] dependencias declaradas en `pyproject.toml`;
- [x] pruebas automatizadas sintéticas/autocontenidas;
- [x] build Windows con PyInstaller;
- [x] validación de Python 3.12 y 3.13;
- [x] auditoría de dependencias Python;
- [x] inventario de paquetes por corrida de CI;
- [x] hash SHA-256 del ejecutable;
- [x] hash SHA-256 del runtime Tesseract;
- [x] reglas para evitar PII, secretos y documentos reales en el repositorio;
- [x] documentación de arquitectura, seguridad, despliegue y liberación.

## 3. Regresión funcional

- [x] los parsers se consideran lógica crítica;
- [x] los cambios funcionales requieren pruebas específicas;
- [x] las pruebas con documentos reales son opt-in y permanecen fuera del repositorio;
- [x] CI compila `app/`, `src/` y `tests/`;
- [x] CI ejecuta Ruff y Pytest;
- [x] CI valida la construcción del artefacto Windows;
- [ ] UAT con corpus institucional autorizado para la versión candidata;
- [ ] aceptación funcional de DGEC para liberación productiva.

## 4. Windows Server e IIS

TIC deberá confirmar y configurar:

- [ ] versión soportada de Windows Server;
- [ ] IIS y mecanismo de reverse proxy aprobado;
- [ ] soporte de WebSocket para Streamlit;
- [ ] nombre DNS institucional;
- [ ] certificado TLS institucional;
- [ ] puerto interno de Streamlit restringido a localhost/red interna autorizada;
- [ ] cuenta de servicio de mínimo privilegio;
- [ ] ACL NTFS sobre aplicación, temporales, salida y logs;
- [ ] reglas de firewall y segmentación;
- [ ] baseline de hardening;
- [ ] antimalware/EDR;
- [ ] calendario de parches;
- [ ] procedimiento de despliegue y rollback.

## 5. Identidad y acceso

TIC y el área funcional deberán definir:

- [ ] mecanismo de autenticación institucional;
- [ ] integración con SIEC cuando corresponda;
- [ ] matriz de roles/autorizaciones;
- [ ] identidad de servicio para integraciones;
- [ ] MFA cuando aplique;
- [ ] segregación de funciones;
- [ ] altas, cambios y bajas de acceso.

El motor no incorpora un directorio de usuarios propio para evitar duplicar controles de identidad institucional.

## 6. Protección de datos personales

Las áreas competentes deberán validar:

- [ ] clasificación formal de la información;
- [ ] inventario de datos personales y sistemas de tratamiento;
- [ ] finalidades y fundamento aplicables;
- [ ] Documento de Seguridad;
- [ ] análisis de riesgos y brecha;
- [ ] procedencia de Evaluación de Impacto;
- [ ] avisos/instrumentos de privacidad aplicables;
- [ ] reglas de conservación y supresión;
- [ ] procedimiento de vulneraciones de datos personales.

El producto aporta criterios de minimización, exclusión de PII en logs y tratamiento local de documentos.

## 7. Dependencias y terceros

- [x] dependencias Python declaradas;
- [x] auditoría automatizada de vulnerabilidades Python;
- [x] inventario de paquetes;
- [x] Tesseract identificado como componente de terceros;
- [x] hash de integridad de Tesseract generado;
- [ ] versión y procedencia de Tesseract formalmente registradas para la liberación;
- [ ] licencia de Tesseract y componentes distribuidos revisada;
- [ ] CVE de Tesseract y librerías nativas revisados;
- [ ] política institucional de actualización definida;
- [ ] SBOM generado si TIC lo requiere.

## 8. Logs, monitoreo e incidentes

- [x] política de no registrar contenido financiero innecesario;
- [x] guía técnica de gestión de vulnerabilidades/incidentes;
- [ ] ubicación y ACL de logs definidas por TIC;
- [ ] rotación y retención definidas;
- [ ] integración con monitoreo/SIEM cuando corresponda;
- [ ] alertas operativas configuradas;
- [ ] canal y responsables de incidentes definidos;
- [ ] sincronización de hora institucional validada.

## 9. Continuidad

- [ ] alcance de respaldo definido;
- [ ] restauración probada;
- [ ] versión anterior disponible para rollback;
- [ ] RTO/RPO definidos cuando aplique;
- [ ] recuperación de configuración/certificados documentada;
- [ ] capacidad del servidor validada con carga OCR representativa.

## 10. Archivo y conservación

- [ ] distinguir documento de archivo, copia de trabajo y temporal;
- [ ] definir expediente/serie documental cuando corresponda;
- [ ] establecer plazos de conservación;
- [ ] definir eliminación/baja autorizada;
- [ ] evitar copias indefinidas en respaldos o temporales.

## 11. Criterios de no liberación

La versión no debe promoverse a producción si existe alguno de los siguientes puntos sin tratamiento formal:

- pruebas automáticas fallidas;
- vulnerabilidad crítica/alta bloqueante;
- parser modificado sin regresión suficiente;
- artefacto o dependencia sin origen/integridad identificable;
- TLS o identidad sin resolver para un servicio expuesto;
- información real fuera de entornos autorizados;
- ausencia de rollback;
- rechazo funcional;
- incumplimiento de un control clasificado como obligatorio por TIC o las áreas competentes.

## 12. Documentación asociada

- [`05_normativa_tic_apf.md`](05_normativa_tic_apf.md)
- [`06_despliegue_produccion_windows.md`](06_despliegue_produccion_windows.md)
- [`09_verificacion_tecnica_version.md`](09_verificacion_tecnica_version.md)
- [`10_matriz_evidencias_tic.md`](10_matriz_evidencias_tic.md)
- [`11_gestion_vulnerabilidades_incidentes.md`](11_gestion_vulnerabilidades_incidentes.md)
- [`12_checklist_liberacion_produccion.md`](12_checklist_liberacion_produccion.md)
