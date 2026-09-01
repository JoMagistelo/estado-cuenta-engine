"""
Catálogo de Firmas Bancarias.

Este archivo centraliza el conocimiento estático sobre las
instituciones financieras que el motor puede identificar.

Cada banco tiene una entrada única que contiene:
- display_name: Nombre común del banco.
- clabe_prefixes: Lista de prefijos CLABE de 3 dígitos.
- rfcs: Lista de RFCs de la institución.
- keywords: Palabras clave que pueden aparecer dentro del estado de cuenta.
- filename_keywords: Palabras clave que pueden aparecer en el nombre del archivo.
"""

BANK_SIGNATURES = {
    "bbva": {
        "display_name": "BBVA México",
        "clabe_prefixes": ["012"],
        "rfcs": ["BBA830831LJ2"],
        "keywords": [
            "LIBRETON BASICO",
            "BBVA BANCOMER",
        ],
        "filename_keywords": [
            "BBVA",
            "BANCOMER",
        ],
    },

    "banamex": {
        "display_name": "Citibanamex",
        "clabe_prefixes": ["002"],
        "rfcs": [
            "BNM840515VB8",
            "BNM840515VB1",
        ],
        "keywords": [
            "MICUENTA",
            "BANCO NACIONAL DE MEXICO",
            "CITIBANAMEX",
        ],
        "filename_keywords": [
            "BANAMEX",
            "CITIBANAMEX",
            "CITIBANK",
        ],
    },

    "santander": {
        "display_name": "Santander",
        "clabe_prefixes": ["014"],
        "rfcs": ["BSM970503DU8"],
        "keywords": [
            "SUPER CUENTA",
            "BANCO SANTANDER",
        ],
        "filename_keywords": [
            "SANTANDER",
        ],
    },

    "banorte": {
        "display_name": "Banorte",
        "clabe_prefixes": ["072"],
        "rfcs": [],
        "keywords": [
            "BANORTE",
            "BANCO MERCANTIL DEL NORTE",
        ],
        "filename_keywords": [
            "BANORTE",
            "MERCANTIL DEL NORTE",
        ],
    },

    "scotiabank": {
        "display_name": "Scotiabank",
        "clabe_prefixes": ["044"],
        "rfcs": [
            "SIN9412025I5",
            "SMB9411015R8",
        ],
        "keywords": [
            "SCOTIANOMINA",
            "INVERLAT",
        ],
        "filename_keywords": [
            "SCOTIABANK",
            "SCOTIA",
            "SCOTIANOMINA",
        ],
    },

    "hsbc": {
        "display_name": "HSBC México",
        "clabe_prefixes": ["021"],
        "rfcs": ["HMI950125KG8"],
        "keywords": [
            "HSBC MEXICO",
        ],
        "filename_keywords": [
            "HSBC",
        ],
    },

    "nu": {
        "display_name": "Nu México",
        "clabe_prefixes": ["638"],
        "rfcs": [
            "SAPI201015...",
        ],
        "keywords": [
            "CUENTA NU",
            "STP",
        ],
        "filename_keywords": [
            "NU",
            "NUBANK",
        ],
    },

    "afirme": {
        "display_name": "Banca Afirme",
        "clabe_prefixes": ["062"],
        "rfcs": ["BAF950102JP8"],
        "keywords": [
            "AFIRME",
            "BANCA AFIRME",
        ],
        "filename_keywords": [
            "AFIRME",
            "BANCA AFIRME",
        ],
    },

    "mifel": {
            "display_name": "Mifel",
            "clabe_prefixes": [], # No aplica por ser plataforma de firma
            "rfcs": [], # Se omite o se puede agregar el RFC corporativo si se requiere
            "keywords": [
                "MIFEL",
                "FIRMA ELECTRONICA",
            ],
            "filename_keywords": [
                "MIFEL",
                "FIRMA",
            ],
        },

    "cetes": {
        "display_name": "Cetes Directo",
        "clabe_prefixes": ["111"], # NAFIN (Nacional Financiera)
        "rfcs": [
            "NFI3407024T2", # Nacional Financiera S.N.C.
        ],
        "keywords": [
            "CETESDIRECTO",
            "NACIONAL FINANCIERA",
            "NAFINSA",
            "BONDDIA",
            "CETES",
        ],
        "filename_keywords": [
            "CETES",
            "CETESDIRECTO",
            "NAFIN",
        ],
    },

    "invex": {
        "display_name": "Banco Invex",
        "clabe_prefixes": ["059"],
        "rfcs": ["BIN9312131H0"],
        "keywords": [
            "INVEX",
            "BANCO INVEX",
        ],
        "filename_keywords": [
            "INVEX",
            "BANCO INVEX",
        ],
    },
}