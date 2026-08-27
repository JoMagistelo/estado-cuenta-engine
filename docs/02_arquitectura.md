# Arquitectura del Proyecto

## Estado Cuenta Engine

Versión: 1.0

---

# Objetivo

Construir un motor de procesamiento capaz de convertir estados de cuenta bancarios mexicanos en un modelo unificado de datos, independientemente del banco emisor.

La arquitectura está diseñada para ser extensible, desacoplada y fácilmente mantenible.

Inicialmente el sistema procesará únicamente archivos PDF con texto (sin OCR).

---

# Filosofía

Cada módulo del sistema debe tener una única responsabilidad.

Cada carpeta representa una etapa específica del flujo de procesamiento.

El objetivo NO es crear un parser para un banco, sino un motor capaz de incorporar nuevos bancos mediante parsers especializados.

---

# Flujo General

```

          PDF

           │

           ▼

     pdf_parser

           │

           ▼

  text_normalizer

           │

           ▼

   bank_detector

           │

           ▼

   parser_factory

           │

           ▼

 Parser Especializado

           │

           ▼

    EstadoCuenta

           │

           ▼

 excel_exporter

```

---

# Arquitectura

```

src/

│

├── app/
│
│     Interfaz de usuario.

│

├── catalog/
│
│     Catálogos y conocimiento del sistema.

│

├── detectors/
│
│     Detectores automáticos.

│

├── engine/
│
│     Coordinador del procesamiento.

│

├── exporters/
│
│     Exportadores de información.

│

├── models/
│
│     Modelo unificado del dominio.

│

├── parsers/
│
│     Parsers específicos para cada banco.

│

└── utils/
      Utilidades reutilizables.

```

---

# Responsabilidad de cada carpeta

## app

Contiene únicamente la interfaz de usuario.

No contiene lógica bancaria.

No contiene expresiones regulares.

No contiene parsers.

Su única responsabilidad es interactuar con el usuario.

---

## catalog

Contiene información estática.

Ejemplo:

- Bancos
- CLABEs
- RFC institucional
- Palabras clave
- Productos conocidos

No contiene lógica.

---

## utils

Contiene funciones reutilizables.

Ejemplo:

- Leer PDF
- Normalizar texto
- CLABE
- Expresiones regulares
- Conversión de fechas

No conoce ningún banco.

---

## detectors

Su responsabilidad es detectar información.

Ejemplos:

- Detectar banco
- Detectar tipo de documento
- Detectar idioma

No extrae movimientos.

No genera modelos.

---

## parsers

Existe un parser por institución financiera.

Cada parser conoce únicamente la estructura documental de un banco.

Ejemplo

BBVAParser

SantanderParser

BanorteParser

Cada parser devuelve exactamente el mismo modelo:

EstadoCuenta

---

## models

Representan el dominio del negocio.

No conocen PDFs.

No conocen expresiones regulares.

No conocen Excel.

Únicamente representan información.

---

## engine

Coordina todo el proceso.

Es el cerebro del sistema.

Decide:

- qué parser utilizar
- cuándo ejecutar cada etapa
- qué objeto devolver

---

## exporters

Transforman un EstadoCuenta en otro formato.

Ejemplos

Excel

CSV

JSON

Base de Datos

---

# Principios de Diseño

Cada archivo responde únicamente una pregunta.

Cada módulo tiene una sola responsabilidad.

Los parsers nunca leen PDFs.

Los exportadores nunca detectan bancos.

Los modelos nunca contienen lógica de extracción.

Todo el sistema gira alrededor del modelo EstadoCuenta.

---

# Pipeline

Entrada

↓

PDF

↓

Texto

↓

Banco

↓

Parser

↓

Modelo

↓

Excel

---

# Objetivo Final

Agregar un nuevo banco debe consistir únicamente en crear un nuevo parser especializado.

El resto del sistema no debe modificarse.

Este principio garantiza escalabilidad y mantenibilidad.