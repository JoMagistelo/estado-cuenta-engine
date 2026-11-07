"""Importador local de resultados CEP de Banxico: ZIP -> PDFs/XML renombrados y XLSX.

No solicita transferencias ni elude controles del sitio. Las coincidencias son conservadoras:
solo se vincula el XML a un movimiento si su rastreo es único y concuerda con los
otros campos disponibles. No constituye validación criptográfica del sello CEP.
"""
from __future__ import annotations

import csv
import io
import re
import shutil
import unicodedata
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape as xml_escape

MAX_ARCHIVOS = 1600
MAX_ARCHIVO = 12 * 1024 * 1024
MAX_TOTAL = 150 * 1024 * 1024

CAMPOS_XML = {
    'nombre_beneficiario': ['nombrebeneficiario', 'nombeneficiario', 'nombrebene', 'beneficiario.nombre', 'datosbeneficiario.nombre', 'beneficiario.nombrecompleto'],
    'nombre_ordenante': ['nombreordenante', 'nomordenante', 'ordenante.nombre', 'datosordenante.nombre', 'ordenante.nombrecompleto'],
    'rfc_beneficiario': ['rfcbeneficiario', 'rfcobeneneficiario', 'beneficiario.rfc', 'datosbeneficiario.rfc', 'beneficiario.curp'],
    'rfc_ordenante': ['rfcordenante', 'ordenante.rfc', 'datosordenante.rfc', 'ordenante.curp'],
    'cuenta_beneficiaria': ['cuentabeneficiaria', 'clabebeneficiaria', 'cuentabene', 'beneficiario.cuenta', 'beneficiario.clabe', 'beneficiario.cuentabeneficiaria'],
    'cuenta_ordenante': ['cuentaordenante', 'clabeordenante', 'ordenante.cuenta', 'ordenante.clabe'],
    'rastreo': ['claverastreo', 'clavederastreo', 'rastreo', 'numerorastreo'],
    'referencia': ['referencianumerica', 'numeroreferencia', 'referencia'],
    'fecha': ['fechaoperacion', 'fechapago', 'fechadeoperacion', 'fechatransferencia'],
    'monto': ['monto', 'importe', 'montopago', 'montooperacion', 'importepago'],
    'concepto': ['conceptopago', 'concepto', 'conceptodelpago'],
    'emisor': ['institucionemisora', 'bancoemisor', 'institucionordenante', 'bancoordenante'],
    'receptor': ['institucionreceptora', 'bancoreceptor', 'bancobeneficiario'],
}
# Datos CEP: sólo valores del XML oficial, más indicadores documentales.
COLUMNAS = [
    'nombre_beneficiario_cep', 'rfc_beneficiario_cep',
    'nombre_ordenante_cep', 'rfc_ordenante_cep',
    'cuenta_beneficiaria_cep', 'cuenta_ordenante_cep',
    'banco_emisor_cep', 'banco_receptor_cep', 'fecha_cep', 'monto_cep',
    'clave_rastreo_cep', 'referencia_cep', 'concepto_cep',
    'tiene_pdf', 'archivo_pdf', 'archivo_xml',
]
# Bitácora única: candidatos SPEI originales y estado real de la consulta.
SPEI_COLUMNAS = [
    'fila_excel', 'id_estado', 'num_movimiento', 'tipo', 'fecha', 'monto',
    'clave_rastreo', 'referencia', 'emisor', 'receptor', 'cuenta_beneficiaria',
    'nombre_beneficiario', 'estado', 'observacion',
    'resultado_cep', 'resultado_detalle', 'fecha_cep_encontrada',
    'diferencia_dias_fecha', 'tiene_pdf', 'archivo_pdf',
    'archivo_xml', 'linea_lote',
]



def _normal(v):
    s = unicodedata.normalize('NFKD', str(v or ''))
    return ''.join(ch for ch in s if not unicodedata.combining(ch)).upper().strip()


def _key(v):
    return re.sub(r'[^a-z0-9]', '', _normal(v).lower())


def _local(q):
    return str(q).rsplit('}', 1)[-1].split(':')[-1]


def _texto(v):
    return re.sub(r'\s+', ' ', str(v or '')).strip()


