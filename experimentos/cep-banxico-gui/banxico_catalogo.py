"""Catálogo inicial de instituciones participantes CEP-SCL (Banxico).
Fuente pública: https://www.banxico.org.mx/cep-scl/listaInstituciones.do
La denominación del estado bancario puede variar: ampliar alias según layouts probados.
"""
BANXICO_INSTITUCIONES = {
    'ACTINVER':'40133','AFIRME':'40062','ALBO':'90721','ALTOR':'90660',
    'ARCUS FI':'90706','ASP INTEGRA OPC':'90659','AZTECA':'40127',
    'BABIEN':'37166','BANCOMEXT':'37006','BANCO COVALTO':'40154',
    'BANCOPPEL':'40137','BANCO S3':'40160','BANCREA':'40152',
    'BANJERCITO':'37019','BANKAOOL':'40147','BANOBRAS':'37009',
    'BANORTE':'40072','BANREGIO':'40058','BANSI':'40060',
    'BARCLAYS':'40129','BBASE':'40145','BBVA MEXICO':'40012',
    'BMONEX':'40112','CAJA POP MEXICA':'90677','CAJA TELEFONIST':'90683',
    'CASHI CUENTA':'90715','CITI MEXICO':'40124','CLIP':'90730',
    'COOPDESARROLLO':'90725','COMPARTAMOS':'40130','CONSUBANCO':'40140',
    'CREDICAPITAL':'90652','CREDICLUB':'90688','CRISTOBAL COLON':'90680',
    'CUENCA':'90723','DONDE':'40151','FINAMEX':'90616',
    'FINCOMUN':'90634','FINCO PAY':'90734','FINTOC':'90738',
    'FONDEADORA':'90699','FONDO (FIRA)':'90685','GBM':'90601',
    'HEY BANCO':'40167','HSBC':'40021','ICBC':'40155',
    'INBURSA':'40036','INDEVAL':'90902','INMOBILIARIO':'40150',
    'INTERCAM BANCO':'40136','INVEX':'40059','JP MORGAN':'40110',
    'KAPITAL':'40128','KLAR':'90661','KUSPIT':'90653',
    'LIBERTAD':'90670','MASARI':'90602','MERCADO PAGO W':'90722',
    'MEXPAGO':'90720','MIFEL':'40042','MIZUHO BANK':'40158',
    'MONEXCB':'90600','MUFG':'40108','MULTIVA BANCO':'40132',
    'NAFIN':'37135','NUBANK':'40638','NVIO':'90710',
    'PAGATODO':'40148','PEIBO':'90732','PPBALANCEMX':'90714',
    'PROFUTURO':'90620','REVOLUT BANK':'40170','SABADELL':'40156',
    'SANTANDER':'40014','SCOTIABANK':'40044','SHINHAN':'40157',
    'SPIN BY OXXO':'90728','STP':'90646','TESORED':'90703',
    'TRANSFER':'90684','TRANSFER DIRECT':'90727','TRF':'90631',
    'UALA':'40138','UNAGRA':'90656','VALMEX':'90617',
    'VALUE':'90605','VE POR MAS':'40113','VOLKSWAGEN':'40141',
    'BANAMEX':'40002','BANCO AZTECA':'40127',
    'BANCO DEL BAJIO':'40030','BAJIO':'40030',
}
# CLABE uses a bank key that is typically the last three digits of participant ID.
# Only infer from a 5-digit code and if no conflicting identifier is found.
BANXICO_CLABE = {}
for name, codigo in BANXICO_INSTITUCIONES.items():
    if len(codigo)!=5: continue
    pref = codigo[-3:]
    if pref in BANXICO_CLABE and BANXICO_CLABE[pref] != codigo:
        BANXICO_CLABE.pop(pref, None)
    else:
        BANXICO_CLABE[pref]=codigo
