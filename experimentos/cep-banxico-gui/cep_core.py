"""Preparador LOCAL de consultas CEP Banxico. Sin descarga automática ni evasión de CAPTCHA.
Dependencias: solo biblioteca estándar de Python 3.10+.
"""
from __future__ import annotations
import csv
import posixpath
import re
import unicodedata
import zipfile
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from html import unescape
from pathlib import Path
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

INDIVIDUAL = 'https://www.banxico.org.mx/cep/'
LOTES = 'https://www.banxico.org.mx/cep-scl/inicio.do'
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
      'p': 'http://schemas.openxmlformats.org/package/2006/relationships'}
BANCOS = {'BANAMEX':'40002','CITIBANAMEX':'40002','CITI MEXICO':'40124',
 'BBVA':'40012','BBVA MEXICO':'40012','BANCOMER':'40012',
 'BANORTE':'40072','SANTANDER':'40014','HSBC':'40021','SCOTIABANK':'40044',
 'BANCO AZTECA':'40127','AZTECA':'40127','BANCOPPEL':'40137',
 'INBURSA':'40036','BAJIO':'40030','AFIRME':'40062','BANREGIO':'40058',
 'MIFEL':'40042','STP':'90646','NVIO':'90710','NU':'40638','NUBANK':'40638'}
CLABE_BANCO = {'002':'40002','012':'40012','014':'40014','072':'40072',
 '021':'40021','044':'40044','127':'40127','137':'40137','036':'40036',
 '030':'40030','062':'40062','058':'40058','042':'40042','646':'90646'}
# Participantes oficiales adicionales, sin eliminar alias históricos de los parsers.
from banxico_catalogo import BANXICO_INSTITUCIONES, BANXICO_CLABE
BANCOS.update(BANXICO_INSTITUCIONES)
CLABE_BANCO.update(BANXICO_CLABE)

MESES = {'ENE':1,'FEB':2,'MAR':3,'ABR':4,'MAY':5,'JUN':6,'JUL':7,'AGO':8,
         'SEP':9,'SEPT':9,'OCT':10,'NOV':11,'DIC':12}
CAMPOS = ['fila_excel','id_estado','num_movimiento','tipo','fecha','clave_rastreo',
          'referencia','emisor','receptor','cuenta_beneficiaria','monto',
          'nombre_beneficiario','estado','observacion','linea_lote']


def normal(texto):
    s = unescape(str(texto or ''))
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = re.sub(r'<[^>]+>', ' ', s)
    return re.sub(r'\s+', ' ', s).upper().strip()


def clave(nombre):
    return re.sub(r'[^A-Z0-9]', '', normal(nombre))


def dato(row, col, nombre):
    j = col.get(clave(nombre))
    return row[j] if j is not None and j < len(row) else None


def id_texto(valor):
    if valor is None or isinstance(valor, bool):
        return ''
    if isinstance(valor, (int, float)):
        if not float(valor).is_integer():
            raise ValueError('identificador decimal inesperado')
        if len(str(int(valor))) > 15:
            raise ValueError('identificador numérico mayor a 15 dígitos: Excel pudo redondearlo')
        return str(int(valor))
    return re.sub(r'\s+', '', str(valor)).strip()


def dinero(valor):
    if valor is None or str(valor).strip() in ('', '-', '#######'):
        return Decimal('0')
    v = str(valor).replace('$', '').replace(',', '').replace(' ', '')
    try:
        d = Decimal(v)
        if not d.is_finite() or d < 0 or d != d.quantize(Decimal('0.01')):
            raise ValueError()
        return d
    except (InvalidOperation, ValueError):
        raise ValueError('importe inválido: ' + str(valor))


def clabe_valida(s):
    if not re.fullmatch(r'\d{18}', s or ''):
        return False
    total = sum(int(c) * (3, 7, 1)[i % 3] % 10 for i, c in enumerate(s[:17]))
    return (10 - total % 10) % 10 == int(s[17])


