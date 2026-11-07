import csv
import tempfile
import unittest
import zipfile
from pathlib import Path
from cep_importador import datos_cep_xml, procesar_zip


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
            self.assertTrue(next((d/'salida'/'PDF').glob('SIN_XML_*.pdf')).is_file())
            self.assertFalse((d/'comprobante.pdf').exists())

if __name__=='__main__': unittest.main()
