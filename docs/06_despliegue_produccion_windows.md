# Línea base de despliegue productivo en Windows Server

## Estado Cuenta Engine — SABG / DGEC

**Estado:** arquitectura prevista, pendiente de aprobación TIC  
**Fecha de corte:** 4 de septiembre de 2026

> Este documento no es una instrucción para publicar el sistema sin autorización. Define una línea base para discutir con TIC y convertir posteriormente en procedimiento operativo aprobado.

## 1. Objetivo

Desplegar Estado Cuenta Engine en infraestructura Windows Server institucional, protegiendo la confidencialidad, integridad y disponibilidad de los estados de cuenta y de los datos derivados.

## 2. Principios

- servidor administrado por TIC;
- mínimo privilegio;
- separación de ambientes;
- acceso sólo desde redes autorizadas;
- HTTPS/TLS obligatorio;
- certificado institucional gestionado conforme al procedimiento SABG/TIC;
- secretos fuera del repositorio;
- datos temporales controlados;
- trazabilidad sin exposición de contenido financiero;
- parches y vulnerabilidades gestionados;
- respaldo y recuperación probados;
- liberaciones reproducibles y reversibles.

## 3. Ambientes

Se recomienda separar al menos:

```text
DESARROLLO  ->  PRUEBAS/UAT  ->  PRODUCCIÓN
```

### Desarrollo

- datos sintéticos o anonimizados;
- acceso de desarrolladores;
- depuración habilitada sólo cuando sea necesario.

### Pruebas/UAT

- versión candidata a producción;
- datos de prueba controlados;
- configuración similar a producción;
- validación funcional y de seguridad.

### Producción

- sin modo debug;
- sin herramientas de desarrollo innecesarias;
- acceso administrativo limitado;
- cambios sólo mediante proceso de liberación.

## 4. Repositorio y artefactos

El repositorio que contiene código productivo debe quedar bajo control institucional y con acceso restringido según funciones.

El repositorio público actual puede utilizarse únicamente si no contiene información, secretos ni componentes cuya publicación esté restringida y si TIC lo autoriza. Para producción se recomienda evaluar migración o espejo controlado en repositorio institucional privado.

Cada liberación debe identificar:

- tag o commit SHA;
- fecha;
- responsable de liberación;
- dependencias;
- resultados de pruebas;
- vulnerabilidades conocidas aceptadas/tratadas;
- hash del artefacto desplegado cuando aplique.

## 5. Topología recomendada

### Opción A — operación web interna

```text
Usuario institucional
        │
        ▼
HTTPS / certificado institucional
        │
        ▼
Reverse proxy / servidor web aprobado
        │
        ▼
Aplicación Streamlit (red local / localhost)
        │
        ▼
Estado Cuenta Engine
```

En esta opción Streamlit es interfaz de usuario, no API pública.

### Opción B — integración futura con Angular

```text
Angular
  │
  ▼
HTTPS
  │
  ▼
API institucional
  │
  ▼
Estado Cuenta Engine
```

La API deberá diseñarse como capa explícita. No se recomienda que Angular dependa de mecanismos internos de Streamlit para integración programática.

La selección de IIS, reverse proxy, framework API, balanceador o componentes adicionales debe ser aprobada por TIC.

## 6. HTTPS y certificado institucional

Antes de producción:

- obtener el certificado TLS mediante el procedimiento institucional que determine TIC/SABG/Buen Gobierno;
- almacenar la llave privada en el almacén o mecanismo seguro aprobado;
- restringir permisos de la llave privada a la cuenta/servicio necesario;
- deshabilitar protocolos y cifrados obsoletos según estándar institucional;
- definir renovación antes del vencimiento;
- registrar responsable y fecha de expiración;
- probar cadena de confianza y nombre DNS;
- impedir HTTP plano o redirigirlo conforme al diseño aprobado.

Nunca se debe guardar la llave privada en Git.

## 7. DNS y red

Definir con TIC:

- nombre DNS institucional;
- segmento de red;
- origen de conexiones permitidas;
- puertos permitidos;
- reglas de firewall;
- necesidad de WAF/reverse proxy;
- acceso administrativo separado del acceso de usuarios;
- restricciones de salida a Internet.

Por defecto, el motor no necesita enviar datos bancarios a Internet. Las salidas de red deben limitarse a lo estrictamente necesario.

## 8. Cuenta de servicio

La aplicación debe ejecutarse con una cuenta de servicio institucional, no con una cuenta personal ni con privilegios de administrador local salvo justificación excepcional.

La cuenta debe tener únicamente permisos necesarios sobre:

- carpeta de aplicación;
- carpeta temporal autorizada;
- carpeta de salida autorizada;
- logs técnicos;
- recursos compartidos o base de datos cuando se incorporen.

Debe prohibirse el inicio de sesión interactivo cuando la política institucional lo determine.

## 9. Sistema de archivos

Separar, idealmente:

```text
C:\Apps\EstadoCuentaEngine\      código/artefacto
D:\EstadoCuenta\Input\          entradas temporales autorizadas
D:\EstadoCuenta\Work\           trabajo temporal
D:\EstadoCuenta\Output\         salidas autorizadas
D:\EstadoCuenta\Logs\           logs técnicos minimizados
```

Las rutas son sólo ejemplos; TIC debe definir las ubicaciones definitivas.

Controles:

