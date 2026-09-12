# Política OCR de producción

## 1. Propósito

Este documento establece la política de ejecución OCR de Estado Cuenta Engine para operación productiva y deja registrada la decisión arquitectónica que debe conservarse en futuras evoluciones del motor.

El nombre histórico de este archivo se mantiene para preservar referencias documentales existentes. La política descrita a continuación sustituye el comportamiento anterior de fallback OCR automático.

## 2. Decisión de producción

El procesamiento estándar de un lote ejecuta **un solo motor OCR por documento escaneado**.

El motor utilizado es el seleccionado en la configuración antes de iniciar el lote:

- `tesseract`: Tesseract local;
- `paddleocr`: PaddleOCR local con modelos previamente instalados.

La selección se toma como una decisión de ejecución del lote. Los PDFs digitales continúan por su ruta digital y no ejecutan OCR.

Durante el procesamiento estándar:

1. se clasifica el documento como Digital u OCR;
2. si es Digital, se conserva la ruta digital existente;
3. si es OCR, se ejecuta exclusivamente el motor seleccionado;
4. el documento resultante se envía al parser y a las validaciones existentes;
5. el resultado, incluidas validaciones fallidas o ausencia de movimientos, se conserva sin iniciar automáticamente otro OCR.

Un fallo de inicialización del motor seleccionado tampoco cambia silenciosamente al motor alternativo. El archivo se reporta con error y conserva una procedencia inequívoca.

## 3. Motivación

La decisión prioriza propiedades requeridas para una operación institucional predecible:

- **determinismo:** un archivo escaneado no duplica trabajo en función de su resultado financiero;
- **trazabilidad:** el motor reportado es el motor realmente solicitado y ejecutado;
- **tiempo de procesamiento controlable:** una validación fallida no convierte implícitamente un OCR en dos OCR consecutivos;
- **operación explícita:** cualquier uso de un segundo motor debe corresponder a una acción deliberada sobre un archivo concreto;
- **evolución segura:** se conserva la infraestructura de candidatos OCR para una futura función de reprocesado manual, pero queda fuera del flujo automático.

Esta política no modifica parsers bancarios, reglas de extracción, validadores ni exportadores.

## 4. Contrato de auditoría

Para un documento OCR procesado por la ruta estándar, el resultado debe reflejar:

- `ocr_requested_primary_engine`: motor seleccionado para el lote;
- `ocr_primary_engine`: el mismo motor efectivamente ejecutado;
- `ocr_engine`: motor del resultado activo;
- `ocr_secondary_engine`: `None`;
- `fallback_attempted`: `False`;
- `fallback_used`: `False`.

La metadata del `DocumentData` mantiene el mismo principio: no debe indicar ejecución secundaria cuando ésta no ocurrió.

Si el motor seleccionado no puede iniciar, no se fabrica un candidato alternativo ni se modifica la identidad del motor solicitado.

## 5. Motores disponibles y operación sin red

### Tesseract

Tesseract se ejecuta localmente. En la distribución Windows autorizada, su runtime y `tessdata` forman parte de los componentes controlados del producto o de la instalación institucional aprobada.

### PaddleOCR

PaddleOCR se ejecuta localmente y requiere modelos previamente instalados. Estado Cuenta Engine no habilita descargas de modelos durante el procesamiento. La selección de PaddleOCR como motor activo no autoriza tráfico de red ni descarga dinámica de artefactos.

La disponibilidad de dos motores no implica ejecución dual.

## 6. Capacidad secundaria reservada

El código conserva de forma deliberada la capacidad de construir y comparar candidatos OCR, pero dicha capacidad es **opt-in** y no forma parte del procesamiento productivo estándar.

Su finalidad es servir como base para una acción explícita por archivo. Ninguna de las siguientes condiciones debe activar por sí sola el motor secundario:

- conciliación de abonos fallida;
- conciliación de cargos fallida;
- validaciones principales ausentes;
- ausencia de movimientos;
- baja calidad del resultado primario;
- error de arranque del motor seleccionado.

