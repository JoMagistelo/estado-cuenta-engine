"""Interfaz del piloto local CEP Banxico. Ejecutar: python CEP_Banxico_GUI.py"""
from __future__ import annotations
import os
import subprocess
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from cep_core import INDIVIDUAL, LOTES, analizar, exportar, diagnostico_web
RESULTADOS_BANXICO = 'https://www.banxico.org.mx/cep-scl/inicio2.do'
from cep_importador import procesar_zip
from cep_paquete import exportar_zip_cep


class Aplicacion(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('CEP Banxico | Consulta paso a paso')
        self.geometry('1200x825')
        self.minsize(930, 690)
        self.configure(bg='#f4f7fb')
        self.archivo = tk.StringVar()
        self.clabe = tk.StringVar()
        self.resumen = tk.StringVar(value='Paso 1: selecciona tu Excel de movimientos.')
        self.ruta_lote = tk.StringVar(value='Todavía no has generado un TXT.')
        self.resultados = []
        self.carpeta_solicitud = None
        self.carpeta = None

        st = ttk.Style(self)
        if 'clam' in st.theme_names(): st.theme_use('clam')
        st.configure('TFrame', background='#f4f7fb')
        st.configure('TLabel', background='#f4f7fb', foreground='#1d2b43', font=('Segoe UI', 10))
        st.configure('TButton', font=('Segoe UI', 10), padding=(9, 6))
        st.configure('Header.TLabel', background='#f4f7fb', font=('Segoe UI', 20, 'bold'), foreground='#0f2545')
        st.configure('Sub.TLabel', background='#f4f7fb', foreground='#53667b')
        st.configure('Step.TLabelframe', background='#f4f7fb')
        st.configure('Step.TLabelframe.Label', background='#f4f7fb', foreground='#0f2545', font=('Segoe UI', 10, 'bold'))
        st.configure('Treeview', rowheight=26, font=('Segoe UI', 9))
        st.configure('Treeview.Heading', font=('Segoe UI', 9, 'bold'))

        area = ttk.Frame(self, padding=15)
        area.pack(fill='both', expand=True)
        ttk.Label(area, text='Consulta de CEP Banxico', style='Header.TLabel').pack(anchor='w')
        ttk.Label(area, text='Del Excel de Estado Cuenta Engine al ZIP final con PDF, XML y nombres/RFC oficiales.',
                  style='Sub.TLabel').pack(anchor='w', pady=(1, 9))

        pasos = ttk.LabelFrame(area, text='PASOS DE CONSULTA', style='Step.TLabelframe', padding=10)
        pasos.pack(fill='x')
        fila1 = ttk.Frame(pasos)
        fila1.pack(fill='x', pady=(0, 5))
        ttk.Label(fila1, text='1. Seleccionar Excel / CSV', width=26).pack(side='left')
        ttk.Entry(fila1, textvariable=self.archivo).pack(side='left', fill='x', expand=True, padx=(0, 8))
        ttk.Button(fila1, text='Buscar archivo...', command=self.seleccionar).pack(side='left')

        fila2 = ttk.Frame(pasos)
        fila2.pack(fill='x', pady=4)
        ttk.Label(fila2, text='CLABE propia (opcional):').pack(side='left')
        ttk.Entry(fila2, textvariable=self.clabe, width=24).pack(side='left', padx=(7, 16))
        ttk.Button(fila2, text='2. Detectar transferencias SPEI', command=self.analizar).pack(side='left')
        ttk.Label(fila2, text='No requiere clasificar Tipo de Operación.',
                  style='Sub.TLabel').pack(side='left', padx=(12, 0))

        fila3 = ttk.Frame(pasos)
        fila3.pack(fill='x', pady=4)
        self.btn_txt = ttk.Button(fila3, text='3. Generar TXT + Excel SPEI', command=self.guardar)
        self.btn_txt.pack(side='left')
        ttk.Label(fila3, textvariable=self.ruta_lote, style='Sub.TLabel').pack(side='left', padx=12)
        ttk.Button(fila3, text='Abrir carpeta', command=self.abrir_carpeta).pack(side='right')

        fila4 = ttk.Frame(pasos)
        fila4.pack(fill='x', pady=4)
        self.btn_carga = ttk.Button(fila4, text='4. Abrir Banxico y subir TXT',
                                    command=self.abrir_carga_banxico)
        self.btn_carga.pack(side='left', padx=(0, 10))
        ttk.Button(fila4, text='5. Recuperar ZIP con correo + token',
                   command=self.abrir_descarga_banxico).pack(side='left')
        ttk.Label(fila4, text='En Banxico selecciona PDF y XML.',
                  style='Sub.TLabel').pack(side='left', padx=(12, 0))

        fila5 = ttk.Frame(pasos)
        fila5.pack(fill='x', pady=4)
        ttk.Button(fila5, text='6. Exportar ZIP final (PDF + XML + Excel)',
                   command=self.importar_zip).pack(side='left')
        ttk.Label(fila5, text='Selecciona el ZIP que descargaste del portal.',
                  style='Sub.TLabel').pack(side='left', padx=(12, 0))

        libre = ttk.LabelFrame(area, text='¿YA TIENES UN ZIP DE BANXICO?', style='Step.TLabelframe',
                               padding=9)
        libre.pack(fill='x', pady=(9, 5))
        ttk.Button(libre, text='Procesar ZIP existente (sin Excel ni TXT)',
                   command=self.importar_zip_libre).pack(side='left')
        ttk.Label(libre, text='Extrae nombres y RFC del XML; conserva PDF y XML, y genera el Excel + ZIP final.',
                  style='Sub.TLabel').pack(side='left', padx=(12, 0))

        ttk.Label(area, textvariable=self.resumen, foreground='#0d6374',
                  font=('Segoe UI', 10, 'bold')).pack(anchor='w', pady=(5, 7))
        herramientas = ttk.Frame(area)
        herramientas.pack(fill='x', pady=(0, 7))
        for titulo, funcion in [
            ('CEP individual', lambda: webbrowser.open(INDIVIDUAL)),
            ('Probar acceso Banxico', self.diagnosticar),
            ('Copiar fila', self.copiar),
            ('Abrir resultados', self.abrir_carpeta),
        ]:
            ttk.Button(herramientas, text=titulo, command=funcion).pack(side='left', padx=(0, 7))

        cols = ('fila_excel', 'tipo', 'fecha', 'monto', 'clave_rastreo',
                'referencia', 'emisor', 'receptor', 'cuenta_beneficiaria', 'estado', 'observacion')
        self.cols = cols
        panel = ttk.Frame(area)
        panel.pack(fill='both', expand=True)
        self.tabla = ttk.Treeview(panel, columns=cols, show='headings', selectmode='extended')
        anchos = {'fila_excel':70, 'tipo':85, 'fecha':100, 'monto':105,
                  'clave_rastreo':165, 'referencia':100, 'emisor':75, 'receptor':75,
                  'cuenta_beneficiaria':170, 'estado':90, 'observacion':380}
        for c in cols:
            self.tabla.heading(c, text=c.replace('_', ' ').capitalize())
            self.tabla.column(c, width=anchos[c], stretch=(c == 'observacion'), anchor='w')
        self.tabla.tag_configure('listo', background='#e7f4ef')
        self.tabla.tag_configure('pendiente', background='#fff5e3')
        self.tabla.pack(side='left', fill='both', expand=True)
        vs = ttk.Scrollbar(panel, orient='vertical', command=self.tabla.yview)
        vs.pack(side='right', fill='y')
        self.tabla.configure(yscrollcommand=vs.set)
        hs = ttk.Scrollbar(area, orient='horizontal', command=self.tabla.xview)
        hs.pack(fill='x')
        self.tabla.configure(xscrollcommand=hs.set)
        ttk.Label(area, text='El TXT es para consultar; el ZIP con los comprobantes lo entrega Banxico. '
                            'La aplicación organiza ese ZIP, no evade CAPTCHA.',
                  style='Sub.TLabel').pack(anchor='w', pady=(8, 0))
        self.archivo.trace_add('write', self._limpiar_analisis)
        self.clabe.trace_add('write', self._limpiar_analisis)
        self._actualizar_botones()

    def _limpiar_analisis(self, *_):
        # Cambiar archivo o CLABE invalida consultas previamente preparadas.
        self.resultados = []
        self.carpeta_solicitud = None
        self.ruta_lote.set('Todavía no has generado un TXT.')
        self.resumen.set('Paso 2: detecta los SPEI del archivo seleccionado.')
        for item in self.tabla.get_children():
            self.tabla.delete(item)
        self._actualizar_botones()

    def _actualizar_botones(self):
        self.btn_txt.configure(state='normal' if self.resultados else 'disabled')
        lotes = bool(self.carpeta_solicitud and
                     list(self.carpeta_solicitud.glob('lote_*.txt')))
        self.btn_carga.configure(state='normal' if lotes else 'disabled')

    def seleccionar(self):
        filename = filedialog.askopenfilename(
            title='Selecciona Excel de Estado Cuenta Engine',
            filetypes=[('Excel o CSV', '*.xlsx *.csv'), ('Excel', '*.xlsx'), ('CSV', '*.csv')])
        if filename:
            self.archivo.set(filename)

    def analizar(self):
        path = self.archivo.get().strip().strip('"')
        if not path or not Path(path).is_file():
            messagebox.showwarning('Paso 1: falta Excel', 'Selecciona primero el Excel o CSV.')
            return
        try:
            registros, total = analizar(path, self.clabe.get().strip())
        except Exception as exc:
            messagebox.showerror('No se pudo analizar', str(exc))
            return
        self.resultados = registros
        self.carpeta_solicitud = None
        self.ruta_lote.set('Paso 3 pendiente: generar TXT.')
        for item in self.tabla.get_children():
            self.tabla.delete(item)
        for i, r in enumerate(registros):
            self.tabla.insert('', 'end', iid=str(i),
                              values=[r.get(c, '') for c in self.cols],
                              tags=('listo' if r['estado'] == 'LISTO' else 'pendiente',))
        listos = sum(bool(r.get('linea_lote')) for r in registros)
        self.resumen.set(f'Movimientos: {total}  |  SPEI candidatos: {len(registros)}  |  '
                         f'Listos: {listos}  |  Por revisar: {len(registros)-listos}')
        self._actualizar_botones()

    def guardar(self):
        if not self.resultados:
            messagebox.showwarning('Paso 2 pendiente', 'Primero detecta las transferencias SPEI.')
            return
        destino = filedialog.askdirectory(title='Carpeta para guardar TXT y CSV de consulta')
        if not destino:
            return
        carpeta = Path(destino) / ('CEP_SOLICITUD_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        try:
            info = exportar(self.resultados, carpeta)
        except Exception as exc:
            messagebox.showerror('No se pudo generar TXT', str(exc))
            return
        self.carpeta_solicitud = carpeta
        self.carpeta = carpeta
        lotes = sorted(carpeta.glob('lote_*.txt'))
        self.ruta_lote.set(f'{len(lotes)} TXT + 1 Excel en: {carpeta}')
        self._actualizar_botones()
        if not lotes:
            messagebox.showwarning('Sin archivo TXT', 'No hay al menos 2 SPEI completos. '
                                   'Revisa los pendientes antes de consultar.')
            return
        messagebox.showinfo('Paso 3 completado',
            f"Listos: {info['listos']}  |  Revisión: {info['pendientes']}\n"
            f"TXT generados: {len(lotes)}\n\n"
            f'Archivo para Banxico:\n{lotes[0]}\n\n'
            'También se creó un solo resultado_CEP.xlsx, con todos los SPEI.\n\n'
            'Banxico acepta el TXT, NO el ZIP final. Ahora usa el botón 4.')

    def abrir_carga_banxico(self):
        carpeta = self.carpeta_solicitud
        lotes = sorted(carpeta.glob('lote_*.txt')) if carpeta else []
        if not lotes:
            messagebox.showwarning('Paso 3 pendiente', 'Primero genera el TXT.')
            return
        messagebox.showinfo('Paso 4: subir TXT en Banxico',
            f'Selecciona este archivo en Banxico:\n{lotes[0]}\n\n'
            'Elige ambos formatos: PDF + XML. Ingresa tu correo y guarda el token. '
            'Si aparece CAPTCHA, complétalo en el navegador.')
        webbrowser.open(LOTES)

    def abrir_descarga_banxico(self):
        messagebox.showinfo('Paso 5: recuperar comprobantes',
            'En la página de resultados de Banxico escribe tu correo y el token '
            'de la consulta. Descarga el ZIP oficial con PDF y XML.\n\n'
            'Después vuelve aquí y pulsa el botón 6 para generar el ZIP final organizado.')
        webbrowser.open(RESULTADOS_BANXICO)

    def importar_zip_libre(self):
        # Funciona sin haber cargado ningún Excel, CSV de rastreos ni TXT.
        return self.importar_zip(independiente=True)

    def importar_zip(self, independiente=False):
        descargas = Path.home() / 'Downloads'
        ruta = filedialog.askopenfilename(
            title='Elige el ZIP oficial de Banxico (PDF y/o XML)',
            initialdir=str(descargas if descargas.is_dir() else Path.home()),
            filetypes=[('ZIP oficial', '*.zip')])
        if not ruta:
            return

        # El cotejo bancario es opcional. Ningún nombre/RFC se toma del CSV.
        consultas = None
        if not independiente and self.carpeta_solicitud:
            candidato = self.carpeta_solicitud / 'resultado_CEP.xlsx'
            if candidato.is_file():
                consultas = candidato
        nombre = 'CEP_BANXICO_FINAL_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.zip'
        destino_zip = filedialog.asksaveasfilename(
            title='Dónde exportar el ZIP final de CEP',
            initialdir=str(Path(ruta).parent),
            initialfile=nombre,
            defaultextension='.zip',
            filetypes=[('Archivo ZIP', '*.zip')])
        if not destino_zip:
            return
        paquete = Path(destino_zip)
        salida = paquete.parent / ('CEP_RECUPERADOS_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        try:
            info = procesar_zip(ruta, consultas, salida)
            paquete_info = exportar_zip_cep(salida, paquete)
        except Exception as exc:
            messagebox.showerror('No se pudo exportar ZIP', str(exc))
            return
        self.carpeta = salida
        r = info['resumen']
        self.resumen.set(f"Datos CEP: {r['Registros en Datos CEP']}  |  "
                         f"Con PDF: {r['Registros con PDF']}  |  "
                         f"Sin PDF: {r['XML sin PDF']}  |  "
                         f"Revisión: {r['Requieren revisión']}")
        messagebox.showinfo('Paso 6: ZIP final exportado',
            f"ZIP creado:\n{paquete_info['zip']}\n\n"
            f"Registros en Excel: {paquete_info['registros_cep']}\n"
            f"PDF vinculados: {paquete_info['pdf_vinculados']}\n"
            f"XML sin PDF: {paquete_info['xml_sin_pdf']}\n\n"
            'Los nombres y RFC del Excel provienen exclusivamente de los XML oficiales. '
            'El ZIP original no se modificó.')

    def copiar(self):
        seleccion = self.tabla.selection()
        if not seleccion: return
        filas = ['\t'.join(str(v) for v in self.tabla.item(i, 'values')) for i in seleccion]
        self.clipboard_clear(); self.clipboard_append('\n'.join(filas))

    def abrir_carpeta(self):
        if not self.carpeta or not self.carpeta.is_dir():
            messagebox.showinfo('Sin resultados', 'Primero genera los archivos.'); return
        if sys.platform == 'win32': os.startfile(str(self.carpeta))
        elif sys.platform == 'darwin': subprocess.Popen(['open', str(self.carpeta)])
        else: subprocess.Popen(['xdg-open', str(self.carpeta)])

    def diagnosticar(self):
        self.resumen.set('Probando acceso HTTP sin enviar datos ni solicitudes de CEP…')
        def job():
            resultado = diagnostico_web()
            self.after(0, lambda: self.ver_diagnostico(resultado))
        threading.Thread(target=job, daemon=True).start()

    def ver_diagnostico(self, s):
        self.resumen.set('Diagnóstico de acceso terminado. Puedes analizar tu Excel.')
        messagebox.showinfo('Diagnóstico Banxico', s)


if __name__ == '__main__':
    Aplicacion().mainloop()
