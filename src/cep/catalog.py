"""Offline participant catalogue. Banxico CEP-SCL, verified 2026-11-09.

https://www.banxico.org.mx/cep-scl/listaInstituciones.do
CLABE's first three digits identify the institution, not a physical branch.
"""

import re

from utils.statement_dates import text_key


CATALOG_SOURCE_URL = "https://www.banxico.org.mx/cep-scl/listaInstituciones.do"
CATALOG_VERIFIED_ON = "2026-11-09"


INSTITUTIONS = {
    "40133": "ACTINVER", "40062": "AFIRME", "90721": "ALBO", "90660": "ALTOR",
    "90706": "ARCUS FI", "90659": "ASP INTEGRA OPC", "40127": "AZTECA",
    "37166": "BABIEN", "40030": "BAJIO", "40002": "BANAMEX",
    "40154": "BANCO COVALTO", "37006": "BANCOMEXT", "40137": "BANCOPPEL",
    "40160": "BANCO S3", "40152": "BANCREA", "37019": "BANJERCITO",
    "40147": "BANKAOOL", "40106": "BANK OF AMERICA", "40159": "BANK OF CHINA",
    "37009": "BANOBRAS", "40072": "BANORTE", "40058": "BANREGIO", "40060": "BANSI",
    "2001": "BANXICO", "40129": "BARCLAYS", "40145": "BBASE", "40012": "BBVA MEXICO",
    "40112": "BMONEX", "90677": "CAJA POP MEXICA", "90683": "CAJA TELEFONIST",
    "90715": "CASHI CUENTA", "40124": "CITI MEXICO", "90730": "CLIP",
    "90901": "CLS", "90903": "CODI VALIDA", "40130": "COMPARTAMOS",
    "40140": "CONSUBANCO", "90725": "COOPDESARROLLO", "90652": "CREDICAPITAL",
    "90688": "CREDICLUB", "90680": "CRISTOBAL COLON", "90723": "CUENCA",
    "90729": "DEP Y PAG DIG", "40151": "DONDE", "90616": "FINAMEX",
    "90634": "FINCOMUN", "90734": "FINCO PAY", "90738": "FINTOC",
    "90699": "FONDEADORA", "90685": "FONDO (FIRA)", "90601": "GBM",
    "40167": "HEY BANCO", "37168": "HIPOTECARIA FED", "40021": "HSBC",
    "40155": "ICBC", "40036": "INBURSA", "90902": "INDEVAL",
    "40150": "INMOBILIARIO", "40136": "INTERCAM BANCO", "40059": "INVEX",
    "40110": "JP MORGAN", "40128": "KAPITAL", "90661": "KLAR", "90653": "KUSPIT",
    "90670": "LIBERTAD", "90602": "MASARI", "90722": "MERCADO PAGO W",
    "90720": "MEXPAGO", "40042": "MIFEL", "40158": "MIZUHO BANK",
    "90600": "MONEXCB", "40108": "MUFG", "40132": "MULTIVA BANCO", "37135": "NAFIN",
    "40638": "NUBANK", "90710": "NVIO", "40148": "PAGATODO", "90732": "PEIBO",
    "90714": "PPBALANCEMX", "90620": "PROFUTURO", "40170": "REVOLUT BANK",
    "40156": "SABADELL", "40014": "SANTANDER", "40044": "SCOTIABANK",
    "40157": "SHINHAN", "90728": "SPIN BY OXXO", "90646": "STP",
    "90703": "TESORED", "90684": "TRANSFER", "90727": "TRANSFER DIRECT",
    "90631": "TRF", "40138": "UALA", "90656": "UNAGRA", "90617": "VALMEX",
    "90605": "VALUE", "40113": "VE POR MAS", "40141": "VOLKSWAGEN",
}
ALIASES = {name: code for code, name in INSTITUTIONS.items()}
ALIASES.update({
    "CITIBANAMEX": "40002", "BANCO NACIONAL DE MEXICO": "40002",
    "BBVA": "40012", "BANCOMER": "40012", "BBVA BANCOMER": "40012",
    "BANCO AZTECA": "40127", "HSBC MEXICO": "40021", "NU": "40638",
    "NU MEXICO": "40638", "MERCADO PAGO": "90722", "MERCADO_PAGO": "90722",
    "SCOTIA": "40044", "SCOTIABANK INVERLAT": "40044", "CETES": "37135",
    "BANORTE_OCR": "40072", "CETESDIRECTO": "37135",
    "CETES DIRECTO": "37135", "BANCO DEL BAJIO": "40030", "BANCA MIFEL": "40042",
})
CLABE_CODES = {code[-3:]: code for code in INSTITUTIONS}


