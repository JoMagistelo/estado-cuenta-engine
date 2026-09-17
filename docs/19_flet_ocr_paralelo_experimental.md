# Prueba visual OCR paralelo en Flet (PR #76)

**Esta integración es experimental y optativa.** No modifica `app/main_flet.py`, el EXE publicado, los parsers, los lectores, el PDF incrustado ni el Excel. Abre una variante de la misma interfaz Flet que incorpora la opción en **Configuración**; no fusionar con producción antes de comprobar equivalencia y estabilidad en Windows.

## Arrancar desde PowerShell

Primero cierra la app y espera a que termine cualquier benchmark en ejecución.

```powershell
cd C:\Proyectos\estado-cuenta-engine
git fetch origin
git switch perf/experimental-ocr-multiprocess-benchmark
git pull --ff-only origin perf/experimental-ocr-multiprocess-benchmark
.\.venv\Scripts\Activate.ps1
flet run app/main_flet_parallel.py
```

En la aplicación, abre el engrane **Configuración**, selecciona `PaddleOCR` como motor activo, activa **Procesamiento OCR paralelo (experimental)**, elige **2 procesos** con el deslizador y pulsa **Guardar**. El encabezado indica `OCR x2 procesos`. Selecciona los mismos PDF y pulsa Procesar normalmente: la lista existente mostrará varios escaneados en estado `Procesando` a la vez y conservará los resultados conforme terminen. Si quieres probar tres o cuatro trabajadores, cierra primero otros programas que consuman mucha memoria; no hay garantía de una mejora adicional.

Para regresar al comportamiento anterior, desactiva el interruptor en Configuración y guarda. Si deseas ejecutar la interfaz original sin el adaptador, usa `flet run app/main_flet.py`. Los ajustes del modo experimental **no se guardan entre aperturas**: comienza desactivado por seguridad. No cambies estos ajustes durante un lote; Configuración se deshabilita mientras se procesa.

## Qué cambia y qué no

- Se conserva `engine.pipeline._process_prepared_statement` para cada PDF completo, incluida su ruta OCR → PDF con capa verificada → lectura digital → parsers → validaciones. No se omiten páginas y no se modifica el número predeterminado de hilos de PaddleOCR por proceso.
- Solo los PDF clasificados como OCR se envían a procesos Python separados. Los PDF digitales conservan su `ThreadPoolExecutor` habitual. La interfaz conserva estados por archivo, botón Detener, revisión del resultado y exportación.
- Los procesos se inician con `spawn` y reciben una señal compartida de cancelación. Detener marca como cancelados los trabajos pendientes y avisa a los OCR en curso; la cancelación dentro de una página no es instantánea. No cierres Windows a la fuerza mientras se estén escribiendo PDF.
- El programa puede consumir más RAM, un proceso por juego de modelos. En Windows, si aparece `BrokenProcessPool`, errores de memoria u otra excepción, desactiva el modo experimental y conserva la salida de consola para diagnóstico. No se realiza un reproceso automático silencioso de archivos fallidos.
- **Esta variante es para `flet run` con el entorno Python local**. El EXE one-file actual sigue sin paralelismo. Integrarlo en el portable exige `freeze_support()`, pruebas con el binario offline y controles adicionales de procesos/cancelación.

## Validación requerida

La medición aportada por el usuario fue **463.5 segundos (7 min 43.5 s) para 17 PDF con 2 procesos**, realizada con `--parallel-only`; no demuestra por sí sola equivalencia ni una reducción porcentual frente a los mismos 17 PDF en Flet. Compara movimientos, encabezados, totales, validaciones y PDFs incrustados frente al modo original utilizando los mismos archivos, además del tiempo total. Para comparación automatizada estricta, ejecuta `scripts/benchmark_parallel_ocr.py` sin `--parallel-only` sobre un conjunto autorizado de prueba. Mantén esta PR en borrador hasta terminar la evaluación.
