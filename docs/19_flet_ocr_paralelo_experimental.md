# OCR paralelo en Flet y portable 4.2 (PR #76)

La versión 4.2 incorpora el procesamiento paralelo validado en la interfaz de desarrollo y en el ejecutable portable. No modifica lectores, parsers, validaciones ni el formato de Excel. Los resultados aparecen conforme termina cada archivo y la exportación conserva el orden original de selección.

## Configuración para usuarios

La aplicación inicia con la opción recomendada:

- **PaddleOCR**, por ofrecer la lectura más precisa;
- **velocidad 8/8**, para procesar varios PDF escaneados al mismo tiempo.

La pantalla evita conceptos como procesos, hilos o núcleos. Tesseract se presenta únicamente como alternativa cuando PaddleOCR no puede procesar un documento. La velocidad sólo debería reducirse si el equipo se vuelve lento o muestra un aviso de memoria insuficiente.

## Funcionamiento interno

- Los PDF digitales conservan su ruta rápida y nunca cargan un modelo OCR.
- Para los documentos escaneados se crean únicamente los trabajadores necesarios, hasta el nivel elegido.
- El presupuesto de CPU se reparte automáticamente para evitar que cada instancia de PaddleOCR intente usar diez hilos simultáneamente.
- La pantalla recibe cada resultado al terminar; el Excel se ordena independientemente.
- La cancelación se comparte con los procesos y los archivos temporales se conservan hasta que todos cierran.

La prueba de 19 archivos terminó en **11:28** y el PDF individual más lento en aproximadamente **11:26**. Esto confirma que el lote quedó limitado por el documento más lento y no por una ejecución secuencial de los siete OCR.

## Integración en el portable

`app/main_desktop.py` carga `main_flet_parallel.py` después del splash. El punto de entrada ejecuta `multiprocessing.freeze_support()` para que Windows/PyInstaller pueda crear procesos hijos sin reabrir la aplicación.

El build ejecuta además `--self-test-parallel-runtime` dentro del EXE final: inicia dos procesos independientes y bloquea la entrega si el mecanismo multiproceso no funciona. Se mantienen las autopruebas de PaddleX, inferencia PaddleOCR real, modelos embebidos y operación offline.

## Construcción de la versión 4.2

Después de fusionar el PR:

```powershell
cd C:\Proyectos\estado-cuenta-engine
git switch master
git pull --ff-only origin master

Remove-Item -Recurse -Force build, dist, .packaging -ErrorAction SilentlyContinue

.\scripts\build_windows_release.ps1 -Version "4.2.0" -PortableOffline

Get-ChildItem .\dist
```

El artefacto principal continúa siendo `dist\Extractor_de_Movimientos_Financieros.exe`. La persona usuaria sólo necesita ese archivo; PaddleOCR, sus modelos y el cliente Flet permanecen embebidos para trabajar sin Internet.