La política productiva sólo podrá cambiar mediante una decisión documentada y una regresión específica.

## 7. Evolución arquitectónica prevista

Las siguientes capacidades forman parte de la ruta de evolución acordada. **No describen funcionalidad implementada por la presente política** y deben incorporarse en cambios separados, verificables y reversibles.

### 7.1 Normalización documental

Se prevé una etapa previa al OCR para normalizar físicamente el documento cuando sea necesario: orientación, deskew, escala, traslación y, cuando corresponda, corrección de perspectiva. La normalización deberá ser independiente de la lógica bancaria siempre que la geometría física lo permita.

### 7.2 OCR como inyector de texto

Tesseract y PaddleOCR evolucionarán de lectores finales de `spatial_words` a motores capaces de generar una capa de texto OCR sobre un PDF normalizado. El artefacto resultante será un PDF seleccionable y auditable.

### 7.3 `PDFWordReader` como fuente espacial canónica

El objetivo es que el lector espacial principal sea `PDFWordReader`: PDFs digitales y PDFs OCR con texto inyectado convergerán antes del parser y producirán el mismo contrato de palabras espaciales.

### 7.4 Registro geométrico por layout

Después de detectar banco/layout podrá aplicarse un motor común de registro geométrico con perfiles de layout. La finalidad es transformar variaciones de un mismo layout —desplazamiento, escala o inclinación residual— a coordenadas canónicas sin introducir excepciones OCR dentro de los parsers.

Los layouts genuinamente distintos continuarán siendo layouts distintos.

### 7.5 Reprocesado manual con motor secundario

La interfaz podrá incorporar, por cada archivo OCR, una acción explícita con el texto de ayuda:

`Reprocesar usando motor secundario`

Esa acción deberá:

1. afectar exclusivamente al archivo seleccionado;
2. ejecutar el motor alternativo sin reabrir un fallback automático del lote;
3. generar su propio PDF con texto inyectado;
4. enviar ese PDF por la ruta espacial/parsing definida para el producto;
5. conservar trazabilidad entre resultado principal y reprocesado.

### 7.6 Descarga de PDFs OCR generados

Los archivos OCR podrán exponer un control sutil para descargar el PDF con texto inyectado. Los documentos digitales no requieren ese artefacto. Cuando un archivo sea reprocesado explícitamente con el motor secundario, podrán coexistir los dos artefactos OCR, uno por motor.

## 8. Límites de esta decisión

La adopción de la política de motor único no implementa todavía:

- generación de PDFs con texto inyectado;
- botones de descarga de PDFs OCR;
- reprocesado manual desde Flet;
- normalización geométrica del documento;
- perfiles de layout;
- transformación canónica de coordenadas;
- sustitución de los readers OCR por inyectores;
- eliminación de parsers OCR históricos.

Estas capacidades deben llegar en pull requests independientes para conservar una regresión clara y reducir el riesgo sobre los parsers ya validados.

## 9. Verificación mínima

Toda modificación posterior a esta política debe comprobar, como mínimo:

1. que un lote OCR con Tesseract seleccionado no ejecuta PaddleOCR;
2. que un lote OCR con PaddleOCR seleccionado no ejecuta Tesseract;
3. que una validación fallida no ejecuta automáticamente el motor secundario;
4. que un error de arranque no cambia silenciosamente de motor;
5. que los PDFs digitales mantienen su ruta existente;
6. que la capacidad secundaria sólo se utiliza mediante una llamada explícita;
7. que parsers, validadores y exportadores conservan su comportamiento salvo cambio funcional documentado.

## 10. Criterio de cambio

Esta política se considera parte del contrato productivo de Estado Cuenta Engine. Cualquier retorno a procesamiento OCR dual automático requiere una decisión arquitectónica nueva, evidencia de rendimiento y precisión, pruebas de regresión y actualización de la documentación operativa antes de liberarse.
