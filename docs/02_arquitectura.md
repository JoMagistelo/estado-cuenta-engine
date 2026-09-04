# Arquitectura del proyecto

## Estado Cuenta Engine

**Versión documental:** 2.0  
**Fecha de corte:** 4 de septiembre de 2026

## 1. Objetivo arquitectónico

Estado Cuenta Engine implementa un pipeline modular para convertir estados de cuenta en PDF, digitales o escaneados, a un modelo de dominio común. La arquitectura separa lectura, clasificación documental, detección de institución, parsing, validación y exportación.

La documentación anterior describía una arquitectura inicial sin OCR y con `src/app/`; esa descripción ya no corresponde al repositorio actual.

## 2. Estructura real del repositorio

```text
estado-cuenta-engine/
├── app/
│   ├── main_flet.py
│   └── main_streamlit.py
├── assets/
│   └── logo_gobierno_mexico.png
├── docs/
├── src/
│   ├── catalog/
│   ├── detectors/
│   ├── engine/
│   ├── exporters/
│   ├── extractors/
│   ├── mappers/
│   ├── models/
│   ├── parsers/
│   ├── readers/
│   ├── utils/
│   └── validators/
├── tests/
├── vendor/
│   └── tesseract/
├── EstadoCuentaEngine.spec
├── pyproject.toml
└── requirements.txt
```

## 3. Componentes

### `app/`

Interfaces de usuario actuales. Contiene implementaciones en Streamlit y Flet.

Regla de arquitectura: la interfaz no debe concentrar reglas bancarias ni convertirse en la única forma de invocar el motor. De cara a una posible integración futura con Angular conviene mantener el núcleo desacoplado de la presentación.

### `src/readers/`

Responsable de lectura de documentos.

Componentes actuales relevantes:

- `pdf_text_reader.py`: extracción de texto;
- `pdf_word_reader.py`: extracción de palabras con coordenadas;
- `tesseract_pdf_reader.py`: OCR local;
- `reader_manager.py`: fachada de lectura y selección de etapas;
- `models/document_data.py`: representación del documento leído.

`ReaderManager` permite separar la lectura inicial de texto de la lectura espacial y del OCR. Esto evita ejecutar Tesseract si el PDF ya contiene información utilizable.

### `src/detectors/`

Responsable de clasificación y detección:

- `document_type_detector.py`: determina si el documento puede procesarse como PDF digital o requiere OCR;
- `bank_detector.py`: identifica la institución financiera;
- `filename_bank_detector.py`: apoyo a detección basada en nombre de archivo;
- `clabe_detector.py`: apoyo a detección basada en CLABE.

### `src/engine/`

Orquesta el procesamiento.

`pipeline.py` contiene:

- `PreparedStatement`;
- preparación y clasificación Digital/OCR;
- procesamiento secuencial;
- procesamiento concurrente e incremental;
- separación de workers de clasificación, digitales y OCR;
- validación posterior al parsing.

`statement_processor.py` contiene el registro de parsers base y la resolución de parsers OCR/normalizadores opcionales.

### `src/parsers/`

Contiene parsers especializados. La estructura observada incluye:

- `banamex/`;
- `banorte/`;
- `banorte_ocr/`;
- `bbva/`;
- `cetes/`;
- `hsbc/`;
- `mercado_pago/`;
- `mifel/`;
- `scotiabank/`;
- `normalizadores/`.

Los parsers especializados mantienen extractores separados para datos de cuenta, resumen financiero, movimientos y otros productos cuando aplica.

### `src/models/`

Modelos del dominio y de procesamiento:

- `estado_cuenta.py`;
- `datos_cuenta.py`;
- `resumen_financiero.py`;
- `movimiento.py`;
- `otros_productos.py`;
- `processing_result.py`.

### `src/validators/`

Contiene validaciones de consistencia, incluyendo `movimiento_validator.py`.

### `src/mappers/` y `src/exporters/`

Transforman el modelo a estructuras tabulares y formatos de salida, actualmente con soporte de exportación a Excel.

### `vendor/tesseract/`

Contiene binarios, librerías y modelos de Tesseract versionados con el proyecto. Este punto requiere revisión específica de TIC antes de producción por razones de cadena de suministro, mantenimiento, vulnerabilidades y licenciamiento.

## 4. Flujo actual Digital/OCR

```text
                     ┌────────────────────┐
                     │    PDF recibido     │
                     └─────────┬──────────┘
                               │
                               ▼
                     ReaderManager.read_text_stage
                               │
                    ¿hay texto extraíble?
                        │              │
                      NO               SÍ
                        │              │
                        │       detect_document_type
                        │              │
                        │       ┌──────┴──────┐
                        │       │             │
                        │   texto útil   texto sospechoso
                        │       │             │
                        │       │       spatial_words
                        │       │             │
                        │       │       nueva detección
                        │       │             │
                        │       └──────┬──────┘
                        │              │
                        ▼              ▼
                       OCR          Digital
                        │              │
                        │              │
                        └──────┬───────┘
                               ▼
                      identify_bank_key
                               │
                               ▼
                   process_single_statement
                               │
               ┌───────────────┴────────────────┐
               │                                │
            Digital                            OCR
               │                                │
        parser base                parser <banco>_ocr si existe
                                             │
                                      si no existe:
                                  normalizador opcional +
                                       parser base
               └───────────────┬────────────────┘
                               ▼
                         EstadoCuenta
                               │
                               ▼
                      validar_movimientos
                               │
                               ▼
                       ProcessingResult
```

## 5. Procesamiento por lotes

Existen dos caminos:

- `process_bank_statements(...)`: procesamiento secuencial;
- `process_bank_statements_incremental(...)`: procesamiento concurrente e incremental.

El segundo separa por defecto la carga de clasificación, documentos digitales y OCR, manteniendo un worker OCR limitado para evitar competencia excesiva entre procesos pesados.

## 6. Modelo de confianza y límites

El resultado de extracción debe considerarse **dato derivado sujeto a validación**, no verdad absoluta. La arquitectura debe mantener diferenciables al menos:

- documento de entrada;
- método de lectura (Digital/OCR);
- institución detectada;
- parser aplicado;
- campos extraídos;
- validaciones ejecutadas;
- errores y advertencias.

Cuando se incorpore persistencia productiva, esta trazabilidad deberá diseñarse sin duplicar innecesariamente datos personales en logs.

## 7. Fronteras de seguridad propuestas

Para producción se recomienda separar conceptualmente:

```text
[Cliente / Angular eventual]
          │
          ▼
[HTTPS / control de acceso]
          │
          ▼
[Capa de servicio o API aprobada]
          │
          ▼
[Estado Cuenta Engine]
          │
    ┌─────┴─────┐
    ▼           ▼
[temporales] [salidas autorizadas]
```

No se define todavía una API concreta. Streamlit puede continuar como interfaz de operación o prototipo, pero una integración Angular debería evaluarse mediante una capa de servicio explícita en lugar de acoplar la aplicación cliente a internals de Streamlit.

## 8. Principios para siguientes cambios

1. Mantener compatibilidad con layouts ya soportados mediante pruebas de regresión.
2. Evitar lógica bancaria en `app/`, `readers/`, `models/` o `exporters/`.
3. Mantener el OCR como capacidad local salvo autorización expresa para usar servicios externos.
4. Evitar persistencia implícita de PDFs y datos derivados.
5. Registrar eventos técnicos sin exponer información financiera completa.
6. Someter nuevas dependencias, integraciones y servicios externos a revisión de seguridad y privacidad.
7. Documentar cada cambio relevante de arquitectura antes de liberarlo a producción.
