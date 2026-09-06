# Entrega del ejecutable Windows a TIC

## Extractor de Movimientos Financieros — SABG / DGEC

**Versión de referencia:** 2.3.x  
**Objetivo:** entregar un ejecutable de escritorio autocontenido, verificable y separado del entorno de desarrollo.

## 1. Alcance actual

La vía inmediata de despliegue es el ejecutable Windows generado con PyInstaller:

```text
Extractor_de_Movimientos_Financieros.exe
```

El EXE inicia la interfaz Flet y utiliza el motor local de extracción. Tesseract se incluye dentro del paquete de escritorio. PaddleOCR/PaddlePaddle sólo deben habilitarse cuando TIC autorice el runtime y disponga de los modelos locales aprobados.

Esta modalidad es adecuada para uso interactivo en una estación de trabajo o en una sesión de escritorio autorizada de Windows Server.

## 2. Build recomendado para entrega

En un equipo Windows controlado por el área técnica, con el ambiente de compilación ya instalado:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows_release.ps1
```

El proceso:

1. ejecuta la regresión no integrada;
2. limpia `build/` y `dist/`;
3. genera el EXE con `EstadoCuentaEngine.spec`;
4. valida que el archivo sea un ejecutable PE;
5. busca marcadores específicos de procedencia del repositorio de desarrollo;
6. calcula SHA-256;
7. genera `release-manifest.json` y `LEEME_TIC.txt`.

La carpeta `dist/` es la unidad de entrega. No deben distribuirse `.git`, `.github`, fuentes Python, archivos de prueba ni documentación de desarrollo junto con el EXE salvo que TIC los solicite como evidencia técnica por un canal separado.

## 3. Procedencia visible del artefacto

El ejecutable no incorpora el repositorio completo. El spec sólo empaqueta el entrypoint, módulos requeridos, runtimes y recursos declarados.

Antes de liberar, `scripts/verify_windows_release.py` rechaza el EXE si detecta identificadores propios del repositorio de desarrollo, por ejemplo el nombre del repositorio o el usuario de desarrollo. Esto evita depender de una revisión visual del archivo final.

La verificación no pretende eliminar atribuciones o avisos de terceros incluidos legalmente por dependencias. Su propósito es impedir que el binario distribuido exponga rutas o identificadores específicos del proyecto de desarrollo.

## 4. Identidad visual del EXE

La compilación genera automáticamente:

- splash institucional con logotipo de Gobierno de México;
- indicador de avance de arranque dinámico;
- icono de aplicación para Windows;
- metadatos PE de producto, versión y dependencia institucional;
- nombre de archivo estable: `Extractor_de_Movimientos_Financieros.exe`.

El logotipo de la interfaz se resuelve desde el directorio temporal de PyInstaller cuando el programa está congelado y desde `assets/` durante desarrollo.

## 5. Instalación operativa mínima

TIC puede colocar el EXE en una ruta controlada, por ejemplo:

```text
C:\Program Files\SABG\ExtractorMovimientos\
```

Recomendaciones:

- ejecutar con cuenta estándar, sin privilegios administrativos;
- permitir escritura sólo en las ubicaciones donde el usuario exportará resultados;
- mantener `%TEMP%` con espacio suficiente porque PyInstaller extrae componentes durante el arranque;
- conservar antimalware/EDR institucional activo;
- validar el hash antes de mover el archivo al ambiente productivo;
- aplicar firma de código institucional si forma parte del estándar de TIC;
- no habilitar descarga de modelos OCR durante la operación.

## 6. Windows Server

El EXE es una aplicación de escritorio. En Windows Server puede ejecutarse dentro de una sesión interactiva autorizada, pero no debe tratarse como un servicio web ni como un proceso de backend multiusuario.

Para una operación centralizada sin escritorio interactivo, la arquitectura recomendada es exponer el motor mediante una capa de servicio/API y mantener la autenticación/autorización en los componentes institucionales definidos por TIC.

## 7. Integración futura con SIEC

Si SIEC en Angular será el punto de acceso de los usuarios:

```text
Usuario institucional
        │
        ▼
SIEC / autenticación institucional
        │
        ▼
API interna del Extractor
        │
        ▼
Estado Cuenta Engine
        │
        ├─ PDF digital
        ├─ Tesseract
        └─ PaddleOCR opcional autorizado
```

No se recomienda que el navegador invoque directamente el EXE. El siguiente paso arquitectónico debe ser una API explícita que reutilice el motor actual y añada autenticación de servicio, autorización, límites de tamaño, concurrencia, trazabilidad, códigos de respuesta, manejo temporal de archivos y versionado del contrato.

La interfaz de escritorio puede mantenerse como herramienta local/operativa aunque exista posteriormente una API.

## 8. Pruebas de aceptación para TIC

Antes de distribuir una versión:

- abrir el EXE desde una ruta distinta al repositorio de desarrollo;
- confirmar que se muestra el logotipo institucional en splash e interfaz;
- confirmar que el indicador de arranque avanza hasta completar;
- verificar icono y propiedades del ejecutable en Windows;
- procesar al menos un PDF digital autorizado;
- procesar al menos un PDF escaneado autorizado con Tesseract;
- comprobar Stop y conservación de resultados terminados;
- comprobar exportación Excel;
- comprobar cierre normal;
- ejecutar el verificador de artefacto;
- conservar SHA-256 y manifiesto de la versión;
- ejecutar antivirus/EDR institucional;
- validar funcionamiento con la cuenta y políticas reales del ambiente objetivo.

## 9. GO / NO-GO del EXE

El ejecutable no debe promoverse si:

- falla la regresión;
- no aparece el branding institucional;
- el verificador detecta identificadores propios del repositorio de desarrollo;
- el hash no coincide;
- Tesseract no funciona en el ambiente objetivo;
- el EDR/antimalware institucional lo bloquea sin resolución;
- se requiere PaddleOCR y los modelos/runtime aún no están autorizados;
- TIC exige firma de código y el archivo todavía no está firmado.

La aprobación de infraestructura, identidad, seguridad, protección de datos y operación sigue siendo responsabilidad de las áreas competentes.
