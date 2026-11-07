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


class Aplicacion(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('CEP Banxico | Piloto Estado Cuenta Engine')
        self.geometry('1160x700'); self.minsize(880, 580)
        self.configure(bg='#f4f7fb')
        self.archivo = tk.StringVar(); self.clabe = tk.StringVar()
        self.resumen = tk.StringVar(value='Selecciona un Excel (.xlsx) o CSV de movimientos para comenzar.')
        self.resultados = []; self.carpeta = None
        st = ttk.Style(self)
        if 'clam' in st.theme_names(): st.theme_use('clam')
        st.configure('TFrame', background='#f4f7fb')
        st.configure('TLabel', background='#f4f7fb', foreground='#1d2b43', font=('Segoe UI', 10))
        st.configure('TButton', font=('Segoe UI', 10), padding=(11, 7))
        st.configure('Header.TLabel', font=('Segoe UI', 20, 'bold'), foreground='#0f2545')
        st.configure('Sub.TLabel', foreground='#50647b')
        st.configure('Treeview', rowheight=27, font=('Segoe UI', 9))
        st.configure('Treeview.Heading', font=('Segoe UI', 9, 'bold'))
        area = ttk.Frame(self, padding=18); area.pack(fill='both', expand=True)
        ttk.Label(area, text='Preparador de CEP Banxico', style='Header.TLabel').pack(anchor='w')
        ttk.Label(area, text='Lee Estado Cuenta Engine · identifica SPEI por sus datos · genera consultas individuales y lotes TXT', style='Sub.TLabel').pack(anchor='w', pady=(0, 15))
        sel = ttk.Frame(area); sel.pack(fill='x')
        ttk.Entry(sel, textvariable=self.archivo).pack(side='left', fill='x', expand=True)
        ttk.Button(sel, text='Seleccionar Excel / CSV', command=self.seleccionar).pack(side='left', padx=(8, 0))
        config = ttk.Frame(area); config.pack(fill='x', pady=11)
        ttk.Label(config, text='CLABE del evaluado (opcional; usa la hoja Datos de la Cuenta cuando existe):').pack(side='left')
        ttk.Entry(config, textvariable=self.clabe, width=25).pack(side='left', padx=10)
        ttk.Button(config, text='Analizar movimientos', command=self.analizar).pack(side='left', padx=(2, 8))
        ttk.Button(config, text='Generar archivos', command=self.guardar).pack(side='left')
        ttk.Label(area, textvariable=self.resumen, foreground='#0d6374', font=('Segoe UI', 10, 'bold')).pack(anchor='w', pady=(6, 10))
        tb = ttk.Frame(area); tb.pack(fill='x', pady=(0, 8))
        for label, fun in [('Abrir CEP individual', lambda: webbrowser.open(INDIVIDUAL)),
                           ('Abrir CEP por lotes', lambda: webbrowser.open(LOTES)),
                           ('Probar acceso Banxico', self.diagnosticar),
                           ('Copiar fila seleccionada', self.copiar),
                           ('Abrir carpeta de resultados', self.abrir_carpeta)]:
            ttk.Button(tb, text=label, command=fun).pack(side='left', padx=(0, 7))
        cols = ('fila_excel', 'tipo', 'fecha', 'monto', 'clave_rastreo',
                'referencia', 'emisor', 'receptor', 'cuenta_beneficiaria', 'estado', 'observacion')
        self.cols = cols
        panel = ttk.Frame(area); panel.pack(fill='both', expand=True)
        self.tabla = ttk.Treeview(panel, columns=cols, show='headings', selectmode='extended')
        anchos = {'fila_excel':60,'tipo':85,'fecha':100,'monto':105,'clave_rastreo':155,
                  'referencia':105,'emisor':75,'receptor':75,'cuenta_beneficiaria':165,
                  'estado':85,'observacion':400}
        for c in cols:
            self.tabla.heading(c, text=c.replace('_',' ').capitalize())
            self.tabla.column(c, width=anchos[c], stretch=c=='observacion', anchor='w')
        self.tabla.tag_configure('listo', background='#e7f4ef')
        self.tabla.tag_configure('pendiente', background='#fff5e3')
        self.tabla.pack(side='left', fill='both', expand=True)
        vs = ttk.Scrollbar(panel, orient='vertical', command=self.tabla.yview)
        vs.pack(side='right', fill='y'); self.tabla.configure(yscrollcommand=vs.set)
        hs = ttk.Scrollbar(area, orient='horizontal', command=self.tabla.xview)
        hs.pack(fill='x'); self.tabla.configure(xscrollcommand=hs.set)
        ttk.Label(area, text='Piloto local: no solicita ni descarga CEP automáticamente. No resuelve ni omite CAPTCHA.', style='Sub.TLabel').pack(anchor='w', pady=(10, 0))

    def seleccionar(self):
        filename = filedialog.askopenfilename(title='Selecciona Excel de Estado Cuenta Engine',
                    filetypes=[('Excel o CSV','*.xlsx *.csv'),('Excel','*.xlsx'),('CSV','*.csv')])
        if filename: self.archivo.set(filename); self.resultados=[]

    def analizar(self):
        path = self.archivo.get().strip().strip('"')
        if not path or not Path(path).is_file():
            messagebox.showwarning('Falta archivo', 'Selecciona primero el Excel o CSV.'); return
        try:
            registros, total = analizar(path, self.clabe.get().strip())
        except Exception as e:
            messagebox.showerror('No se pudo analizar', str(e)); return
        self.resultados = registros
        for iid in self.tabla.get_children(): self.tabla.delete(iid)
        for i, r in enumerate(registros):
            self.tabla.insert('', 'end', iid=str(i), values=[r.get(c, '') for c in self.cols],
                              tags=('listo' if r['estado']=='LISTO' else 'pendiente',))
        listos = sum(r['estado']=='LISTO' for r in registros)
        self.resumen.set(f'Movimientos leídos: {total}   |   SPEI candidatos: {len(registros)}   |   Listos: {listos}   |   Revisión: {len(registros)-listos}')

    def guardar(self):
        if not self.resultados:
            messagebox.showwarning('Primero analiza', 'Carga y analiza el archivo antes de exportar.'); return
        destino = filedialog.askdirectory(title='Selecciona dónde guardar los resultados')
        if not destino: return
        carpeta = Path(destino) / ('CEP_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
        try: info = exportar(self.resultados, carpeta)
        except Exception as e:
            messagebox.showerror('Error al exportar', str(e)); return
        self.carpeta = carpeta
        messagebox.showinfo('Archivos preparados',
          f"Listos: {info['listos']} | Revisión: {info['pendientes']} | Lotes TXT: {info['lotes']}\n\n{carpeta}\n\nLos TXT deben cargarse manualmente en Banxico; no son CEP descargados.")

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