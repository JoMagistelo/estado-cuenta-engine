# Prueba visual OCR paralelo en Flet (PR #76)

**Esta integración es experimental y optativa.** No modifica `app/main_flet.py`, el EXE publicado, los parsers, los lectores ni el formato de Excel. La variante Flet muestra resultados a medida que terminan y ordena únicamente la lista entregada a Excel según el orden original de selección. No fusionar con producción antes de comprobar equivalencia, velocidad y estabilidad en Windows.

## Actualizar y abrir desde PowerShell

Cierra la aplicación antes de cambiar de rama; revisa `git status` si tienes cambios locales. Si ya creaste `prueba-pr-76` para probar el PR:

```powershell
cd C:\Proyectos\estado-cuenta-engine
git status
git fetch origin
git switch prueba-pr-76
git pull --ff-only origin perf/experimental-ocr-multiprocess-benchmark
flet run app/main_flet_parallel.py
```

Si todavía no tienes la rama local, sustituye `git switch prueba-pr-76` y el `git pull` por `git switch -c prueba-pr-76 origin/perf/experimental-ocr-multiprocess-benchmark`. No necesitas reinstalar dependencias si ya están presentes en el entorno que usa tu terminal.

En **Configuración** comprueba **PaddleOCR**, Turbo **activado** y **4 procesos** al abrir. Un `OCR_PRIMARY_ENGINE` explícito prevalece sobre el valor por defecto. Si falta RAM o es más lento, ajusta a 2 o 3 procesos, o desactiva Turbo. Los ajustes de esta entrada experimental son de la sesión; la interfaz normal sigue intacta.

## Qué cambia y qué no

- El clasificador distingue Digital/OCR con la lógica existente. Los digitales van a los hilos de lectura digital; sólo los escaneados entran en `ProcessPoolExecutor(spawn)`. El pool OCR ni siquiera se crea en lotes exclusivamente digitales. No se garantiza que todos los digitales *empiecen* primero, pero sus resultados no esperan a los OCR anteriores.
- Cada PDF mantiene el pipeline íntegro: OCR → PDF con texto incrustado y verificado → lector canónico → parsers → validaciones. Se conservan las palabras y sus coordenadas; no se omiten páginas ni se modifica el número de hilos de PaddleOCR por proceso.
- La pantalla recibe `completed` / `error` / `cancelled` de inmediato, incluso si otro PDF anterior continúa trabajando. El Excel conserva el orden de selección entre lotes y después de reprocesar con el motor secundario. La interfaz puede mostrar primero un digital aunque el OCR aparezca antes en el selector.
- Los procesos OCR reciben cancelación compartida. El trabajador en segundo plano espera su cierre antes de que Flet termine el lote y limpie los artefactos; si una biblioteca OCR no coopera, detener puede tardar hasta terminar su operación actual. Evita forzar el cierre de Windows durante la escritura.
- Cada proceso carga sus modelos: cuatro procesos pueden agotar RAM o rendir peor que dos. El EXE one-file actual **no** ejecuta esta variante experimental ni ha sido validado con ella.

## Comprobación automática antes de fusionar

Con un lote autorizado de PDF, ejecuta sin mantener otro benchmark o lote activo:

```powershell
python scripts/compare_flet_ocr_modes.py "C:\ruta\lote_pdf" --engine paddleocr --workers 4 --report ".\comparacion_pr76_x4.json"
python scripts/compare_flet_ocr_modes.py "C:\ruta\lote_pdf" --engine paddleocr --workers 2 --report ".\comparacion_pr76_x2.json"
```

Comprueba equivalencia exacta de datos, movimientos, validaciones, texto y palabras/coordenadas; mide el tiempo total y la memoria en varios intentos. La única medición histórica disponible fue **463,5 s para 17 PDF con dos procesos y sin referencia secuencial**: no demuestra un ahorro. La CI sintética y la compilación del EXE normal no sustituyen las pruebas en el Windows de destino. El PR permanece en borrador hasta contar con esta evidencia.