def fecha(valor):
    if isinstance(valor, (date, datetime)):
        return valor.date() if isinstance(valor, datetime) else valor
    if isinstance(valor, (int, float)) and 20000 < valor < 80000:
        return date(1899, 12, 30) + timedelta(days=int(valor))
    s = normal(valor).replace('.', '')
    for fmt in ('%Y-%m-%d','%d/%m/%Y','%d-%m-%Y','%d/%m/%y'):
        try: return datetime.strptime(s, fmt).date()
        except ValueError: pass
    # Cortes mal extraídos: 'AL 05/DIC/2025' o '05/ENE/2024 $...'
    m = re.search(r'(?<!\d)(\d{1,2})\s*[/ -]\s*([A-Z]{3,})\s*[/ -]\s*(20\d{2}|\d{2})(?!\d)', s)
    if m and m[2][:3] in MESES:
        y = int(m[3]); y += 2000 if y < 100 else 0
        return date(y, MESES[m[2][:3]], int(m[1]))
    raise ValueError('fecha no interpretable: ' + str(valor))


def fecha_operacion(valor, inicio, fin, nombre_archivo):
    try: return fecha(valor)
    except ValueError: pass
    m = re.fullmatch(r'(\d{1,2})\s*[/ -]?\s*([A-Z]{3,})', normal(valor))
    if not m or m[2][:3] not in MESES:
        raise ValueError('fecha de operación no identificada: ' + str(valor))
    dia, mes = int(m[1]), MESES[m[2][:3]]
    if inicio and fin and inicio <= fin:
        candidatos = []
        for y in (inicio.year-1, inicio.year, fin.year, fin.year+1):
            try: d = date(y, mes, dia)
            except ValueError: continue
            if inicio <= d <= fin and d not in candidatos: candidatos.append(d)
        if len(candidatos) == 1: return candidatos[0]
    if fin:
        candidatos = []
        for y in (fin.year, fin.year - 1):
            try: d = date(y, mes, dia)
            except ValueError: continue
            if 0 <= (fin - d).days <= 120: candidatos.append(d)
        if len(candidatos) == 1: return candidatos[0]
    periodo = re.search(r'(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\s*[_-]?\s*(20\d{2}|\d{2})', normal(nombre_archivo))
    if periodo:
        mes_fin = MESES[periodo[1]]; y = int(periodo[2]); y += 2000 if y < 100 else 0
        # Nombre de archivo identifica mes DE CORTE aproximado: sin intervalo fiable, no inventar el año.
        if mes == mes_fin: return date(y, mes, dia)
        if mes == (mes_fin - 2) % 12 + 1: return date(y - (mes_fin == 1), mes, dia)
    raise ValueError('no se puede determinar año de operación')


def nombres_bancos(texto, excluir=''):
    s = normal(texto)
    codigos = []
    for n in sorted(BANCOS, key=len, reverse=True):
        if re.search(r'(?<![A-Z])' + re.escape(n) + r'(?![A-Z])', s):
            c = BANCOS[n]
            if c != excluir and c not in codigos: codigos.append(c)
    return codigos


def detectar_cuenta(texto):
    s = normal(texto)
    m = re.search(r'(?:CTA\.?\s*BENEFICIARIO|CLABE\s*(?:DEL\s*)?BENEFICIARIO|CTA\.?\s*DESTINO)\s*[:\-]?\s*(\d{10}|\d{16}|\d{18})\b', s)
    return m[1] if m else ''


def extraer_clave(texto):
    m = re.search(r'\b(?:CLAVE\s+DE\s+RASTREO|RASTREO)\s*[:\-]?\s*([A-Z0-9\-]{8,40})\b', normal(texto))
    return m[1] if m else ''


def extraer_ref(texto):
    m = re.search(r'\bREF(?:ERENCIA)?\.?\s*[:\-]?\s*(\d{1,12})\b', normal(texto))
    return m[1] if m else ''


