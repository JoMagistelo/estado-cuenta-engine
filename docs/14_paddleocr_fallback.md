# PaddleOCR como fallback OCR controlado

## Estado Cuenta Engine — SABG / DGEC

**Fecha de corte:** 5 de septiembre de 2026

## 1. Objetivo

PaddleOCR se incorpora como un segundo motor OCR local para aumentar la capacidad de recuperación de documentos escaneados cuando el resultado obtenido con Tesseract presenta inconsistencias financieras verificables.

La integración no reemplaza a Tesseract ni modifica los parsers bancarios. El criterio de activación y de selección se apoya en las mismas validaciones financieras utilizadas por el pipeline del sistema.

El alcance lingüístico de esta integración es **español para documentación bancaria utilizada en México**. No se habilitan otros idiomas en esta versión.

## 2. Flujo de decisión

```text
Documento OCR
     │
     ▼
Tesseract
     │
     ▼
Parser del banco
     │
     ▼
Validación financiera
     │
     ├── Sin fallas ─────────────► conservar Tesseract
     │
     └── Con falla
            │
            ▼
      ¿Fallback habilitado
       y modelos locales
       autorizados disponibles?
            │
       ┌────┴────┐
       │         │
      NO         SÍ
       │         │
       ▼         ▼
 Tesseract    PaddleOCR
                 │
                 ▼
           mismo parser
                 │
                 ▼
        misma validación
                 │
                 ▼
        comparar resultados
                 │
       ┌─────────┴─────────┐
       │                   │
 mejora validación     no mejora / falla
 sin perder cobertura       │
       │                    │
       ▼                    ▼
   PaddleOCR             Tesseract
```

PaddleOCR sólo sustituye a Tesseract cuando:

1. Tesseract produjo al menos una validación financiera y alguna resultó incorrecta;
2. PaddleOCR produce al menos el mismo número de validaciones disponibles;
3. PaddleOCR reduce estrictamente la cantidad de validaciones fallidas.

Si PaddleOCR no está instalado, los modelos no están configurados, la inferencia falla o el resultado no mejora la validación, se conserva el resultado de Tesseract.

## 3. Alcance de la validación

El fallback utiliza `validar_movimientos()` y, por tanto, considera las validaciones disponibles para el documento, entre ellas:

- suma de depósitos/abonos contra el resumen;
- suma de retiros/cargos contra el resumen;
- saldo del último movimiento contra saldo final;
- ecuación saldo anterior + abonos - cargos = saldo final.

No se utiliza una puntuación OCR aislada para decidir qué resultado financiero conservar. La decisión depende de consistencia de negocio verificable y de la cobertura de las validaciones.

## 4. Seguridad y privacidad

La integración está diseñada para ejecución **local dentro de infraestructura autorizada**.

Controles implementados:

- no se utiliza una API alojada de PaddleOCR;
- los documentos no se envían a un servicio OCR externo;
- los modelos no se descargan automáticamente durante el procesamiento;
- los directorios de modelos deben configurarse explícitamente;
- se deshabilita la comprobación automática de proveedores de modelos mediante `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=1`;
- el fallback está deshabilitado por defecto;
- el registro técnico del fallback utiliza estados y conteos de validación, no importes ni contenido financiero.

La documentación oficial de PaddleOCR permite indicar rutas locales para los modelos de detección y reconocimiento; cuando no se proporcionan, la herramienta puede descargar modelos oficiales. Por ese motivo Estado Cuenta Engine exige las rutas locales antes de inicializar PaddleOCR.

Referencias técnicas:

- https://paddlepaddle.github.io/PaddleOCR/main/en/version3.x/pipeline_usage/OCR.html
- https://paddlepaddle.github.io/PaddleX/3.7/FAQ.html

## 5. Componentes controlados

La línea controlada utiliza:

- PaddleOCR `>=3.7,<3.8`;
- PaddlePaddle `>=3.3.1,<3.4`;
- modelo de detección `PP-OCRv5_mobile_det`;
- modelo de reconocimiento `latin_PP-OCRv5_mobile_rec`;
- `PADDLEOCR_LANG=es` como único idioma admitido;
- inferencia CPU como configuración inicial.

PaddleOCR no publica un modelo `es-MX` separado. El modelo oficial `latin_PP-OCRv5_mobile_rec` incluye español y reconocimiento numérico, por lo que se utiliza como componente técnico de reconocimiento mientras la aplicación restringe el idioma a `es`.

Referencia oficial:

- https://paddlepaddle.github.io/PaddleOCR/latest/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.html

Estas versiones forman parte de la línea técnica de esta versión del producto. Cualquier actualización debe pasar por pruebas de regresión, revisión de vulnerabilidades y actualización del inventario de terceros.

## 6. Instalación de dependencia opcional

PaddleOCR no forma parte del runtime mínimo del motor. Se instala únicamente en el entorno institucional donde se autorice el fallback:

```powershell
python -m pip install -e ".[streamlit,paddleocr]"
```

La automatización de calidad instala y audita este extra en Windows para comprobar compatibilidad del runtime y revisar las dependencias Python incorporadas.

## 7. Gestión institucional de modelos

Los modelos no deben incorporarse al código fuente ni obtenerse dinámicamente durante una solicitud de procesamiento.

Antes de habilitar PaddleOCR, TIC debe disponer de un paquete de modelos aprobado que registre como mínimo:

- nombre exacto del modelo;
- versión o referencia de origen;
- fuente oficial de adquisición;
- fecha de adquisición;
- licencia aplicable;
- hash SHA-256 de cada paquete o directorio distribuido conforme al procedimiento institucional;
- revisión de vulnerabilidades/avisos de seguridad aplicables;
- responsable de incorporación;
- ubicación autorizada en servidor.

