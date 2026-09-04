# PaddleOCR como fallback de Tesseract

Esta integración conserva a **Tesseract como OCR primario** y utiliza
**PaddleOCR únicamente cuando el resultado Tesseract presenta señales de
fallo**.

El flujo inicial está habilitado por defecto sólo para `hsbc`:

```text
PDF OCR
  ↓
Tesseract
  ↓
Parser del banco
  ↓
Validaciones / completitud
  ├─ resultado suficiente → conservar Tesseract
  └─ resultado débil       → ejecutar PaddleOCR
                                ↓
                              mismo parser
                                ↓
                              comparar calidad
                                ↓
                              conservar el mejor
```

PaddleOCR es opcional. Si no está instalado, no inicializa, no puede bajar
sus modelos o produce un resultado peor, el engine conserva el resultado de
Tesseract.

## 1. Qué formato entrega PaddleOCRPDFReader

`PaddleOCRPDFReader` devuelve exactamente un `DocumentData`, igual que
`TesseractPDFReader`.

Cada elemento de `spatial_words` contiene como mínimo:

```python
{
    "text": "PAGO",
    "x0": 100.0,
    "x1": 125.0,
    "top": 220.0,
    "bottom": 230.0,
    "doctop": 1012.0,
    "width": 25.0,
    "height": 10.0,
    "upright": True,
    "direction": "ltr",
    "page": 2,
    "confidence": 96.0,
}
```

Las coordenadas detectadas sobre la imagen se convierten nuevamente a
**puntos del PDF**, que es el sistema espacial esperado por los parsers
actuales.

PaddleOCR reconoce texto por líneas. Para mantener compatibilidad con los
parsers actuales, cada línea se divide en tokens y su caja horizontal se
reparte proporcionalmente entre esos tokens.

## 2. Instalación recomendada inicialmente: CPU

Se recomienda probar primero CPU para validar exactitud antes de complicar
la instalación con CUDA.

Dentro del mismo entorno virtual del proyecto:

```powershell
python -m pip install --upgrade pip
python -m pip install paddlepaddle==3.2.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
python -m pip install paddleocr
```

Después verifica imports:

```powershell
python -c "import paddle; print(paddle.__version__)"
python -c "from paddleocr import PaddleOCR; print('PaddleOCR OK')"
```

> PaddleOCR descarga modelos preentrenados la primera vez que inicializa el
> pipeline. La primera ejecución puede tardar más y requiere acceso a red.

## 3. Configuración del fallback

Por defecto sólo HSBC puede disparar PaddleOCR:

```text
PADDLEOCR_FALLBACK_BANKS=hsbc
```

No necesitas definir esta variable para la prueba inicial porque `hsbc` ya
es el valor por defecto.

Para agregar bancos más adelante:

```powershell
$env:PADDLEOCR_FALLBACK_BANKS="hsbc,banorte"
```

Para todos los bancos:

```powershell
$env:PADDLEOCR_FALLBACK_BANKS="*"
```

Para apagar completamente el fallback:

```powershell
$env:PADDLEOCR_FALLBACK_BANKS="off"
```

## 4. Idioma, dispositivo y resolución

Valores predeterminados:

```text
PADDLEOCR_LANG=es
PADDLEOCR_DEVICE=cpu
PADDLEOCR_DPI=300
```

Puedes sobrescribirlos antes de ejecutar la app:

```powershell
$env:PADDLEOCR_LANG="es"
$env:PADDLEOCR_DEVICE="cpu"
$env:PADDLEOCR_DPI="300"
```

La resolución aceptada se limita internamente al rango 150-600 DPI.

## 5. Cuándo se intenta PaddleOCR

Para un documento OCR leído inicialmente por Tesseract, el fallback puede
activarse cuando ocurre alguna de estas condiciones:

- no se extrajo ningún movimiento;
- una o más validaciones financieras existentes devuelven `correcto=False`;
- faltan al menos dos de los cuatro valores centrales del resumen:
  `saldo_anterior`, `depositos_abonos`, `retiros_cargos`, `saldo_final`;
- faltan al menos tres identificadores básicos de cuenta/cliente.

El hecho de intentar PaddleOCR **no significa que se use su resultado**.

## 6. Cómo se elige el OCR ganador

Se calcula una puntuación para ambas candidatas.

Las validaciones financieras tienen el peso principal. También se considera:

- cantidad de movimientos recuperados;
- presencia de los cuatro valores centrales del resumen;
- presencia de cuenta, cliente, nombre y RFC.

PaddleOCR sustituye a Tesseract únicamente si su puntuación es
**estrictamente mayor**.

Esto protege los layouts donde Tesseract ya funciona correctamente.

## 7. Metadata de diagnóstico

Cuando se intenta PaddleOCR, el `DocumentData` seleccionado puede incluir:

```python
{
    "reader": "tesseract" | "paddleocr",
    "paddle_fallback_attempted": True,
    "paddle_fallback_selected": True | False,
    "tesseract_quality_score": 0.0,
    "paddle_quality_score": 0.0,
}
```

Si PaddleOCR falla y se conserva Tesseract:

```python
{
    "paddle_fallback_error": "RuntimeError: ..."
}
```

Esto permite auditar por qué un archivo cambió de OCR sin modificar los
modelos de dominio ni los parsers.

## 8. Probar PaddleOCR directamente

Para aislar el reader del resto del pipeline:

```python
from readers.reader_manager import ReaderManager

pdf = r"C:\ruta\estado_hsbc.pdf"

document = ReaderManager.read_paddle_ocr(pdf)

print(document.metadata)
print(len(document.spatial_words))
print(document.spatial_words[:10])
```

También puedes reutilizar la prueba existente del reader y exportar sus
`spatial_words` a JSON para compararlos contra Tesseract.

## 9. Estrategia recomendada de validación

Antes de habilitar PaddleOCR en más bancos:

1. correr todos los estados HSBC actuales con el fallback habilitado;
2. anotar qué archivos conservaron Tesseract y cuáles eligieron PaddleOCR;
3. revisar movimientos, conceptos, importes y resumen de los archivos que
   cambiaron de motor;
4. confirmar las validaciones financieras;
5. comparar tiempos y memoria;
6. sólo después considerar `PADDLEOCR_FALLBACK_BANKS=*`.

El objetivo de esta primera integración no es reemplazar Tesseract, sino
crear una segunda lectura compatible y medible para los archivos donde
Tesseract no logra un resultado suficientemente confiable.
