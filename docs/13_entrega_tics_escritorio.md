# Entrega de escritorio para TICS

## Propósito

Esta guía describe la modalidad de escritorio del **Extractor de Movimientos Financieros** para una distribución controlada en Windows. No sustituye la ruta institucional de integración con SIEC; el ejecutable se mantiene como alternativa operativa y de validación mientras la solución evoluciona hacia un servicio consumido por la plataforma institucional.

## Artefacto de escritorio

El repositorio contiene `EstadoCuentaEngine.spec`, utilizado por PyInstaller para generar:

- `Extractor_de_Movimientos_Financieros.exe`
- manifiesto SHA-256 del ejecutable;
- splash institucional de arranque con identidad gráfica y estado de carga;
- runtime Tesseract versionado;
- Flet como interfaz nativa de escritorio.

El workflow manual **TICS desktop release** instala además el runtime Python de PaddleOCR/PaddlePaddle y genera un paquete de entrega verificable.

## Modelos PaddleOCR

Los modelos de PaddleOCR **no se descargan en tiempo de ejecución**. Esta decisión evita dependencias de red no controladas y permite que TICS gestione el origen, versión e integridad de los modelos autorizados.

Antes de habilitar PaddleOCR en un equipo de destino deben existir modelos locales aprobados y configurarse:

```text
PADDLEOCR_TEXT_DETECTION_MODEL_DIR
PADDLEOCR_TEXT_RECOGNITION_MODEL_DIR
```

El ejecutable puede seguir operando con Tesseract cuando PaddleOCR no está disponible. Cuando una revisión genera resultados válidos de ambos motores, la aplicación no elige silenciosamente uno para exportación: el usuario debe revisar y confirmar explícitamente **Tesseract** o **PaddleOCR** para ese PDF.

## Semántica de Detener

Al pulsar **Detener**:

1. se registra inmediatamente la solicitud de cancelación;
2. no se programan nuevos documentos ni un OCR secundario nuevo;
3. los trabajos pendientes se marcan como cancelados;
4. la interfaz deja de esperar a trabajos que ya estaban dentro de una llamada OCR;
5. los resultados que habían llegado a estado **Terminado** antes de la solicitud permanecen en memoria y pueden exportarse;
6. un archivo que no alcanzó estado **Terminado** antes de la solicitud no se agrega a la exportación.

La cancelación observable por la interfaz se revisa con un intervalo máximo aproximado de 100 ms en el coordinador del lote. Una llamada nativa de OCR que ya estuviera ejecutándose puede tardar un poco más en abandonar su hilo interno; su resultado se descarta y la interfaz no espera por él.

## Cierre de la aplicación durante procesamiento

La interfaz Flet intercepta el cierre de ventana cuando existe un lote activo y ofrece:

- **Seguir trabajando**; o
- **Detener y cerrar**.

`Detener y cerrar` usa la misma cancelación del lote. La ventana recupera el control y se cierra sin esperar a que termine el lote completo. Los resultados ya terminados no se corrompen; si el usuario necesita exportarlos debe hacerlo antes de cerrar la aplicación.

## Arranque del ejecutable

El ejecutable muestra un splash institucional antes de que aparezca la ventana principal. El splash incluye:

- logotipo institucional disponible en `assets/logo_gobierno_mexico.png`;
- nombre del sistema;
- Dirección General de Evaluación de Confianza;
- indicador visual de carga;
- mensajes de estado de arranque.

El splash se cierra cuando Flet ha construido la interfaz principal, evitando la impresión de que el programa no respondió durante el arranque de un ejecutable de un solo archivo.

## Controles mínimos antes de distribución

TICS debe verificar, al menos:

- compilación desde un commit/tag identificado;
- resultado exitoso del workflow `Production readiness`;
- resultado exitoso del workflow manual `TICS desktop release` para el binario completo;
- coincidencia SHA-256 antes y después de transferir el ejecutable;
- política de firma de código de la Secretaría, cuando corresponda;
- origen e integridad de los modelos PaddleOCR autorizados;
- permisos de lectura de PDFs y escritura del Excel únicamente en las rutas requeridas;
- ejecución sin privilegios administrativos salvo que una política institucional disponga lo contrario;
- prueba funcional de Detener, cierre de ventana, selección OCR dual y exportación parcial controlada.

## Arquitectura recomendada a mediano plazo

Para integración institucional con SIEC/Angular, la recomendación sigue siendo desacoplar el motor de extracción de la interfaz y exponerlo mediante una API interna con autenticación, autorización, trazabilidad y controles definidos por TICS. Streamlit puede mantenerse como interfaz técnica/de validación; Flet es la opción más adecuada del repositorio actual cuando se necesita una aplicación de escritorio empaquetable para Windows.
