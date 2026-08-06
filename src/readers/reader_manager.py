from __future__ import annotations

from pathlib import Path

from readers.models import DocumentData

from .pdf_text_reader import PDFTextReader
from .pdf_table_reader import PDFTableReader
from .pdf_word_reader import PDFWordReader # <-- Importa el nuevo

class ReaderManager:
    @staticmethod
    def read(file_path: str | Path) -> DocumentData:
        raw_text = PDFTextReader.read(file_path)
        tables = PDFTableReader.read(file_path)
        
        # <-- Agrega la extracción espacial
        spatial_words = PDFWordReader.read(file_path) 

        return DocumentData(
            raw_text=raw_text,
            normalized_text="",
            tables=tables,
            spatial_words=spatial_words, # <-- Inyéctalo aquí
            metadata={}
        )