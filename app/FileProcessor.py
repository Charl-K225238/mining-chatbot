"""
File Processor for handling uploaded documents and data files.

Supports PDF, DOCX, TXT, and Excel files.
Processes and moves to clean directory.
"""

import os
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional
import logging
import json

logger = logging.getLogger(__name__)

class FileProcessor:
    """Classe pour traiter les fichiers chargés."""

    def __init__(self, raw_dir: str = "data/raw", clean_dir: str = "data/clean"):
        self.raw_dir = Path(raw_dir)
        self.clean_dir = Path(clean_dir)
        self.raw_dir.mkdir(exist_ok=True)
        self.clean_dir.mkdir(exist_ok=True)
        # Create subdirs
        for sub in ["pdf", "doc", "txt", "excel"]:
            (self.clean_dir / sub).mkdir(exist_ok=True)
        self.processed_data = {}  # Cache des données traitées

    def save_file(self, uploaded_file, filename: str) -> str:
        """Sauvegarder le fichier uploadé dans raw/."""
        file_path = self.raw_dir / filename
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        logger.info(f"File saved: {file_path}")
        return str(file_path)

    def process_file(self, file_path: str) -> Dict[str, Any]:
        """Traiter un fichier selon son type et le déplacer vers clean/."""
        path = Path(file_path)
        ext = path.suffix.lower()

        processed = None
        if ext == ".pdf":
            processed = self._process_pdf(file_path)
            clean_sub = "pdf"
        elif ext in [".docx", ".doc"]:
            processed = self._process_docx(file_path)
            clean_sub = "doc"
        elif ext == ".txt":
            processed = self._process_txt(file_path)
            clean_sub = "txt"
        elif ext in [".xlsx", ".xls"]:
            processed = self._process_excel(file_path)
            clean_sub = "excel"
        else:
            return {"error": f"Unsupported file type: {ext}"}

        if processed and "error" not in processed:
            # Move to clean directory
            self._move_to_clean(file_path, clean_sub, processed)

        return processed

    def _move_to_clean(self, file_path: str, sub_dir: str, processed: Dict[str, Any]):
        """Déplacer le fichier traité vers le dossier clean approprié."""
        path = Path(file_path)
        filename = path.name

        # Save processed data as JSON in clean subdir
        clean_path = self.clean_dir / sub_dir / f"{path.stem}_processed.json"
        with open(clean_path, "w", encoding="utf-8") as f:
            json.dump(processed, f, ensure_ascii=False, indent=2)

        logger.info(f"Processed file moved to: {clean_path}")

    def _process_pdf(self, file_path: str) -> Dict[str, Any]:
        """Extraire le texte d'un PDF."""
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return {
                "type": "pdf",
                "content": text.strip(),
                "pages": len(reader.pages),
                "filename": Path(file_path).name
            }
        except ImportError:
            return {"error": "PyPDF2 not installed"}
        except Exception as e:
            return {"error": f"PDF processing failed: {e}"}

    def _process_docx(self, file_path: str) -> Dict[str, Any]:
        """Extraire le texte d'un DOCX."""
        try:
            from docx import Document
            doc = Document(file_path)
            text = ""
            for para in doc.paragraphs:
                text += para.text + "\n"
            return {
                "type": "docx",
                "content": text.strip(),
                "filename": Path(file_path).name
            }
        except ImportError:
            return {"error": "python-docx not installed"}
        except Exception as e:
            return {"error": f"DOCX processing failed: {e}"}

    def _process_txt(self, file_path: str) -> Dict[str, Any]:
        """Lire un fichier texte."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return {
                "type": "txt",
                "content": content,
                "filename": Path(file_path).name
            }
        except Exception as e:
            return {"error": f"TXT processing failed: {e}"}

    def _process_excel(self, file_path: str) -> Dict[str, Any]:
        """Traiter un fichier Excel."""
        try:
            xl = pd.ExcelFile(file_path)
            sheets_data = {}
            for sheet_name in xl.sheet_names:
                df = xl.parse(sheet_name)
                # Convertir en dict et gérer la sérialisation JSON
                records = df.to_dict('records')
                # Convertir les objets non sérialisables
                for record in records:
                    for key, value in record.items():
                        if hasattr(value, 'isoformat'):  # Timestamp
                            record[key] = str(value)
                        elif pd.isna(value):  # NaN, NaT
                            record[key] = ""
                sheets_data[sheet_name] = {
                    "columns": list(df.columns),
                    "rows": len(df),
                    "data": records[:100]  # Limiter à 100 lignes
                }
            return {
                "type": "excel",
                "sheets": sheets_data,
                "filename": Path(file_path).name
            }
        except Exception as e:
            return {"error": f"Excel processing failed: {e}"}

    def get_processed_content(self, filename: str) -> Optional[Dict[str, Any]]:
        """Obtenir le contenu traité d'un fichier depuis clean/."""
        # Try to find in clean subdirs
        for sub in ["pdf", "doc", "txt", "excel"]:
            clean_file = self.clean_dir / sub / f"{Path(filename).stem}_processed.json"
            if clean_file.exists():
                try:
                    with open(clean_file, "r", encoding="utf-8") as f:
                        return json.load(f)
                except json.JSONDecodeError as e:
                    logger.error(f"Malformed JSON in {clean_file}: {e}")
                    continue
                except UnicodeDecodeError as e:
                    logger.error(f"Encoding error in {clean_file}: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Error loading processed file {clean_file}: {e}")
                    continue

        # Fallback to raw processing if not in clean
        raw_file = self.raw_dir / filename
        if raw_file.exists():
            return self.process_file(str(raw_file))

        return None

    def list_files(self) -> list:
        """Lister les fichiers dans raw/."""
        return [f.name for f in self.raw_dir.iterdir() if f.is_file()]

    def list_clean_files(self) -> Dict[str, list]:
        """Lister les fichiers traités dans clean/ (seulement les fichiers _processed.json)."""
        clean_files = {}
        for sub in ["pdf", "doc", "txt", "excel"]:
            sub_dir = self.clean_dir / sub
            if sub_dir.exists():
                # Filter to only include processed JSON files to avoid reading binary files
                json_files = [f.name for f in sub_dir.iterdir() 
                             if f.is_file() and f.name.endswith('_processed.json')]
                if json_files:
                    clean_files[sub] = json_files
        return clean_files