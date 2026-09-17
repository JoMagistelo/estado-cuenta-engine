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

En **Configuración** comprueba **PaddleOCR**, Turbo **activado** y **hasta 8 procesos** al abrir. Un `OCR_PRIMARY_ENGINE` explícito prevalece sobre el valor por defecto. El valor es un máximo: si el lote sólo contiene cinco PDF escaneados, se crean cinco procesos OCR aunque el selector indique x8. Si falta RAM o es más lento, ajusta a x6 o x4, o desactiva Turbo. Los ajustes de esta entrada experimental son de la sesión; la interfaz normal sigue intacta.

## Qué cambia y qué no

- El clasificador distingue Digital/OCR con la lógica existente. Los digitales van a los hilos de lectura digital; sólo los escaneados entran en `ProcessPoolExecutor(spawn)`. El pool OCR ni siquiera se crea en lotes exclusivamente digitales. No se garantiza que todos los digitales *empiecen* primero, pero sus resultados no esperan a los OCR anteriores.
- Cada PDF mantiene el pipeline íntegro: OCR → PDF con texto incrustado y verificado → lector canónico → parsers → validaciones. Se conservan las palabras y sus coordenadas; no se omiten páginas. Después de clasificar el lote, el administrador cuenta los PDF OCR, crea entre uno y ocho procesos y reparte entre ellos los CPU lógicos disponibles. Así evita que x4 intente usar 40 hilos Paddle o que x8 intente usar 80. El modo estándar conserva los diez hilos históricos.
- La pantalla recibe `completed` / `error` / `cancelled` de inmediato, incluso si otro PDF anterior continúa trabajando. El Excel conserva el orden de selección entre lotes y después de reprocesar con el motor secundario. La interfaz puede mostrar primero un digital aunque el OCR aparezca antes en el selector.
- Los procesos OCR reciben cancelación compartida. El trabajador en segundo plano espera su cierre antes de que Flet termine el lote y limpie los artefactos; si una biblioteca OCR no coopera, detener puede tardar hasta terminar su operación actual. Evita forzar el cierre de Windows durante la escritura.
- Cada proceso carga sus modelos: ocho procesos pueden agotar RAM o rendir peor que seis o cuatro. Los archivos tampoco tienen la misma cantidad de páginas, por lo que iniciar varios a la vez no implica que terminen juntos. El EXE one-file actual **no** ejecuta esta variante experimental ni ha sido validado con ella.

## Comprobación automática antes de fusionar

Con un lote autorizado de PDF, ejecuta sin mantener otro benchmark o lote activo:

```powershell
python scripts/compare_flet_ocr_modes.py "C:\ruta\lote_pdf" --engine paddleocr --workers 8 --report ".\comparacion_pr76_x8.json"
python scripts/compare_flet_ocr_modes.py "C:\ruta\lote_pdf" --engine paddleocr --workers 6 --report ".\comparacion_pr76_x6.json"
python scripts/compare_flet_ocr_modes.py "C:\ruta\lote_pdf" --engine paddleocr --workers 4 --report ".\comparacion_pr76_x4.json"
```

Deja que el reparto de hilos sea automático en la primera ronda. El JSON registra los procesos OCR efectivos, los hilos por proceso y los CPU lógicos detectados. Sólo para diagnóstico avanzado se puede fijar `--threads-per-worker N`; no compares esa corrida con otra configuración como si fueran equivalentes de rendimiento.

Comprueba equivalencia exacta de datos, movimientos, validaciones, texto y palabras/coordenadas; mide el tiempo total y la memoria en varios intentos. La medición histórica de **463,5 s para 17 PDF con dos procesos** carecía de referencia secuencial. Una observación posterior de aproximadamente 18 frente a 14 minutos sí sugiere trabajo concurrente, pero la captura contiene 19 archivos y no constituye todavía una comparación controlada del mismo lote. La CI sintética y la compilación del EXE normal no sustituyen las pruebas en el Windows de destino. El PR permanece en borrador hasta contar con esta evidencia.
