"""Firmas estáticas utilizadas para identificar instituciones financieras.

Cada entrada mantiene señales de identificación independientes del layout del
estado de cuenta. Los identificadores no verificados deben omitirse en lugar de
representarse mediante valores parciales o de ejemplo.
"""

BANK_SIGNATURES = {
    "bbva": {
        "display_name": "BBVA México",
        "clabe_prefixes": ["012"],
        "rfcs": ["BBA830831LJ2"],
        "keywords": ["LIBRETON BASICO", "BBVA BANCOMER"],
        "filename_keywords": ["BBVA", "BANCOMER"],
    },
    "banamex": {
        "display_name": "Citibanamex",
        "clabe_prefixes": ["002"],
        "rfcs": ["BNM840515VB8", "BNM840515VB1"],
        "keywords": ["MICUENTA", "BANCO NACIONAL DE MEXICO", "CITIBANAMEX"],
        "filename_keywords": ["BANAMEX", "CITIBANAMEX", "CITIBANK"],
    },
    "santander": {
        "display_name": "Santander",
        "clabe_prefixes": ["014"],
        "rfcs": ["BSM970503DU8"],
        "keywords": ["SUPER CUENTA", "BANCO SANTANDER"],
        "filename_keywords": ["SANTANDER"],
    },
    "banorte": {
        "display_name": "Banorte",
        "clabe_prefixes": ["072"],
        "rfcs": [],
        "keywords": ["BANORTE", "BANCO MERCANTIL DEL NORTE"],
        "filename_keywords": ["BANORTE", "MERCANTIL DEL NORTE"],
    },
    "scotiabank": {
        "display_name": "Scotiabank",
        "clabe_prefixes": ["044"],
        "rfcs": ["SIN9412025I5", "SMB9411015R8"],
        "keywords": ["SCOTIANOMINA", "INVERLAT"],
        "filename_keywords": ["SCOTIABANK", "SCOTIA", "SCOTIANOMINA"],
    },
    "hsbc": {
        "display_name": "HSBC México",
        "clabe_prefixes": ["021"],
        "rfcs": ["HMI950125KG8"],
        "keywords": ["HSBC MEXICO"],
        "filename_keywords": ["HSBC"],
    },
    "nu": {
        "display_name": "Nu México",
        "clabe_prefixes": ["638"],
        "rfcs": [],
        "keywords": ["CUENTA NU", "STP"],
        "filename_keywords": ["NU", "NUBANK"],
    },
    "afirme": {
        "display_name": "Banca Afirme",
        "clabe_prefixes": ["062"],
        "rfcs": ["BAF950102JP8"],
        "keywords": ["AFIRME", "BANCA AFIRME"],
        "filename_keywords": ["AFIRME", "BANCA AFIRME"],
    },
    "mifel": {
        "display_name": "Mifel",
        "clabe_prefixes": ["042"],
        "rfcs": [],
        "keywords": ["MIFEL", "FIRMA ELECTRONICA"],
        "filename_keywords": ["MIFEL", "FIRMA"],
    },
    "mercado_pago": {
        "display_name": "Mercado Pago",
        "clabe_prefixes": ["722"],
        "rfcs": ["MAG2105031W3"],
        "keywords": ["MERCADO PAGO", "MP AGREGADOR"],
        "filename_keywords": ["MERCADO PAGO", "MERCADOPAGO"],
    },
    "cetes": {
        "display_name": "Cetes Directo",
        "clabe_prefixes": ["111"],
        "rfcs": ["NFI3407024T2"],
        "keywords": ["CETESDIRECTO", "NACIONAL FINANCIERA", "NAFINSA", "BONDDIA", "CETES"],
        "filename_keywords": ["CETES", "CETESDIRECTO", "NAFIN"],
    },
    "invex": {
        "display_name": "Banco Invex",
        "clabe_prefixes": ["059"],
        "rfcs": ["BIN9312131H0"],
        "keywords": ["INVEX", "BANCO INVEX"],
        "filename_keywords": ["INVEX", "BANCO INVEX"],
    },
}
