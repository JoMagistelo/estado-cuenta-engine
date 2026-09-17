# Prueba controlada: lote OCR en procesos independientes

**Estado:** experimento optativo. No modifica `master`, el ejecutable portable, la interfaz Flet ni el comportamiento productivo. No fusionar como mejora de rendimiento demostrada hasta medirla en el equipo objetivo.

## Objetivo

Evaluar si procesar varios estados de cuenta al mismo tiempo en procesos Python separados reduce el tiempo de un lote de diez PDF al menos un **50 %**, preservando los resultados. Cada hijo llama al `process_bank_statements()` existente, que mantiene sin modificaciones PaddleOCR, proyección del texto al PDF, verificación, lectura canónica, parsers y validaciones. No se omiten páginas ni se usa un segundo OCR automático.

Este experimento se ejecuta desde el entorno Python de desarrollo, **no desde el EXE portable**. Su resultado permite decidir si merece la pena integrar después el administrador de procesos en Flet y comprobarlo también en el binario PyInstaller. No extrapolar sus tiempos directamente al arranque del EXE.

## Preparación en Windows PowerShell

```powershell
cd C:\Proyectos\estado-cuenta-engine
git fetch origin
git switch perf/experimental-ocr-multiprocess-benchmark
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[desktop,paddleocr]"
```

Elige una carpeta de prueba autorizada con diez PDF representativos. No uses material real fuera del entorno institucional autorizado. Los modelos PaddleOCR deben estar disponibles **localmente** (por ejemplo, desde la carpeta preparada por el build). El script deshabilita consultas a fuentes externas de modelos.

## Medición y comparación estricta

```powershell
python scripts\benchmark_parallel_ocr.py "C:\ruta\lote_de_prueba" --workers 2 --report ".\benchmark_2.json"
```

El comando procesa el lote secuencialmente y después en dos procesos independientes. Compara los resultados bancarios, texto OCR, validaciones y todas las palabras con coordenadas recuperadas de los PDF con capa OCR. Los artefactos se almacenan en un directorio temporal distinto por ejecución y se eliminan al terminar. El JSON registra únicamente métricas agregadas y los índices de los documentos que difieran, nunca su contenido.

Si el modelo sólo existe en un directorio de preparación, utiliza `--model-root "C:\ruta\a\modelos"` (esa carpeta debe contener `PP-OCRv5_mobile_det` y `latin_PP-OCRv5_mobile_rec`). También puedes probar `--workers 3` o `--workers 4`, siempre que el equipo disponga de RAM suficiente. **No cambies `--cpu-threads` en la primera comparación**: se conserva el valor actualmente configurado, o los diez hilos predeterminados del reader. Ajustar los hilos por proceso constituye otro experimento y necesita una nueva referencia de resultados.

Para medir únicamente el paralelo sin volver a pagar el tiempo de la referencia:

```powershell
python scripts\benchmark_parallel_ocr.py "C:\ruta\lote_de_prueba" --workers 2 --parallel-only
```

Esta variante **no demuestra equivalencia**. La primera corrida recomendada es la comparación completa sin `--parallel-only`.

## Criterios para una integración posterior al EXE

1. **Equivalencia:** cero diferencias en resultados funcionales y palabras/coordenadas de la capa OCR. Cualquier diferencia bloquea la integración.
2. **Rendimiento:** reducción de al menos 50 % en tiempo total de un lote representativo, comprobada en varias corridas y más de una computadora objetivo.
3. **Recursos:** sin agotamiento de memoria, procesos huérfanos, bloqueos ni degradación en equipos con menos núcleos. La ejecución multiproceso no garantiza ahorro: diez motores de diez hilos pueden competir por la CPU.
4. **Portable:** una implementación posterior deberá incorporar correctamente `multiprocessing.freeze_support()` en el punto de entrada del EXE, preservar operación offline, evitar ventanas secundarias, conservar cancelación inmediata de la interfaz y superar pruebas reales del ejecutable empaquetado.
5. **Reversibilidad:** conservar el procesamiento de un solo trabajador y permitir regresar a él sin cambiar los parsers ni los lectores.

**Límite explícito:** esta PR sólo añade el banco de pruebas y sus tests. No acelera todavía el EXE que se distribuye ni demuestra por sí misma el objetivo de rendimiento; los tiempos se obtienen al ejecutar el benchmark en la computadora destinataria.
