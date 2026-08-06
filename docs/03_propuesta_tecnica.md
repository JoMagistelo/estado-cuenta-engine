# Propuesta Técnica: Motor de Procesamiento de Estados de Cuenta

Documento ejecutivo de arquitectura, avance actual y visión de evolución del sistema.

---

## 1. Resumen Ejecutivo

El **Motor de Procesamiento de Estados de Cuenta** es una plataforma diseñada para automatizar la recepción, análisis y transformación de estados de cuenta bancarios en formato PDF hacia información estructurada, auditable y reutilizable.

La solución permite procesar documentos de diferentes instituciones financieras mediante una arquitectura modular donde cada banco cuenta con reglas especializadas sin afectar el funcionamiento general del sistema.

---

## 2. Flujo General del Sistema

| Etapa | Módulo | Descripción Funcional |
| :---: | :--- | :--- |
| **1** | **PDF Bancario** | Documento original recibido (procesamiento individual o batch). |
| **2** | **Extracción** | Obtención del texto crudo y estructura del documento PDF. |
| **3** | **Normalización** | Limpieza, sanitizado y preparación estandarizada del texto. |
| **4** | **Detector Bancario** | Identificación automática de la institución emisora. |
| **5** | **Parser Especializado** | Extracción según formato y reglas específicas del banco. |
| **6** | **Modelo Unificado** | Estructuración en el modelo estándar de dominio (`EstadoCuenta`). |
| **7** | **Exportación** | Generación de archivos Excel, integración a bases de datos y reportes. |

---

## 3. Arquitectura del Sistema

```text
                     [ ESTADOS DE CUENTA PDF ]
                                │
                                ▼
                   [ Motor de Procesamiento ]
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
   [Detectores]            [Extractores]            [Parsers]
                                │
                                ▼
                   [ Modelo: EstadoCuenta ]
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
  [DatosCuenta]        [ResumenFinanciero]        [Movimientos]
                                │
                                ▼
                  [ Exportador Excel / BD / API ]