- ACL NTFS por grupo/rol;
- herencia revisada;
- no usar carpetas públicas o perfiles personales;
- cuotas/límites para prevenir llenado de disco;
- limpieza segura de temporales;
- respaldo sólo de información que deba conservarse.

## 10. Entrada de PDFs

Si se implementa carga web/API:

- limitar tamaño máximo;
- verificar extensión y tipo real de archivo;
- rechazar formatos no permitidos;
- renombrar internamente con identificador seguro;
- evitar path traversal;
- no confiar en el nombre enviado por el usuario;
- integrar antimalware/escaneo conforme a infraestructura institucional;
- limitar número de archivos y concurrencia;
- registrar ID de transacción, no contenido del archivo.

## 11. OCR y consumo de recursos

Tesseract es una operación intensiva. El pipeline actual limita por defecto el worker OCR en el procesamiento incremental.

En producción se debe medir:

- CPU por documento;
- memoria máxima;
- tiempo por página;
- espacio temporal;
- concurrencia aceptable;
- comportamiento ante PDFs grandes/corruptos.

Establecer límites para impedir agotamiento de recursos.

## 12. Autenticación y autorización

Pendiente de definición con TIC.

Como mínimo se deberá resolver:

- quién puede cargar documentos;
- quién puede consultar resultados;
- quién puede exportar;
- quién administra el servicio;
- segregación de funciones;
- expiración/bloqueo de sesiones;
- MFA cuando aplique;
- integración con identidad institucional cuando sea posible.

No se recomienda implementar un directorio paralelo de usuarios si existe un mecanismo institucional autorizado reutilizable.

## 13. Sesiones y archivos por usuario

La aplicación debe impedir que un usuario pueda recuperar archivos o resultados de otra sesión por URL, nombre de archivo, caché o ubicación temporal.

Si Streamlit permanece en producción, se deberá revisar específicamente:

- manejo de sesión;
- caché;
- estado compartido;
- descargas;
- uploads temporales;
- configuración de servidor;
- cabeceras de seguridad en la capa frontal;
- límites de carga.

## 14. Secretos

No almacenar secretos en:

- `README`;
- código Python;
- archivos `.py` de configuración;
- variables versionadas;
- archivos `.env` dentro del repositorio;
- scripts de despliegue compartidos.

Usar el mecanismo institucional aprobado (almacén de certificados, variables protegidas, vault o equivalente definido por TIC).

## 15. Logs

Registrar sólo lo necesario para auditoría y soporte:

- timestamp;
- ID de solicitud/proceso;
- usuario/cuenta identificada de manera controlada;
- versión del servicio;
- parser/método;
- resultado técnico;
- código de error;
- duración.

Evitar datos financieros completos y texto extraído.

Definir:

- ubicación;
- ACL;
- rotación;
- tamaño máximo;
- retención;
- envío a SIEM/monitor institucional cuando aplique;
- sincronización de tiempo del servidor.

## 16. Backups y recuperación

Antes de producción debe existir procedimiento probado de:

- respaldo de configuración necesaria;
- respaldo de datos que legalmente deban conservarse;
- restauración;
- recuperación del servicio;
- rollback de aplicación;
- recuperación de certificados/configuración.

No respaldar indiscriminadamente temporales o duplicados de estados de cuenta.

## 17. Vulnerabilidades y parches

Liberación inicial y periódica:

- escaneo de dependencias Python;
- revisión de CVE de Tesseract y librerías incluidas;
- revisión de Windows Server e IIS/reverse proxy si aplica;
- inventario de software;
- parcheo programado;
- retest después de cambios relevantes;
- eliminación de componentes no utilizados.

## 18. Endurecimiento

Aplicar el baseline de hardening que establezca TIC. Como apoyo, y sólo si TIC lo autoriza, pueden usarse guías Microsoft/CIS para revisar:

- servicios innecesarios;
- SMB y protocolos heredados;
- PowerShell y administración remota;
- firewall;
- Defender/EDR;
- auditoría avanzada;
- permisos locales;
- política de bloqueo;
- cifrado de disco/volumen cuando corresponda.

## 19. Liberación

Flujo propuesto:

```text
PR aprobado
  ↓
pruebas automáticas
  ↓
revisión de dependencias
  ↓
build/artefacto identificado
  ↓
UAT
  ↓
pruebas de seguridad
  ↓
aprobación TIC + funcional
  ↓
backup / punto de reversa
  ↓
despliegue
  ↓
smoke test
  ↓
monitoreo
```

## 20. Rollback

Cada despliegue debe tener:

- versión previa identificada;
- pasos de reversa;
- compatibilidad de configuración/datos;
- responsable autorizado;
- criterio de activación del rollback.

## 21. Pendientes de decisión TIC

- [ ] Windows Server versión exacta;
- [ ] servidor web/reverse proxy;
- [ ] Streamlit productivo sí/no;
- [ ] Flet productivo sí/no;
- [ ] API dedicada sí/no;
- [ ] integración Angular sí/no;
- [ ] autenticación institucional;
- [ ] MFA;
- [ ] DNS;
- [ ] certificado TLS y responsable de renovación;
- [ ] base de datos/persistencia;
- [ ] SIEM/monitor;
- [ ] antivirus/EDR;
- [ ] respaldo;
- [ ] RTO/RPO;
- [ ] retención y archivística;
- [ ] procedimiento de soporte.