def identifier(value: object) -> str:
    """Never accept an identifier already rounded by Excel's 15 digit limit."""
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, (int, float)):
        if not float(value).is_integer() or len(str(int(value))) > 15:
            return ""
        return str(int(value))
    result = re.sub(r"\s+", "", str(value)).strip().lstrip("'")
    if text_key(result) in {"N/A", "NA", "NONE", "NULL", "SINDATO", "SININFORMACION", "NOIDENTIFICADO"}:
        return ""
    return result


def valid_clabe(value: object) -> bool:
    s = account_identifier(value)
    if not re.fullmatch(r"[0-9]{18}", s):
        return False
    total = sum(int(c) * (3, 7, 1)[i % 3] % 10 for i, c in enumerate(s[:17]))
    return (10 - total % 10) % 10 == int(s[-1])


def bank_code(value: object) -> str:
    s = text_key(value)
    if s.isdigit():
        if s in INSTITUTIONS:
            return s
        if len(s) <= 3:
            return CLABE_CODES.get(s.zfill(3), "")
        return s.zfill(5) if s.zfill(5) in INSTITUTIONS else ""
    return ALIASES.get(s, "")


def clabe_bank(value: object) -> str:
    s = account_identifier(value)
    return CLABE_CODES.get(s[:3], "") if valid_clabe(s) else ""


def account_identifier(value: object) -> str:
    s = identifier(value)
    return s.replace("-", "") if re.fullmatch(r"[0-9]+(?:-[0-9]+)*", s) else s


def statement_account(value: object) -> str:
    value = account_identifier(value)
    return value if re.fullmatch(r"[0-9]{5,17}", value) or valid_clabe(value) else ""


def bank_mentions(text: str) -> set[str]:
    text = text_key(text)
    return {code for name, code in ALIASES.items()
            if re.search(r"(?<![A-Z0-9])" + re.escape(name) + r"(?![A-Z0-9])", text)}


def labelled_bank(text: str, role: str) -> str:
    """Resolve a stated SPEI participant, never a bank from a card's prefix."""
    text = re.sub(r"\s+", " ", text_key(text))
    label = (r"(?:EMISOR[AO]?|ORDENANTE|ORIGEN)" if role == "emisor"
             else r"(?:RECEPTOR[AO]?|BENEFICIARI[AO]|DESTINO)")
    patterns = [
        rf"\b(?:BANCO|INSTITUCION)\s+(?:DEL?\s+)?{label}\s*[:#=-]?\s*",
        r"\bRECIBIDO\s+DE\s+" if role == "emisor"
        else r"\b(?:ENVIADO|PAGO\s+INTERBANCARIO)\s+A\s+",
    ]
    options = set()
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            tail = text[match.end():match.end() + 50]
            number = re.match(r"([0-9]{3,5})\b", tail)
            if number and bank_code(number[1]):
                options.add(bank_code(number[1]))
            for name in sorted(ALIASES, key=len, reverse=True):
                if re.match(re.escape(name) + r"(?![A-Z0-9])", tail):
                    options.add(ALIASES[name])
                    break
    return next(iter(options)) if len(options) == 1 else ""
