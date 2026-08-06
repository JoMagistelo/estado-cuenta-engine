# Estado Cuenta Engine 🏦

Engine modular para la recepción, extracción, normalización y exportación automatizada de datos desde estados de cuenta bancarios en PDF.

---

## 📌 Visión General

El sistema automatiza el procesamiento documental bancario mediante una arquitectura extensible. Transforma documentos PDF no estructurados o semiestructurados en modelos de dominio unificados (`EstadoCuenta`), listos para exportarse a Excel o integrarse a bases de datos y pipelines analíticos.

---

## 🏗️ Arquitectura y Flujo de Procesamiento

```text
  [ PDF Bancario ]
         │
         ▼
[ Extracción & Normalización ]
         │
         ▼
[ Detector de Banco ] ──► [ Parser Especializado ] (BBVA, Banorte, etc.)
                                   │
                                   ▼
                       [ Modelo Unificado: EstadoCuenta ]
                                   │
                                   ▼
                      [ Exportación: Excel / BD / API ]