def xlsx_hojas(path):
    """Lee valores XLSX, conservando cadenas de identificadores; sin dependencias externas."""
    out = {}
    with zipfile.ZipFile(path) as z:
        shared = []
        if 'xl/sharedStrings.xml' in z.namelist():
            root = ET.fromstring(z.read('xl/sharedStrings.xml'))
            for item in root.findall('m:si', NS):
                shared.append(''.join(t.text or '' for t in item.findall('.//m:t', NS)))
        work = ET.fromstring(z.read('xl/workbook.xml'))
        relroot = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        rels = {r.attrib['Id']: r.attrib['Target'] for r in relroot}
        for node in work.findall('m:sheets/m:sheet', NS):
            name = node.attrib['name']
            rid = node.attrib['{' + NS['r'] + '}id']
            target = rels[rid]
            fn = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
            tree = ET.fromstring(z.read(fn))
            table = []
            for row in tree.findall('.//m:sheetData/m:row', NS):
                excel_row = int(row.attrib.get('r', len(table)+1))
                while len(table) < excel_row-1: table.append([])
                values = []
                for c in row.findall('m:c', NS):
                    ref = c.attrib.get('r', 'A1')
                    letters = re.match(r'[A-Z]+', ref)
                    if not letters: continue
                    idx = 0
                    for ch in letters[0]: idx = idx * 26 + ord(ch) - 64
                    idx -= 1
                    if idx > 250: continue
                    while len(values) <= idx: values.append(None)
                    t = c.attrib.get('t')
                    if t == 'inlineStr':
                        values[idx] = ''.join(n.text or '' for n in c.findall('.//m:t', NS))
                    else:
                        v = c.find('m:v', NS)
                        if v is None: continue
                        raw = v.text or ''
                        if t == 's': values[idx] = shared[int(raw)]
                        elif t == 'b': values[idx] = raw == '1'
                        elif t in ('str', 'e'): values[idx] = raw
                        else:
                            try:
                                num = Decimal(raw)
                                values[idx] = int(num) if num == num.to_integral_value() else float(num)
                            except InvalidOperation: values[idx] = raw
                table.append(values)
            out[name] = table
    return out


