"""Flet workspace for original/normalized Excel, TXT and official CEP ZIP."""

from __future__ import annotations

import asyncio
import tempfile
from collections import Counter
from copy import deepcopy
from pathlib import Path

import flet as ft

from cep.evidence import CepEvidence, match_evidence
from cep.package import append_cep, export_cep_zip
from cep.queries import BANXICO_BATCH_URL, batch_texts, queries_from_workbook
from exporters.excel.workbook_bundle import WorkbookBundle, original_from_results


class CepPanel:
    def __init__(self, page, get_results, can_use_results):
        self.page = page
        self.get_results = get_results
        self.can_use_results = can_use_results
        self.bundle = None
        self.normalized = False
        self.source = None
        self.source_name = "movimientos.xlsx"
        self.queries = []
        self.evidence = CepEvidence()
        self.busy = False
        self.message = ft.Text("Carga un Excel exportado o usa los resultados actuales.", selectable=True, size=12)
        self.summary = ft.Text("", size=12, weight=ft.FontWeight.BOLD)
        self.preview = ft.Column(spacing=4)
        self.adjacent = ft.Checkbox(label="Fecha homologada y reintentos de un día antes y después", value=True)
        self.load_button = ft.OutlinedButton(content="Cargar Excel", icon=ft.Icons.UPLOAD_FILE, on_click=self.load_excel)
        self.current_button = ft.FilledButton(content="Usar extracción actual", icon=ft.Icons.TABLE_VIEW, on_click=self.use_current)
        self.normalize_button = ft.FilledButton(content="Normalizar Excel", icon=ft.Icons.AUTO_FIX_HIGH,
                                                on_click=self.normalize_excel, disabled=True)
        self.clean_button = ft.OutlinedButton(content="Descargar Excel normalizado", icon=ft.Icons.DOWNLOAD, on_click=self.save_improved, disabled=True)
        self.txt_button = ft.FilledButton(content="Descargar TXT Banxico", icon=ft.Icons.DESCRIPTION, on_click=self.save_txt, disabled=True)
        self.zip_button = ft.FilledButton(content="Importar ZIP Banxico y cruzar", icon=ft.Icons.FOLDER_ZIP, on_click=self.import_zips, disabled=True)
        self.final_button = ft.FilledButton(content="Descargar ZIP final", icon=ft.Icons.DOWNLOAD, on_click=self.save_package, disabled=True)
        self.actions = [self.load_button, self.current_button, self.normalize_button, self.clean_button,
                        self.txt_button, self.zip_button, self.final_button]
        self.control = ft.Column([
            ft.Text("CEP Banxico", size=22, weight=ft.FontWeight.BOLD),
            ft.Text("1. Selecciona tus movimientos", size=15, weight=ft.FontWeight.BOLD),
            ft.Text(
                "Acepta Excel antiguos, originales, mejorados o ya cruzados. "
                "Después de corregir Movimientos puedes descargar TXT directamente, "
                "sin volver a normalizar. La descarga del Excel original sigue en Extracción.",
                size=12,
            ),
            ft.Row([self.load_button, self.current_button], wrap=True),
            self.message, self.summary,
            ft.Row([self.normalize_button, self.clean_button], wrap=True),
            ft.Divider(),
            ft.Text("2. Descarga el TXT para Banxico", size=15, weight=ft.FontWeight.BOLD),
            self.adjacent,
            ft.Text(
                "En Movimientos: verde para los datos originales, azul para las seis columnas TXT "
                "y naranja para los resultados CEP. Corrige directamente las columnas azules: "
                "fecha, rastreo, banco emisor, banco receptor, cuenta beneficiaria e importe. "
                "Guarda el XLSX, vuelve a cargarlo y genera TXT directamente.",
                size=12,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            ft.Text(
                "Normalizar clasifica las transferencias y recupera datos SPEI faltantes del concepto. "
                "Puedes filtrar por Clasificación SPEI; revisa los pendientes en Revisión Normalización. "
                "Si el Excel ya contiene columnas TXT, se usan sus valores, incluso tus correcciones. "
                "Los catálogos de bancos y palabras de clasificación están incluidos. "
                "Si hay más de 500 consultas se generan varios TXT.",
                size=12,
            ),
            ft.Row([self.txt_button, ft.TextButton(content="Abrir consulta por lotes en Banxico", on_click=self.open_banxico)], wrap=True),
            ft.Text("Carga los TXT en Banxico y solicita PDF y XML. Después importa aquí los ZIP descargados.", size=12),
            ft.Divider(),
            ft.Text("3. Cruza los comprobantes con tus movimientos", size=15, weight=ft.FontWeight.BOLD),
            ft.Text("Los datos oficiales se añaden al final de cada fila coincidente. Puedes acumular varios ZIP de originales y reintentos.", size=12),
            ft.Row([self.zip_button, self.final_button], wrap=True),
            ft.Text("El ZIP final incluye ambos Excel cruzados y los PDF/XML renombrados. Extrae todo su contenido para abrir cada PDF desde el vínculo del Excel.", size=12),
            self.preview,
        ], spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)

    def refresh(self):
        for button in self.actions:
            button.disabled = self.busy
        self.normalize_button.disabled = self.busy or self.source is None
        self.clean_button.disabled = self.busy or self.bundle is None or not self.normalized
        for button in [self.txt_button, self.zip_button]:
            button.disabled = self.busy or self.bundle is None
        self.final_button.disabled = self.busy or self.bundle is None or not self.evidence.preserved
        self.adjacent.disabled = self.busy
        self.page.update()

    async def perform(self, work, finish):
        if self.busy:
            return
        self.busy = True
        self.message.value = "Procesando…"
        self.message.color = None
        self.refresh()
        try:
            value = await asyncio.to_thread(work)
            finish(value)
        except Exception as error:
            self.message.value = str(error)
            self.message.color = ft.Colors.RED
        finally:
            self.busy = False
            self.refresh()

    def set_bundle(self, bundle):
        queries = queries_from_workbook(bundle.improved)
        self.bundle = bundle
        self.queries = queries
        self.normalized = True
        self.evidence = CepEvidence()
        report = bundle.report
        self.message.value = (f"{bundle.source_name} · Comprobación del Excel terminada: "
                              f"{report.movements} movimientos; {report.dates_resolved} fechas homologadas; "
                              f"{report.dates_review} fechas para revisión; "
                              f"{sum(report.classifications.values())} transferencias clasificadas; "
                              f"{report.metadata_recovered} campos recuperados.")
        self.update_preview()

    def update_preview(self):
        candidates = [q for q in self.queries if q.candidate]
        ready = sum(q.ready for q in candidates)
        matches = match_evidence(self.queries, self.evidence) if self.evidence.preserved else {}
        counts = Counter(v["CEP Estado"] for v in matches.values())
        self.summary.value = f"{len(candidates)} candidatos · {ready} con datos para TXT · {len(candidates) - ready} para revisión"
        if matches:
            self.summary.value += f" · {counts['EXITO'] + counts['EXITO_FECHA_ALTERNATIVA']} con CEP · {counts['REVISAR']} cruces para revisar"
        self.preview.controls = [ft.Text("Vista previa de candidatos (primeros 50; el Excel conserva todos)", size=12, weight=ft.FontWeight.BOLD)]
        for q in candidates[:50]:
            status = matches[q.row]["CEP Estado"] if matches else "LISTO" if q.ready else "NO_CONSULTABLE"
            self.preview.controls.append(ft.Text(
                f"Fila {q.row} · {q.filename} · {q.operation_date or 'Fecha pendiente'} · {q.direction} · "
                f"{q.value or ''} · {q.tracking or 'Sin rastreo'} · {status}"
                + (" · " + "; ".join(q.issues) if q.issues else ""), size=11, selectable=True))

    def set_source(self, source, name="movimientos.xlsx"):
        # Validate and prepare direct queries before switching the UI. Uploaded
        # bytes remain intact; no normalization is required to generate TXT.
        bundle = WorkbookBundle.from_uploaded(source, source_name=name)
        queries = queries_from_workbook(bundle.improved)
        self.source, self.source_name = bundle.original, name
        self.bundle, self.queries = bundle, queries
        self.normalized = bundle.prepared
        self.evidence = CepEvidence()
        self.message.value = (
            f"{name} · {bundle.report.movements} movimientos cargados SIN modificar. "
            + ("TXT listo para generarse desde las columnas azules, sin volver a normalizar."
               if bundle.prepared else "Normalizar prepara las columnas azules. También puedes generar TXT directamente.")
        )
        self.update_preview()

    async def normalize_excel(self, event=None):
        if self.source is None:
            return
        await self.perform(lambda: WorkbookBundle.from_excel(self.source, source_name=self.source_name), self.set_bundle)

    async def use_current(self, event=None):
        if not self.can_use_results():
            self.message.value = "Espera a que termine la extracción o el reprocesado OCR."
            self.page.update()
            return
        snapshot = list(self.get_results())
        if not snapshot:
            self.message.value = "Primero extrae movimientos o carga un Excel."
            self.page.update()
            return
        await self.perform(lambda: original_from_results(snapshot), self.set_source)

    async def load_excel(self, event=None):
        if self.busy:
            return
        files = await ft.FilePicker().pick_files(dialog_title="Selecciona Excel original o mejorado",
            file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=["xlsx"], allow_multiple=False)
        if files and files[0].path:
            path = Path(files[0].path)
            await self.perform(path.read_bytes, lambda source: self.set_source(source, path.name))

    async def save_variant(self, variant):
        if self.busy or self.bundle is None:
            return
        has_ceps = bool(self.evidence.preserved)
        name = f"excel_{variant}" + ("_con_CEP" if has_ceps else "") + ".xlsx"
        path = await ft.FilePicker().save_file(file_name=name, file_type=ft.FilePickerFileType.CUSTOM,
                                               allowed_extensions=["xlsx"])
        if path:
            path = path if path.lower().endswith(".xlsx") else path + ".xlsx"
            source = self.bundle.content(variant)
            def work():
                data = append_cep(source, match_evidence(self.queries, self.evidence), self.queries, self.evidence) if has_ceps else source
                Path(path).write_bytes(data)
            await self.perform(work, lambda _: setattr(self.message, "value", "Excel guardado y comprobado."))

    async def save_improved(self, event):
        await self.save_variant("mejorado")

    async def save_txt(self, event):
        if self.busy or self.bundle is None:
            return
        try:
            files = batch_texts(self.queries, adjacent_days=bool(self.adjacent.value))
        except ValueError as error:
            self.message.value = str(error)
            self.page.update()
            return
        if len(files) == 1:
            path = await ft.FilePicker().save_file(file_name="consultas_banxico.txt",
                file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=["txt"])
            if not path:
                return
            path = path if path.lower().endswith(".txt") else path + ".txt"
            await self.perform(lambda: Path(path).write_bytes(next(iter(files.values()))),
                lambda _: setattr(self.message, "value", "TXT guardado. Súbelo a la consulta por lotes de Banxico."))
        else:
            folder = await ft.FilePicker().get_directory_path(dialog_title="Guardar los TXT Banxico")
            if not folder:
                return
            def work():
                target = Path(tempfile.mkdtemp(prefix="TXT_Banxico_", dir=folder))
                for name, content in files.items():
                    (target / name).write_bytes(content)
                return target
            await self.perform(work, lambda target: setattr(self.message, "value", f"{len(files)} archivos TXT guardados en {target}"))

    async def open_banxico(self, event):
        await self.page.launch_url(BANXICO_BATCH_URL)

    async def import_zips(self, event):
        if self.busy or self.bundle is None:
            return
        files = await ft.FilePicker().pick_files(dialog_title="Selecciona ZIP de resultados Banxico",
            file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=["zip"], allow_multiple=True)
        if not files:
            return
        def work():
            evidence = deepcopy(self.evidence)
            for file in files:
                if file.path:
                    evidence.add_zip(file.path)
            return evidence
        def finish(evidence):
            self.evidence = evidence
            self.message.value = f"{len(evidence.records)} XML CEP leídos; {len(evidence.review)} documentos para revisión."
            self.update_preview()
        await self.perform(work, finish)

    async def save_package(self, event):
        if self.busy or self.bundle is None:
            return
        path = await ft.FilePicker().save_file(file_name="Movimientos_y_CEP.zip",
            file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=["zip"])
        if path:
            path = path if path.lower().endswith(".zip") else path + ".zip"
            await self.perform(lambda: export_cep_zip(self.bundle, self.queries, self.evidence, path),
                lambda _: setattr(self.message, "value", "ZIP final guardado: Excel original y mejorado con CEP, PDF y XML."))
