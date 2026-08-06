"""
Reader genérico de tablas.

Extrae estructuras tabulares
desde PDFs mediante análisis espacial.

No interpreta.
No limpia.
No normaliza.
No modifica valores.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pdfplumber



class PDFTableReader:


    @staticmethod
    def read(
        file_path: str | Path
    ) -> list[list[list[Any]]]:


        file_path = Path(file_path)


        tables = []


        settings = {

            "vertical_strategy": "text",

            "horizontal_strategy": "text",

            "snap_tolerance": 5,

            "join_tolerance": 5,

            "intersection_tolerance": 5,

            "text_tolerance": 3,

        }


        with pdfplumber.open(file_path) as pdf:


            for page in pdf.pages:


                page_tables = page.extract_tables(
                    table_settings=settings
                )


                for table in page_tables:


                    if table:

                        tables.append(
                            table
                        )


        return tables