def _fecha(v):
    s = _texto(v)
    m = re.search(r'(20\d{2})[-/](\d{2})[-/](\d{2})', s)
    if m:
        try: return datetime(int(m[1]), int(m[2]), int(m[3])).strftime('%Y-%m-%d')
        except ValueError: pass
    m = re.search(r'(\d{2})[-/](\d{2})[-/](20\d{2})', s)
    if m:
        try: return datetime(int(m[3]), int(m[2]), int(m[1])).strftime('%Y-%m-%d')
        except ValueError: pass
    return ''


def _dinero(v):
    try: return Decimal(str(v).replace('$', '').replace(',', '').strip())
    except (InvalidOperation, ValueError): return None


def datos_cep_xml(contenido):
    """Extrae datos en atributos, elementos simples o hijos de Ordenante/Beneficiario."""
    if len(contenido) > MAX_ARCHIVO: raise ValueError('XML demasiado grande')
    raiz = ET.fromstring(contenido)
    valores = defaultdict(list)

    def visitar(nodo, contexto=''):
        etiqueta = _key(_local(nodo.tag))
        actual = f'{contexto}.{etiqueta}' if contexto else etiqueta
        if nodo.text and nodo.text.strip() and len(nodo) == 0:
            t = _texto(nodo.text)
            valores[etiqueta].append(t)
            valores[actual].append(t)
        for k, v in nodo.attrib.items():
            key = _key(_local(k))
            valor = _texto(v)
            valores[key].append(valor)
            valores[actual + '.' + key].append(valor)
            valores[etiqueta + '.' + key].append(valor)
        for hijo in nodo: visitar(hijo, actual)
    visitar(raiz)

    def obtener(nombres):
        # First exact context path, then suffix path for namespaced wrappers
        for nombre in nombres:
            k = '.'.join(_key(p) for p in nombre.split('.'))
            if valores.get(k): return valores[k][0]
        for nombre in nombres:
            k = '.'.join(_key(p) for p in nombre.split('.'))
            for path, vs in valores.items():
                if path.endswith('.' + k) and vs: return vs[0]
        return ''

    datos = {k: obtener(names) for k, names in CAMPOS_XML.items()}
    datos['fecha'] = _fecha(datos['fecha'])
    return datos


def _seguro_nombre(v):
    v = _normal(v).replace('/', ' ').replace('\\', ' ')
    v = re.sub(r'[^A-Z0-9 _.-]', '', v)
    v = re.sub(r'[ _]+', '_', v).strip('._ ')
    return v[:62] or 'SIN_NOMBRE_XML'


def _identificador(s):
    return re.sub(r'[^A-Z0-9]', '', _normal(s))


def _xlsx_xml_escape(s):
    # Remove XML 1.0 forbidden control characters.
    return xml_escape(''.join(c for c in str(s) if c in '\t\n\r' or ord(c) >= 32))


def _col_name(i):
    r = ''
    while i:
        i, d = divmod(i - 1, 26)
        r = chr(65 + d) + r
    return r


