"""
Catálogo de Firmas Bancarias.

Este archivo centraliza el conocimiento estático sobre las
instituciones financieras que el motor puede identificar.

Cada banco tiene una entrada única que contiene:
- display_name: El nombre común del banco.
- clabe_prefixes: Lista de prefijos CLABE de 3 dígitos.
- rfcs: Lista de RFCs de la institución.
- keywords: Palabras clave únicas que aparecen en sus estados de cuenta.
"""

BANK_SIGNATURES = {
    "bbva": {
        "display_name": "BBVA México",
        "clabe_prefixes": ["012"],
        "rfcs": ["BBA830831LJ2"],
        "keywords": ["LIBRETON BASICO", "BBVA BANCOMER"],
    },
    "citibanamex": {
        "display_name": "Citibanamex",
        "clabe_prefixes": ["002"],
        "rfcs": ["BNM840515VB8", "BNM840515VB1"], 
        "keywords": ["MICUENTA", "BANCO NACIONAL DE MEXICO", "CITIBANAMEX"],
    },
    "santander": {
        "display_name": "Santander",
        "clabe_prefixes": ["014"],
        "rfcs": ["BSM970503DU8"],
        "keywords": ["SUPER CUENTA", "BANCO SANTANDER"],
    },
    "scotiabank": {
        "display_name": "Scotiabank",
        "clabe_prefixes": ["044"],
        "rfcs": ["SIN9412025I5", "SMB9411015R8"], 
        "keywords": ["SCOTIANOMINA", "INVERLAT"],
    },
    "hsbc": {
        "display_name": "HSBC México",
        "clabe_prefixes": ["021"],
        "rfcs": ["HMI950125KG8"],
        "keywords": ["HSBC MEXICO"],
    },
    "nu": {
        "display_name": "Nu México",
        "clabe_prefixes": ["638"],
        "rfcs": ["SAPI201015..."], # Ajustar si se requiere el RFC exacto
        "keywords": ["CUENTA NU", "STP"],
    },
    "afirme": {
        "display_name": "Banca Afirme",
        "clabe_prefixes": ["062"],
        "rfcs": ["BAF950102JP8"],
        "keywords": ["AFIRME", "BANCA AFIRME"],
    },
    "invex": {
        "display_name": "Banco Invex",
        "clabe_prefixes": ["059"],
        "rfcs": ["BIN9312131H0"],
        "keywords": ["INVEX", "BANCO INVEX"],
    }
}