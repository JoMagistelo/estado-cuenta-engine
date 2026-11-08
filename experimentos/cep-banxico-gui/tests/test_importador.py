import csv
import tempfile
import unittest
import zipfile
from pathlib import Path
from cep_importador import datos_cep_xml, procesar_zip
from cep_core import xlsx_hojas


XML = b'''<?xml version="1.0" encoding="UTF-8"?>
<CEP><FechaOperacion>2025-04-28</FechaOperacion><ClaveRastreo>PRUEBA-123456789</ClaveRastreo>
<Monto>10000.00</Monto><ConceptoPago>TEST</ConceptoPago>
<Ordenante><Nombre>REMITENTE DE PRUEBA</Nombre><RFC>RUTX010101XXX</RFC></Ordenante>
<Beneficiario><Nombre>Beneficiario &amp; Compa\xc3\xb1\xc3\xada</Nombre><RFC>BETX010101XXX</RFC><Cuenta>012123456789012346</Cuenta></Beneficiario></CEP>'''

class TestImportador(unittest.TestCase):
    def consultas(self, p, monto='10000.00'):
        with p.open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f, fieldnames=['clave_rastreo','fecha','monto','cuenta_beneficiaria','nombre_beneficiario','tipo','fila_excel','id_estado','estado'])
            w.writeheader(); w.writerow({'clave_rastreo':'PRUEBA-123456789','fecha':'2025-04-28','monto':monto,'cuenta_beneficiaria':'012123456789012346',
                                     'nombre_beneficiario':'NO VERIFICADO','tipo':'ENVIADO','fila_excel':'18','id_estado':'1','estado':'LISTO'})

    def test_extraer_xml_con_estructura_anidada(self):
        x=datos_cep_xml(XML)
        self.assertEqual(x['nombre_beneficiario'],'Beneficiario & Compañía')
        self.assertEqual(x['nombre_ordenante'],'REMITENTE DE PRUEBA')
        self.assertEqual(x['rastreo'],'PRUEBA-123456789')
        self.assertEqual(x['monto'],'10000.00')

    def test_extrae_pdfs_y_xlsx_sin_modificar_zip(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); self.consultas(d/'consultas.csv')
            with zipfile.ZipFile(d/'descarga.zip','w') as z:
                z.writestr('carpeta/001.xml', XML)
                z.writestr('carpeta/001.pdf', b'%PDF-1.4\n% PDF DE PRUEBA\n')
                z.writestr('resumen.txt','OK')
            original=(d/'descarga.zip').read_bytes()
            result=procesar_zip(d/'descarga.zip',d/'consultas.csv', d/'salida')
            self.assertEqual(result['resumen']['Coincidencias con Excel'],1)
            self.assertEqual(result['resumen']['PDF renombrados'],1)
            pdfs=list((d/'salida'/'PDF').glob('*.pdf'))
            self.assertEqual(len(pdfs),1)
            self.assertIn('BENEFICIARIO_COMPANIA',pdfs[0].name)
            self.assertTrue((d/'salida'/'resultado_CEP.xlsx').exists())
            with zipfile.ZipFile(d/'salida'/'resultado_CEP.xlsx') as book:
                self.assertIn('xl/worksheets/sheet2.xml', book.namelist())
                self.assertIn(b'Beneficiario',book.read('xl/worksheets/sheet2.xml'))
            self.assertEqual(original,(d/'descarga.zip').read_bytes())
            self.assertIn('ENVIADO',pdfs[0].name)
            self.assertIn('10000.00',pdfs[0].name)

    def test_recibido_se_nombra_con_ordenante_no_titular(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d)
            self.consultas(d/'c.csv')
            # La cuenta/beneficiario puede ser la persona evaluada que recibió el SPEI.
            with (d/'c.csv').open('r',encoding='utf-8-sig',newline='') as f:
                rows=list(csv.DictReader(f))
            rows[0]['tipo']='RECIBIDO'
            with (d/'c.csv').open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
            with zipfile.ZipFile(d/'z.zip','w') as z:
                z.writestr('001.xml', XML);z.writestr('001.pdf',b'%PDF-1.4')
            result=procesar_zip(d/'z.zip',d/'c.csv', d/'out')
            nombres=[x.name for x in (d/'out'/'PDF').glob('*.pdf')]
            self.assertEqual(len(nombres),1)
            self.assertIn('REMITENTE_DE_PRUEBA', nombres[0])
            self.assertNotIn('BENEFICIARIO_COMPANIA', nombres[0])
            self.assertEqual(result['resumen']['Coincidencias con Excel'],1)

    def test_monto_distinto_marca_revision(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); self.consultas(d/'c.csv','9800.00')
            with zipfile.ZipFile(d/'z.zip','w') as z:
                z.writestr('001.xml',XML);z.writestr('001.pdf',b'%PDF-1.4')
            r=procesar_zip(d/'z.zip',d/'c.csv',d/'salida')
            self.assertEqual(r['resumen']['Requieren revisión'],1)
            self.assertEqual(r['resumen']['Coincidencias con Excel'],0)

    def test_pdf_sin_xml_se_conserva_no_inventa_nombre(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);self.consultas(d/'c.csv')
            with zipfile.ZipFile(d/'z.zip','w') as z:z.writestr('../comprobante.pdf',b'%PDF-1.4')
            r=procesar_zip(d/'z.zip',d/'c.csv',d/'salida')
            self.assertEqual(r['resumen']['PDF sin XML'],1)
            self.assertTrue(next((d/'salida'/'REVISION').glob('SIN_XML_*.pdf')).is_file())
            self.assertFalse((d/'comprobante.pdf').exists())


    def test_unica_hoja_pdf_si_no_y_datos_solo_xml(self):
        from xml.etree import ElementTree as ET
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); self.consultas(d/'c.csv')
            distinto = XML.replace(b'PRUEBA-123456789',b'PRUEBA-987654321')
            distinto = distinto.replace(b'10000.00',b'500.00')
            with zipfile.ZipFile(d/'z.zip','w') as z:
                z.writestr('001.xml', XML)
                z.writestr('001.pdf', b'%PDF-1.4\\nPrueba')
                z.writestr('002.xml', distinto)
            r=procesar_zip(d/'z.zip',d/'c.csv',d/'out')
            self.assertEqual(r['resumen']['Registros en Datos CEP'],2)
            self.assertEqual(r['resumen']['Registros con PDF'],1)
            self.assertEqual(len(list((d/'out'/'PDF').glob('*.pdf'))),1)
            self.assertEqual(len(list((d/'out'/'XML').glob('*.xml'))),2)
            with zipfile.ZipFile(d/'out'/'resultado_CEP.xlsx') as book:
                workbook=book.read('xl/workbook.xml')
                self.assertIn(b'Datos CEP',workbook)
                self.assertNotIn(b'CEP solo XML',workbook)
                sheet=ET.fromstring(book.read('xl/worksheets/sheet2.xml'))
                ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                rows=sheet.findall('./s:sheetData/s:row',ns)
                self.assertEqual(len(rows),3)
                def ctext(c): return ''.join(c.itertext())
                titles=[ctext(c) for c in rows[0].findall('s:c',ns)]
                self.assertIn('tiene_pdf',titles)
                self.assertNotIn('beneficiario_estado_cuenta',titles)
                ix=titles.index('tiene_pdf')
                vals=[ctext(row.findall('s:c',ns)[ix]) for row in rows[1:]]
                self.assertEqual(sorted(vals),['NO','SÍ'])
                self.assertIn(b'BETX010101XXX',book.read('xl/worksheets/sheet2.xml'))

    def test_pdf_invalido_no_cuenta_como_pdf_oficial(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); self.consultas(d/'c.csv')
            with zipfile.ZipFile(d/'z.zip','w') as z:
                z.writestr('001.xml',XML)
                z.writestr('001.pdf',b'NO ES PDF')
            r=procesar_zip(d/'z.zip',d/'c.csv',d/'out')
            self.assertEqual(r['resumen']['Registros en Datos CEP'],1)
            self.assertEqual(r['resumen']['Registros con PDF'],0)
            self.assertEqual(len(list((d/'out'/'PDF').glob('*.pdf'))),0)
            self.assertEqual(len(list((d/'out'/'REVISION').glob('*.pdf'))),1)


    def test_fecha_alternativa_un_dia_preserva_fecha_original(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t)
            self.consultas(p/'consultas.csv')
            alternativa = XML.replace(b'2025-04-28', b'2025-04-29')
            with zipfile.ZipFile(p/'banxico.zip', 'w') as z:
                z.writestr('001.xml', alternativa)
                z.writestr('001.pdf', b'%PDF-1.4\nPRUEBA')
            resultado = procesar_zip(p/'banxico.zip', p/'consultas.csv', p/'out')
            self.assertEqual(resultado['resumen']['SPEI CEP encontrados con fecha alternativa'],1)
            hojas=xlsx_hojas(p/'out'/'resultado_CEP.xlsx')
            encabezado=hojas['SPEI'][0]
            fila=hojas['SPEI'][1]
            self.assertEqual(fila[encabezado.index('resultado_cep')], 'EXITO_FECHA_ALTERNATIVA')
            self.assertEqual(fila[encabezado.index('fecha')], '2025-04-28')
            self.assertEqual(fila[encabezado.index('fecha_cep_encontrada')], '2025-04-29')
            self.assertEqual(str(fila[encabezado.index('diferencia_dias_fecha')]), '1')

if __name__=='__main__': unittest.main()