Ejemplo de ubicación operativa:

```text
C:\ProgramData\EstadoCuentaEngine\PaddleOCR\
    PP-OCRv5_mobile_det\
    latin_PP-OCRv5_mobile_rec\
```

La ubicación definitiva y sus ACL corresponden a TIC.

## 8. Configuración

Variables requeridas para habilitar el fallback:

```powershell
$env:PADDLEOCR_FALLBACK_ENABLED = "1"
$env:PADDLEOCR_FALLBACK_BANKS = "hsbc"

$env:PADDLEOCR_TEXT_DETECTION_MODEL_DIR = `
  "C:\ProgramData\EstadoCuentaEngine\PaddleOCR\PP-OCRv5_mobile_det"

$env:PADDLEOCR_TEXT_RECOGNITION_MODEL_DIR = `
  "C:\ProgramData\EstadoCuentaEngine\PaddleOCR\latin_PP-OCRv5_mobile_rec"

$env:PADDLEOCR_DEVICE = "cpu"
$env:PADDLEOCR_LANG = "es"
$env:PADDLEOCR_DPI = "300"
```

`PADDLEOCR_LANG` debe permanecer en `es`. El reader rechaza expresamente cualquier otro valor para evitar cambios lingüísticos no aprobados en producción.

`PADDLEOCR_FALLBACK_BANKS` admite una lista separada por comas o `*`. Para una primera liberación se recomienda habilitarlo únicamente en los bancos incluidos en la UAT correspondiente y ampliar cobertura de manera controlada.

## 9. Estado por defecto y rollback

El fallback queda **deshabilitado por defecto**. Esto permite instalar el código y sus pruebas sin alterar el comportamiento histórico hasta que TIC y el área funcional completen la validación correspondiente.

Rollback operativo:

```powershell
$env:PADDLEOCR_FALLBACK_ENABLED = "0"
```

Después de reiniciar el servicio, el flujo vuelve a utilizar exclusivamente Tesseract para OCR, sin requerir rollback de código ni modificación de parsers.

## 10. Observabilidad

El `DocumentData.metadata` puede registrar únicamente información técnica del intento:

- si el fallback fue intentado;
- si PaddleOCR fue seleccionado;
- número de validaciones disponibles por motor;
- número de validaciones fallidas por motor;
- tipo de error técnico si PaddleOCR no pudo ejecutarse.

No deben registrarse:

- importes esperados u obtenidos;
- saldos;
- nombres;
- cuentas/CLABE;
- conceptos de movimientos;
- texto OCR completo;
- contenido del PDF.

## 11. Recursos de servidor

PaddlePaddle agrega un runtime de inferencia significativamente mayor que el OCR Tesseract actual. Antes de producción se debe medir con corpus autorizado:

- memoria residente del proceso;
- tiempo adicional cuando se activa el fallback;
- CPU por página;
- espacio de los modelos;
- concurrencia máxima segura;
- comportamiento bajo lotes con múltiples documentos OCR fallidos.

El fallback sólo ejecuta PaddleOCR ante una falla de validación, por lo que no duplica el costo OCR para documentos que Tesseract procesa correctamente.

## 12. Ejecutable de escritorio

El build PyInstaller actual permanece sin PaddleOCR para conservar el artefacto de escritorio existente, su tamaño y su cadena de suministro.

La integración PaddleOCR de esta versión está destinada al runtime Python institucional de la aplicación web/servicio. Si TIC requiere PaddleOCR dentro del ejecutable de escritorio, deberá evaluarse como un cambio de empaquetado separado que incluya PaddlePaddle, modelos, licencias, hashes, tamaño del artefacto y pruebas específicas de distribución.

## 13. UAT recomendada

Antes de habilitar el fallback en producción:

1. instalar el extra PaddleOCR en un ambiente controlado;
2. registrar e instalar los modelos aprobados;
3. confirmar `PADDLEOCR_LANG=es`;
4. habilitar inicialmente un banco/layout objetivo;
5. procesar corpus institucional autorizado que incluya casos correctos y casos donde Tesseract falle validación;
6. incluir nombres, conceptos, abreviaturas bancarias, acentos, `Ñ`, importes, fechas y referencias representativas de documentación mexicana;
7. comprobar que PaddleOCR sólo se ejecuta ante la condición definida;
8. comparar movimientos, resumen y datos relevantes;
9. verificar que los casos correctos de Tesseract no cambien;
10. medir CPU, memoria y tiempos;
11. validar rollback por configuración;
12. documentar la aceptación funcional y técnica.

## 14. Criterios de aceptación TIC

- [ ] PaddleOCR/PaddlePaddle incluidos en inventario de software;
- [ ] versiones aprobadas y auditadas;
- [ ] modelos identificados con procedencia/licencia/hash;
- [ ] modelos instalados en ubicación protegida por ACL;
- [ ] idioma de aplicación restringido a español;
- [ ] no existen descargas de modelos durante el procesamiento;
- [ ] no se requiere transferencia del documento a servicios externos;
- [ ] fallback deshabilitado hasta concluir UAT;
- [ ] condición de activación verificada;
- [ ] selección Paddle vs Tesseract validada con casos representativos;
- [ ] uso de CPU/memoria aceptado;
- [ ] rollback por configuración probado;
- [ ] logs/telemetría sin información financiera o personal innecesaria.

## 15. Responsabilidades

**Equipo de aplicación:** implementación del reader, política de fallback, pruebas, dependencias declaradas y documentación técnica.

**TIC:** aprobación/instalación de runtime y modelos, ubicación/ACL, inventario, vulnerabilidades, configuración de servicio, recursos y operación.

**DGEC / área funcional:** validación de resultados con corpus autorizado y aceptación de la condición de fallback.