def crear_excel_sin_dependencias(destino, resumen, fichas, pendientes, registros=None):
    """XLSX mínimo con tres hojas, filtros, encabezados, panel inmovilizado.
    Todos los datos externos se escriben como strings (sin fórmulas ejecutables).
    """
    # Un solo XLSX. Los datos CEP se obtienen SOLO del XML oficial.
    # El estado de cuenta y los intentos de consulta van exclusivamente en SPEI.
    sheets = [
        ('Resumen', ['Indicador', 'Valor'], [[a, str(b)] for a, b in resumen.items()]),
        ('Datos CEP', COLUMNAS, [[f.get(c, '') for c in COLUMNAS] for f in fichas]),
        ('SPEI', SPEI_COLUMNAS, [[r.get(c, '') for c in SPEI_COLUMNAS] for r in (registros or [])]),
    ]
    import xml.etree.ElementTree as ET2
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    ET2.register_namespace('', ns)
    def q(t): return '{'+ns+'}'+t

    def xml_valido(valor):
        # XML 1.0: no incluir controles/surrogates ilegales en datos externos.
        return ''.join(c for c in str(valor if valor is not None else '')
                       if c in '\t\n\r' or 0x20 <= ord(c) <= 0xD7FF
                       or 0xE000 <= ord(c) <= 0xFFFD
                       or 0x10000 <= ord(c) <= 0x10FFFF)
    with zipfile.ZipFile(destino, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>' + ''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1,len(sheets)+1)) + '</Types>')
        z.writestr('_rels/.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml', '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>' + ''.join(f'<sheet name="{name}" sheetId="{i}" r:id="rId{i}"/>' for i,(name,_,__) in enumerate(sheets,1)) + '</sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + ''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1,len(sheets)+1)) + f'<Relationship Id="rId{len(sheets)+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        z.writestr('xl/styles.xml', '<?xml version="1.0" encoding="UTF-8"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="10"/><name val="Aptos"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="10"/><name val="Aptos"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF164675"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="3"><xf xfId="0" fontId="0" fillId="0" borderId="0"/><xf xfId="0" fontId="1" fillId="2" borderId="0" applyFont="1" applyFill="1"/><xf xfId="0" numFmtId="2" fontId="0" fillId="0" borderId="0" applyNumberFormat="1"/></cellXfs></styleSheet>')
        for i, (nombre, headers, body) in enumerate(sheets, 1):
            root = ET2.Element(q('worksheet'))
            # Orden obligatorio en OOXML: dimension, sheetViews, sheetFormatPr, cols, sheetData.
            # Cols antes de sheetViews producía la reparación de hojas en Microsoft Excel.
            ET2.SubElement(root, q('dimension'), {
                'ref': f'A1:{_col_name(len(headers))}{len(body)+1}'})
            views = ET2.SubElement(root, q('sheetViews'))
            view = ET2.SubElement(views, q('sheetView'), {'workbookViewId':'0'})
            ET2.SubElement(view, q('pane'), {
                'ySplit':'1', 'topLeftCell':'A2', 'activePane':'bottomLeft', 'state':'frozen'})
            ET2.SubElement(root, q('sheetFormatPr'), {'defaultRowHeight':'15'})
            widths = ET2.SubElement(root, q('cols'))
            for j, h in enumerate(headers, 1):
                ET2.SubElement(widths, q('col'), {
                    'min':str(j), 'max':str(j),
                    'width':str(min(41,max(13,len(str(h))+3))), 'customWidth':'1'})
            data = ET2.SubElement(root, q('sheetData'))
            for rowno, vals in enumerate([headers]+body, 1):
                rr = ET2.SubElement(data, q('row'), {'r':str(rowno), 'ht':'22' if rowno==1 else '18', 'customHeight':'1'})
                for j, val in enumerate(vals, 1):
                    # Inline strings are never interpreted as formulas.
                    importe = _dinero(val) if rowno>1 and headers[j-1] in ('monto_cep','monto_estado_cuenta') else None
                    if importe is not None:
                        c = ET2.SubElement(rr,q('c'), {'r':f'{_col_name(j)}{rowno}', 's':'2'})
                        ET2.SubElement(c,q('v')).text = f'{importe:.2f}'
                    else:
                        c = ET2.SubElement(rr,q('c'), {'r':f'{_col_name(j)}{rowno}', 't':'inlineStr', 's':'1' if rowno==1 else '0'})
                        ET2.SubElement(ET2.SubElement(c,q('is')),q('t')).text = xml_valido(val)
            if body:
                ET2.SubElement(root, q('autoFilter'), {'ref':f'A1:{_col_name(len(headers))}{len(body)+1}'})
            z.writestr(f'xl/worksheets/sheet{i}.xml', ET2.tostring(root, encoding='utf-8', xml_declaration=True))
    return Path(destino)


def leer_consultas(path):
    """Lee la hoja SPEI del único XLSX; admite CSV históricos si se aportan."""
    if not path or not Path(path).is_file():
        return []
    if Path(path).suffix.lower() == '.xlsx':
        # Importación local para evitar dependencia circular con la generación del libro.
        from cep_core import xlsx_hojas
        libro = xlsx_hojas(path)
        hoja = libro.get('SPEI', [])
        if not hoja:
            raise ValueError('El archivo Excel no contiene la hoja SPEI')
        cols = [str(c or '').strip() for c in hoja[0]]
        return [dict(zip(cols, (str(v) if v is not None else '' for v in values)))
                for values in hoja[1:] if any(v not in (None, '') for v in values)]
    if Path(path).suffix.lower() == '.csv':
        with open(path, 'r', encoding='utf-8-sig', newline='') as f:
            return list(csv.DictReader(f))
    raise ValueError('Formato de consultas no compatible; selecciona resultado_CEP.xlsx')


def _validacion(xml, reg):
    problemas = []
    if xml['rastreo'] and _identificador(xml['rastreo']) != _identificador(reg.get('clave_rastreo')):
        problemas.append('Rastreo XML distinto')
    if xml['fecha'] and reg.get('fecha') and xml['fecha'] != reg['fecha']:
        problemas.append('Fecha XML distinta')
    mx, mr = _dinero(xml['monto']), _dinero(reg.get('monto'))
    if mx is not None and mr is not None and mx != mr:
        problemas.append('Monto XML distinto')
    cxml = _identificador(xml['cuenta_beneficiaria'])
    creg = _identificador(reg.get('cuenta_beneficiaria'))
    if cxml and creg and cxml != creg:
        problemas.append('Cuenta beneficiaria distinta')
    return problemas


def _encontrar_movimiento(xml, csv_map):
    rastreo = _identificador(xml['rastreo'])
    if not rastreo: return None, 'XML sin clave de rastreo; sin vínculo fiable al Excel'
    candidatos = csv_map.get(rastreo, [])
    if not candidatos: return None, 'Rastreo XML ausente en consultas individuales'
    if len(candidatos)==1: return candidatos[0], ''
    # Repeated tracking key: require unique date, amount, destination.
    filtrados = []
    for r in candidatos:
        if xml['fecha'] and r.get('fecha') != xml['fecha']: continue
        if xml['monto'] and _dinero(xml['monto']) != _dinero(r.get('monto')): continue
        if xml['cuenta_beneficiaria'] and _identificador(xml['cuenta_beneficiaria']) != _identificador(r.get('cuenta_beneficiaria')): continue
        filtrados.append(r)
    if len(filtrados)==1: return filtrados[0], ''
    # Un mismo rastreo puede repetirse, pero un XML con fecha +/-1 puede
    # relacionarse si monto, cuenta y la cercanía de fecha son inequívocos.
    cercanos = []
    for r in candidatos:
        try:
            delta = (datetime.fromisoformat(xml['fecha']) -
                     datetime.fromisoformat(r['fecha'])).days
        except (ValueError, TypeError, KeyError):
            continue
        if abs(delta) != 1:
            continue
        if xml['monto'] and _dinero(xml['monto']) != _dinero(r.get('monto')):
            continue
        if (xml['cuenta_beneficiaria'] and
                _identificador(xml['cuenta_beneficiaria']) !=
                _identificador(r.get('cuenta_beneficiaria'))):
            continue
        cercanos.append(r)
    if len(cercanos) == 1:
        return cercanos[0], ''
    return None, 'Múltiples movimientos con el mismo rastreo; relación ambigua'


def procesar_zip(ruta_zip, consultas_csv, salida):
    """Conserva ZIP; crea PDF/XML copias renombradas, Excel de extracción y pendientes."""
    ruta_zip, salida = Path(ruta_zip), Path(salida)
    if not zipfile.is_zipfile(ruta_zip): raise ValueError('Selecciona un ZIP válido descargado de Banxico')
    if salida.resolve() == ruta_zip.resolve(): raise ValueError('Ruta de salida inválida')
    if salida.exists() and any(salida.iterdir()):
        raise ValueError('Selecciona una carpeta de resultados vacía para evitar sobreescrituras')
    rows = leer_consultas(consultas_csv)
    for reg in rows:
        # No declarar FALLO sólo por ausencia: el ZIP puede estar incompleto.
        if reg.get('linea_lote') or reg.get('estado') in ('LISTO', 'LISTO_CON_ALERTAS'):
            reg['resultado_cep'] = 'NO_APARECE_EN_ZIP'
            reg['resultado_detalle'] = 'No se localizó XML vinculado dentro de este ZIP; no confirma rechazo de Banxico'
        else:
            reg['resultado_cep'] = 'NO_CONSULTABLE'
            reg['resultado_detalle'] = reg.get('observacion', 'Faltan datos para TXT')
        reg['tiene_pdf'] = 'NO'
        reg['archivo_pdf'] = ''
        reg['archivo_xml'] = ''
    csv_map = defaultdict(list)
    for r in rows:
        if r.get('clave_rastreo'): csv_map[_identificador(r['clave_rastreo'])].append(r)
    salida.mkdir(parents=True, exist_ok=True)
    pdf_dir = salida / 'PDF'; xml_dir = salida / 'XML'; revision_dir = salida / 'REVISION'
    for carpeta in (pdf_dir, xml_dir, revision_dir): carpeta.mkdir(exist_ok=True)
    resumen = {'XML procesados':0,'PDF encontrados':0,'PDF renombrados':0,
               'Coincidencias con Excel':0,'Requieren revisión':0,'PDF sin XML':0,
               'Sin CEP encontrado':0, 'XML sin PDF':0}
    fichas = []; pendientes=[]
    with zipfile.ZipFile(ruta_zip) as z:
        entradas = [i for i in z.infolist() if not i.is_dir()]
        if len(entradas) > MAX_ARCHIVOS or sum(i.file_size for i in entradas)>MAX_TOTAL:
            raise ValueError('ZIP excede los límites de seguridad')
        if any(i.file_size>MAX_ARCHIVO for i in entradas):
            raise ValueError('ZIP contiene un archivo excesivamente grande')
        xmls, pdfs, textos = [], [], []
        for info in entradas:
            path = Path(info.filename)
            # Only select by extension; never extract using untrusted path.
            suf = path.suffix.lower()
            if suf=='.xml': xmls.append(info)
            elif suf=='.pdf': pdfs.append(info)
            elif suf=='.txt': textos.append(info)
        resumen['PDF encontrados'] = len(pdfs)
        pdf_por_stem = defaultdict(list)
        for info in pdfs: pdf_por_stem[Path(info.filename).stem.casefold()].append(info)
        usados_pdf = set()
        for info in xmls:
            resumen['XML procesados'] += 1
            try: xd = datos_cep_xml(z.read(info))
            except (ET.ParseError, ValueError) as e:
                revision = revision_dir / ('INVALIDO_' + _seguro_nombre(Path(info.filename).stem) + '.xml')
                n = 2
                while revision.exists():
                    revision = revision_dir / f'INVALIDO_{_seguro_nombre(Path(info.filename).stem)}_{n}.xml'; n += 1
                revision.write_bytes(z.read(info))
                pendientes.append({'motivo':f'XML inválido {Path(info.filename).name}: {str(e)[:120]}'})
                continue
            if not xd['rastreo'] and not (xd['nombre_beneficiario'] and xd['nombre_ordenante'] and xd['monto']):
                revision = revision_dir / ('NO_CEP_' + _seguro_nombre(Path(info.filename).stem) + '.xml')
                n = 2
                while revision.exists():
                    revision = revision_dir / f'NO_CEP_{_seguro_nombre(Path(info.filename).stem)}_{n}.xml'; n += 1
                revision.write_bytes(z.read(info))
                pendientes.append({'motivo':'XML sin campos CEP suficientes: ' + Path(info.filename).name})
                continue
            reg, nota = _encontrar_movimiento(xd, csv_map)
            problemas = _validacion(xd, reg) if reg else []
            diferencia_fecha = None
            fecha_alternativa = False
            if reg and xd.get('fecha') and reg.get('fecha'):
                try:
                    diferencia_fecha = (datetime.fromisoformat(xd['fecha']) -
                                        datetime.fromisoformat(reg['fecha'])).days
                except ValueError:
                    pass
            if diferencia_fecha in (-1, 1):
                # No se sustituye silenciosamente la fecha original: el
                # comprobante existe, pero se registra la diferencia.
                fecha_alternativa = True
                problemas = [p for p in problemas if p != 'Fecha XML distinta']
            if nota and rows: problemas.append(nota)
            if reg and not all(xd.get(c) for c in ('rastreo', 'fecha', 'monto')):
                problemas.append('XML sin rastreo/fecha/monto suficientes para validar coincidencia')
            if not xd.get('nombre_beneficiario'):
                problemas.append('XML no aporta nombre de beneficiario reconocible')
            if reg and reg.get('tipo') == 'RECIBIDO' and not xd.get('nombre_ordenante'):
                problemas.append('SPEI recibido: nombre de ordenante no reconocido en XML')
            # An XML without identifiable core fields is not a verified extracted CEP.
            if not any(xd.get(k) for k in ('rastreo','nombre_beneficiario','nombre_ordenante')):
                problemas.append('XML sin campos CEP reconocibles')
            stem = Path(info.filename).stem.casefold()
            asociados = [p for p in pdf_por_stem.get(stem, []) if p.filename not in usados_pdf]
            if not asociados and len(pdfs)==1 and len(xmls)==1:
                asociados = [p for p in pdfs if p.filename not in usados_pdf]
            pdf = asociados[0] if len(asociados)==1 else None
            if len(asociados)>1: problemas.append('PDF ambiguos para XML')
            if pdf and not z.read(pdf).lstrip().startswith(b'%PDF-'):
                problemas.append('Archivo PDF inválido')
                pdf = None
            if not pdf: resumen['XML sin PDF'] += 1
            tipo = reg.get('tipo', '') if reg else ''
            # Contraparte real: salidas -> beneficiario, entradas -> ordenante.
            nombre_contraparte = xd['nombre_ordenante'] if tipo == 'RECIBIDO' else xd['nombre_beneficiario']
            nombre = _seguro_nombre(nombre_contraparte)
            periodo = xd['fecha'] or (reg.get('fecha') if reg else '') or 'SIN_FECHA'
            monto_nombre = _seguro_nombre(xd['monto'] or (reg.get('monto') if reg else '') or 'SIN_MONTO')
            rastreo = _seguro_nombre(xd['rastreo'] or (reg.get('clave_rastreo') if reg else '') or Path(info.filename).stem)[-26:]
            base = f'{periodo}__{tipo or "TIPO_INCIERTO"}__{nombre}__{monto_nombre}__{rastreo}'
            destino_xml = xml_dir / (base + '.xml')
            contador = 2
            while destino_xml.exists():
                destino_xml = xml_dir / f'{base}_{contador}.xml'; contador += 1
            destino_xml.write_bytes(z.read(info))
            destino_pdf = ''
            if pdf:
                usados_pdf.add(pdf.filename)
                ruta_pdf = pdf_dir / (destino_xml.stem + '.pdf')
                ruta_pdf.write_bytes(z.read(pdf))
                destino_pdf = str(Path('PDF')/ruta_pdf.name)
                resumen['PDF renombrados'] += 1
            estado = ('COINCIDE_FECHA_ALTERNATIVA' if reg and not problemas and fecha_alternativa else
                      'COINCIDE' if reg and not problemas else
                      'SIN_CRUCE' if not rows and not problemas else 'REVISAR')
            if reg:
                reg['resultado_cep'] = ('EXITO_FECHA_ALTERNATIVA' if estado == 'COINCIDE_FECHA_ALTERNATIVA'
                                        else 'EXITO' if estado == 'COINCIDE' else 'REVISAR')
                reg['fecha_cep_encontrada'] = xd.get('fecha', '')
                reg['diferencia_dias_fecha'] = str(diferencia_fecha) if diferencia_fecha is not None else ''
                reg['resultado_detalle'] = ('Fecha oficial CEP +/-1 día respecto del Excel'
                                            if fecha_alternativa and not problemas else
                                            '; '.join(problemas) if problemas else
                                            'XML oficial localizado y cotejado')
                reg['tiene_pdf'] = 'SÍ' if destino_pdf else 'NO'
                reg['archivo_pdf'] = destino_pdf
                reg['archivo_xml'] = str(Path('XML') / destino_xml.name)
            if estado in ('COINCIDE', 'COINCIDE_FECHA_ALTERNATIVA'): resumen['Coincidencias con Excel']+=1
            else: resumen['Requieren revisión']+=1
            fichas.append({
                'estado':estado, 'fecha_cep':xd['fecha'], 'nombre_beneficiario_cep':xd['nombre_beneficiario'],
                'nombre_ordenante_cep':xd['nombre_ordenante'], 'rfc_beneficiario_cep':xd['rfc_beneficiario'],
                'rfc_ordenante_cep':xd['rfc_ordenante'], 'cuenta_beneficiaria_cep':xd['cuenta_beneficiaria'],
                'cuenta_ordenante_cep':xd['cuenta_ordenante'], 'banco_emisor_cep':xd['emisor'],
                'banco_receptor_cep':xd['receptor'], 'monto_cep':xd['monto'],
                'clave_rastreo_cep':xd['rastreo'], 'referencia_cep':xd['referencia'],
                'concepto_cep':xd['concepto'], 'tipo_movimiento':reg.get('tipo','') if reg else '',
                'beneficiario_estado_cuenta':reg.get('nombre_beneficiario','') if reg else '',
                'fecha_estado_cuenta':reg.get('fecha','') if reg else '',
                'monto_estado_cuenta':reg.get('monto','') if reg else '',
                'clave_rastreo_estado_cuenta':reg.get('clave_rastreo','') if reg else '',
                'fila_excel':reg.get('fila_excel','') if reg else '',
                'id_estado':reg.get('id_estado','') if reg else '',
                'tiene_pdf':'SÍ' if destino_pdf else 'NO',
                'archivo_pdf':destino_pdf, 'archivo_xml':str(Path('XML')/destino_xml.name),
                'observaciones':'; '.join(problemas)})
        for info in pdfs:
            if info.filename in usados_pdf: continue
            # Preserve unknown PDFs separately; never assign an unverified identity.
            destino = revision_dir / ('SIN_XML_' + _seguro_nombre(Path(info.filename).stem) + '.pdf')
            i=2
            while destino.exists():
                destino=revision_dir / f'SIN_XML_{_seguro_nombre(Path(info.filename).stem)}_{i}.pdf'; i+=1
            destino.write_bytes(z.read(info))
            resumen['PDF sin XML']+=1
            pendientes.append({'motivo':'PDF sin XML asociado: '+destino.name})
        # Banxico includes 'resumen.txt' with not-found outcomes: preserve it.
        for info in textos:
            if Path(info.filename).name.lower()=='resumen.txt':
                (salida/'resumen_original_banxico.txt').write_bytes(z.read(info))
                lineas = z.read(info).decode('utf-8-sig','replace').splitlines()
                for ln in lineas:
                    if 'no se pudo localizar' in _normal(ln).lower():
                        resumen['Sin CEP encontrado']+=1
                        pendientes.append({'motivo':_texto(ln)[:200]})
                        # Un resultado negativo de Banxico es un fallo de búsqueda,
                        # NO una afirmación de que la transferencia haya fallado.
                        rastreos = [r for r in rows
                                   if r.get('clave_rastreo')
                                   and re.search(r'(?<![A-Za-z0-9])' +
                                                 re.escape(r['clave_rastreo']) +
                                                 r'(?![A-Za-z0-9])', ln, re.IGNORECASE)]
                        if len(rastreos) == 1 and rastreos[0].get('resultado_cep') == 'NO_APARECE_EN_ZIP':
                            rastreos[0]['resultado_cep'] = 'FALLO_BUSQUEDA_CEP'
                            rastreos[0]['resultado_detalle'] = _texto(ln)[:200]
        # Do not label absence in ZIP as definitely absent in Banxico.
    coincididos={_identificador(r['clave_rastreo_estado_cuenta']) for r in fichas if r.get('clave_rastreo_estado_cuenta')}
    for reg in rows:
        if reg.get('linea_lote') and _identificador(reg.get('clave_rastreo')) not in coincididos:
            pendientes.append({'clave_rastreo':reg.get('clave_rastreo',''),
                               'fecha':reg.get('fecha',''),'monto':reg.get('monto',''),
                               'fila_excel':reg.get('fila_excel',''),
                               'motivo':'Sin XML vinculado en el ZIP; verificar resumen de Banxico'})
    resumen['Registros en Datos CEP'] = len(fichas)
    resumen['Registros con PDF'] = sum(f['tiene_pdf'] == 'SÍ' for f in fichas)
    if (len(list(pdf_dir.glob('*.pdf'))) != resumen['Registros con PDF'] or
        len(list(xml_dir.glob('*.xml'))) != len(fichas) or
        any(not (salida / f['archivo_xml']).is_file() for f in fichas) or
        any(f['tiene_pdf'] == 'SÍ' and not (salida / f['archivo_pdf']).is_file() for f in fichas)):
        raise RuntimeError('Invariante documental: cada PDF/ debe corresponder a una fila SÍ en Datos CEP')
    resumen['SPEI en bitácora'] = len(rows)
    resumen['SPEI con XML vinculado'] = sum(r.get('resultado_cep') in ('EXITO', 'EXITO_FECHA_ALTERNATIVA', 'REVISAR') for r in rows)
    resumen['SPEI CEP encontrados con fecha alternativa'] = sum(r.get('resultado_cep') == 'EXITO_FECHA_ALTERNATIVA' for r in rows)
    resumen['SPEI sin XML en ZIP'] = sum(r.get('resultado_cep') == 'NO_APARECE_EN_ZIP' for r in rows)
    resumen['Fallos reportados en resumen.txt'] = sum(r.get('resultado_cep') == 'FALLO_BUSQUEDA_CEP' for r in rows)
    crear_excel_sin_dependencias(salida/'resultado_CEP.xlsx', resumen, fichas, pendientes, registros=rows)
    return {'resumen':resumen,'excel':str(salida/'resultado_CEP.xlsx'), 'carpeta':str(salida),
            'fichas':len(fichas),'pendientes':len(pendientes)}
