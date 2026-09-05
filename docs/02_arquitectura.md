# Arquitectura del sistema

## Estado Cuenta Engine — SABG / DGEC

**Versión documental:** 2.0  
**Fecha de corte:** 5 de septiembre de 2026

## 1. Objetivo arquitectónico

Estado Cuenta Engine implementa un pipeline modular para convertir estados de cuenta bancarios en PDF, digitales o escaneados, a un modelo de dominio común.

La arquitectura separa:

- lectura documental;
- clasificación Digital/OCR;
- detección de institución;
- parsing especializado;
- validación;
- mapeo/exportación;
- presentación.

Esta separación permite evolucionar parsers y reglas bancarias sin acoplarlas innecesariamente a interfaces, infraestructura o exportadores.

## 2. Estructura principal

```text
estado-cuenta-engine/
├── app/
│   ├── main_flet.py
│   └── main_streamlit.py
├── assets/
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
└── pyproject.toml
```

## 3. Capas y responsabilidades

### `app/`

Interfaces de usuario.

- `main_flet.py`: interfaz de escritorio;
- `main_streamlit.py`: interfaz web.

La interfaz consume el pipeline; no debe concentrar lógica bancaria.

### `src/readers/`

Responsable de convertir el PDF a representaciones utilizables por el motor.

Componentes principales:

- `pdf_text_reader.py`: extracción de texto;
- `pdf_word_reader.py`: extracción de palabras y coordenadas;
- `tesseract_pdf_reader.py`: OCR local;
- `reader_manager.py`: fachada de lectura;
- modelos de documento leído.

### `src/detectors/`

Responsable de clasificación e identificación:

- tipo documental Digital/OCR;
- institución financiera;
- señales auxiliares por nombre de archivo o CLABE cuando corresponda.

### `src/engine/`

Orquesta el flujo de procesamiento.

`pipeline.py` administra:

- preparación de documentos;
- clasificación;
- lectura Digital/OCR;
- procesamiento secuencial;
- procesamiento concurrente/incremental;
- validaciones posteriores.

`statement_processor.py` resuelve el parser correspondiente y los componentes OCR/normalización compatibles con el banco.

### `src/parsers/`

Contiene la lógica especializada por institución/layout.

La estructura actual incluye parsers para:

- Banamex;
- Banorte;
- Banorte OCR;
- BBVA;
- CETES;
- HSBC;
- Mercado Pago;
- Mifel;
- Scotiabank.

Los parsers pueden contener extractores separados para datos de cuenta, resumen financiero, movimientos y otros productos.

### `src/models/`

Define los modelos de dominio y resultados de procesamiento, incluyendo:

- `EstadoCuenta`;
- datos de cuenta;
- resumen financiero;
- movimientos;
- otros productos;
- resultados de procesamiento.

### `src/validators/`

Contiene validaciones de consistencia entre datos extraídos y resumen financiero.

### `src/mappers/` y `src/exporters/`

Transforman el modelo de dominio a estructuras tabulares y formatos de salida. La salida principal actual es Excel.

### `vendor/tesseract/`

Contiene el runtime OCR utilizado por la distribución Windows. Se gestiona como componente de terceros sujeto a control de versión, procedencia, licencia, integridad y vulnerabilidades.

## 4. Flujo Digital/OCR

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
        parser base                parser OCR especializado
                                             │
                                      o normalizador +
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

El engine dispone de:

- procesamiento secuencial;
- procesamiento concurrente e incremental.

El flujo incremental separa la carga de clasificación, documentos digitales y OCR para evitar competencia excesiva entre operaciones intensivas.

## 6. Contrato funcional

Los siguientes elementos se consideran comportamiento crítico:

- institución detectada;
- método Digital/OCR;
- parser aplicado;
- datos de cuenta;
- resumen financiero;
- movimientos;
- referencias y claves de rastreo;
- matching SPEI;
- validaciones;
- estructura exportada.

Los cambios en estas áreas requieren regresión específica.

## 7. Integración web institucional

La arquitectura recomendada para despliegue web es:

```text
Usuario institucional
        │
        ▼
HTTPS
        │
        ▼
IIS / reverse proxy
        │
        ▼
Streamlit en interfaz local
        │
        ▼
Estado Cuenta Engine
```

La infraestructura de publicación, identidad, red y TLS queda fuera del motor.

## 8. Integración con SIEC

Cuando SIEC requiera consumo programático, debe incorporarse una capa API explícita sobre el engine.

```text
SIEC
 │
 ▼
API institucional
 │
 ▼
Estado Cuenta Engine
```

La API puede agregar autenticación, autorización, límites, trazabilidad y versionado sin modificar parsers ni modelos de extracción.

## 9. Fronteras de seguridad

Se distinguen al menos:

- documento de entrada;
- memoria/temporales de procesamiento;
- motor de extracción;
- salida autorizada;
- logs técnicos;
- capa de publicación;
- identidad institucional.

La arquitectura debe evitar que logs o temporales se conviertan en repositorios secundarios de información financiera.

## 10. Principios de mantenimiento

1. Preservar layouts soportados mediante regresión.
2. Mantener lógica bancaria dentro de componentes especializados.
3. Mantener OCR local salvo decisión institucional expresa.
4. Evitar persistencia implícita de documentos.
5. Mantener configuración operativa fuera del código.
6. Evaluar nuevas dependencias y terceros antes de liberación.
7. Documentar cambios de contrato y arquitectura.