def csv_hoja(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        sample = f.read(4096); f.seek(0)
        try: dialect = csv.Sniffer().sniff(sample, delimiters=',;\t')
        except csv.Error: dialect = csv.excel
        return {'Movimientos': list(csv.reader(f, dialect))}


def metadata(hojas):
    res = {}
    for nombre, tabla in hojas.items():
        if clave(nombre) != 'DATOSDELACUENTA' or not tabla: continue
        cols = {clave(h):i for i,h in enumerate(tabla[0])}
        for r in tabla[1:]:
            idx = str(dato(r, cols, 'id_estado') or '').strip()
            if not idx: continue
            def safe_date(label):
                try: return fecha(dato(r, cols, label))
                except (ValueError, TypeError): return None
            cuentas = []
            for campo in ('CLABE','Número de Cuenta'):
                try: v = id_texto(dato(r, cols, campo))
                except ValueError: continue
                if clabe_valida(v): cuentas.append(v)
            res[idx] = {'clabe':cuentas[0] if cuentas else '',
                        'inicio':safe_date('Periodo de Inicio'),
                        'fin':safe_date('Periodo de Fin') or safe_date('Fecha de Corte')}
    return res


def preparar(row, cols, fila, meta, clabe_manual=''):
    get = lambda n: dato(row, cols, n)
    texto = str(get('Concepto') or get('Concepto Original') or '')
    t = normal(texto + ' ' + str(get('Concepto Original') or ''))
    try: rastreo = id_texto(get('Clave de Rastreo')) or extraer_clave(t)
    except ValueError: rastreo = ''
    try: referencia = id_texto(get('Referencia')) or extraer_ref(t)
    except ValueError: referencia = extraer_ref(t)
    # Tipo de operación deliberadamente NO interviene: lo genera Estado Cuenta Engine o el analista.
    senales = bool(rastreo or re.search(r'\bSPEI\b|INTERBANCARI|\bRASTREO\b', t))
    if not senales: return None
    idx = str(get('id_estado') or '')
    x = dict.fromkeys(CAMPOS, '')
    x.update(fila_excel=str(fila), id_estado=idx,
             num_movimiento=str(get('No. de Movimiento') or ''),
             clave_rastreo=rastreo, referencia=referencia,
             nombre_beneficiario=str(get('Beneficiario') or ''), estado='PENDIENTE')
    problemas = []
    try:
        c, a = dinero(get('Cargo')), dinero(get('Abono'))
        if bool(c) == bool(a): raise ValueError('cargo/abono ambiguos')
        enviado = c > 0
        x['tipo'] = 'ENVIADO' if enviado else 'RECIBIDO'
        x['monto'] = f'{c if enviado else a:.2f}'
    except ValueError as e:
        enviado = None; problemas.append(str(e))
    info = meta.get(idx, {})
    try:
        fin = info.get('fin')
        if not fin:
            try: fin = fecha(get('Fecha de Corte'))
            except ValueError: pass
        x['fecha'] = fecha_operacion(get('Fecha de Operación'), info.get('inicio'), fin, str(get('Nombre del Archivo') or '')) .isoformat()
    except (ValueError, TypeError) as e: problemas.append(str(e))
    banco_estado = BANCOS.get(normal(get('Banco')))
    if not banco_estado: problemas.append('banco del estado no identificado')
    if enviado is True:
        x['emisor'] = banco_estado or ''
        try:
            cuenta = id_texto(get('CLABE del Beneficiario')) or id_texto(get('Cuenta del Beneficiario')) or detectar_cuenta(t)
            if cuenta and not re.fullmatch(r'\d{10}|\d{16}|\d{18}', cuenta):
                raise ValueError('cuenta de tercero con longitud inválida')
            x['cuenta_beneficiaria'] = cuenta
            if not cuenta: problemas.append('falta cuenta de destino')
        except ValueError as e: problemas.append(str(e))
        posibles = nombres_bancos(t, banco_estado)
        if len(posibles) == 1: x['receptor'] = posibles[0]
        elif len(posibles) > 1: problemas.append('banco destino ambiguo')
        else:
            prefijo = CLABE_BANCO.get(x['cuenta_beneficiaria'][:3]) if len(x['cuenta_beneficiaria']) == 18 else None
            if prefijo: x['receptor'] = prefijo
            else: problemas.append('banco destino desconocido')
        if len(x['cuenta_beneficiaria']) == 18:
            if not clabe_valida(x['cuenta_beneficiaria']): problemas.append('CLABE destino falla dígito verificador')
            if CLABE_BANCO.get(x['cuenta_beneficiaria'][:3]) not in (None, x['receptor']):
                problemas.append('CLABE destino contradice banco receptor')
    elif enviado is False:
        x['receptor'] = banco_estado or ''
        propia = info.get('clabe', '') or clabe_manual
        x['cuenta_beneficiaria'] = propia
        if not clabe_valida(propia): problemas.append('SPEI recibido: falta CLABE propia válida (Datos de la Cuenta o campo manual)')
        if propia and CLABE_BANCO.get(propia[:3]) not in (None, banco_estado):
            problemas.append('CLABE propia contradice banco receptor')
        posibles = nombres_bancos(t, banco_estado)
        if len(posibles) == 1: x['emisor'] = posibles[0]
        else: problemas.append('SPEI recibido: banco emisor no identificado inequívocamente')
    if not rastreo: problemas.append('sin clave de rastreo; usar referencia en consulta individual')
    if rastreo and not re.fullmatch(r'[A-Z0-9-]{8,40}', rastreo.upper()):
        problemas.append('formato de rastreo inválido')
    if x['emisor'] and x['emisor'] == x['receptor']: problemas.append('bancos emisor/receptor iguales')
    obligatorios = ('fecha','clave_rastreo','emisor','receptor','cuenta_beneficiaria','monto')
    # Distinguir un dato no corroborado de uno materialmente inválido.
    # Para no rechazar todo un lote, jamás fabricar campos ausentes o CLABE incorrecta.
    fatales = (
        'cargo/abono ambiguos', 'CLABE destino falla dígito verificador',
        'CLABE destino contradice banco receptor',
        'CLABE propia contradice banco receptor',
        'bancos emisor/receptor iguales', 'cuenta de tercero con longitud inválida',
        'formato de rastreo inválido',
    )
    completos = all(x[k] for k in obligatorios)
    formato_ok = bool(
        completos and re.fullmatch(r'20\\d{2}-\\d{2}-\\d{2}', x['fecha'])
        and re.fullmatch(r'[A-Za-z0-9-]{8,40}', x['clave_rastreo'])
        and re.fullmatch(r'\\d{5}', x['emisor'])
        and re.fullmatch(r'\\d{5}', x['receptor'])
        and re.fullmatch(r'\\d{10}|\\d{16}|\\d{18}', x['cuenta_beneficiaria'])
        and Decimal(x['monto']) > 0
    )
    if formato_ok and not any(p.startswith(f) for f in fatales for p in problemas):
        x['linea_lote'] = ','.join(x[k] for k in obligatorios)
        x['estado'] = 'LISTO' if not problemas else 'LISTO_CON_ALERTAS'
        x['observacion'] = '; '.join(dict.fromkeys(problemas)) if problemas else 'Datos suficientes para solicitar CEP; no confirmado'
    else:
        x['observacion'] = '; '.join(dict.fromkeys(problemas)) or 'No tiene los seis datos válidos para lote'
    return x


def analizar(path, clabe_manual=''):
    path = Path(path)
    if path.suffix.lower() not in ('.xlsx', '.csv'):
        raise ValueError('Se acepta .xlsx o .csv (no .xls)')
    if clabe_manual and not clabe_valida(clabe_manual):
        raise ValueError('CLABE manual no válida; verifica los 18 dígitos')
    hojas = csv_hoja(path) if path.suffix.lower() == '.csv' else xlsx_hojas(path)
    met = metadata(hojas)
    registros = []
    movimiento_total = 0
    for nombre, tabla in hojas.items():
        if clave(nombre) != 'MOVIMIENTOS' or not tabla: continue
        col = {clave(c):i for i,c in enumerate(tabla[0]) if c is not None}
        if not all(clave(k) in col for k in ('Fecha de Operación','Cargo','Abono')):
            raise ValueError('La hoja Movimientos no contiene Fecha de Operación, Cargo y Abono')
        for numero, row in enumerate(tabla[1:], 2):
            if not any(v not in (None, '') for v in row): continue
            movimiento_total += 1
            try: r = preparar(row, col, numero, met, clabe_manual)
            except ValueError as e:
                r = dict.fromkeys(CAMPOS, '')
                r.update(fila_excel=str(numero), estado='PENDIENTE', observacion=str(e))
            if r: registros.append(r)
    if movimiento_total == 0: raise ValueError('No se encontraron movimientos en el archivo')
    return registros, movimiento_total


def exportar(registros, carpeta):
    """Salida mínima: un XLSX de trabajo y un TXT por lote (500 registros máximo)."""
    from cep_importador import crear_excel_sin_dependencias
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    validos = [r for r in registros if r.get('linea_lote')]
    # Los incompletos se CONSERVAN en la hoja SPEI, pero no se envían con datos falsos.
    lotes = []
    if len(validos) > 1:
        i = 0
        while i < len(validos):
            restantes = len(validos) - i
            tam = 499 if restantes == 501 else min(restantes, 500)
            if tam < 2:
                raise ValueError('No es posible formar un lote de al menos dos SPEI')
            grupo = validos[i:i+tam]
            i += tam
            fn = carpeta / f'lote_{len(lotes)+1:03d}.txt'
            fn.write_text('\\n'.join(r['linea_lote'] for r in grupo) + '\\n', encoding='utf-8')
            lotes.append(fn)
    registros_excel = []
    for reg in registros:
        dato = dict(reg)
        if reg.get('linea_lote') and lotes:
            dato['resultado_cep'] = 'PENDIENTE_BANXICO'
            dato['resultado_detalle'] = 'Preparado en TXT; todavía no se confirmó la consulta'
        elif reg.get('linea_lote'):
            dato['resultado_cep'] = 'SIN_LOTE'
            dato['resultado_detalle'] = 'Banxico solicita al menos 2 operaciones por lote'
        else:
            dato['resultado_cep'] = 'NO_CONSULTABLE'
            dato['resultado_detalle'] = reg.get('observacion', '')
        dato['tiene_pdf'] = 'NO'
        registros_excel.append(dato)
    resumen = {
        'SPEI candidatos':len(registros),
        'Preparados en TXT':sum(len(p.read_text(encoding='utf-8').splitlines()) for p in lotes),
        'No consultables':len(registros)-len(validos),
        'Lotes TXT':len(lotes),
        'CEP descargados':0,
    }
    # Un XLSX; no se producen CSV de individuales ni pendientes.
    crear_excel_sin_dependencias(carpeta/'resultado_CEP.xlsx', resumen, [], [], registros=registros_excel)
    return {'total':len(registros), 'listos':len(validos), 'pendientes':len(registros)-len(validos),
            'lotes':len(lotes), 'salida':str(carpeta), 'excel':str(carpeta/'resultado_CEP.xlsx')}


def diagnostico_web():
    reporte = []
    for url in (INDIVIDUAL, LOTES):
        try:
            req = Request(url, headers={'User-Agent':'Mozilla/5.0 (CEP piloto diagnóstico)'})
            with urlopen(req, timeout=15) as resp:
                texto = resp.read(200000).decode('utf-8', 'replace')
                reporte.append(f'{url} : HTTP {resp.status}, captcha HTML={"captcha" in texto.lower()}')
        except Exception as e:
            reporte.append(f'{url} : FALLÓ {type(e).__name__}: {e}')
    return '\n'.join(reporte) + '\nEl diagnóstico no descarga CEP ni prueba autorización para automatizar.'
