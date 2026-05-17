"""Extracción de texto desde PDFs.

Estrategia: PyMuPDF primero (rápido, bueno para PDFs digitales). Si extrae
menos texto que un umbral, intentamos Tika como fallback (mejor para
PDFs escaneados que ya pasaron por OCR aguas arriba).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pymupdf  # type: ignore[import-untyped]

from .logging import get_logger

log = get_logger("sabueso.pipeline.extract")

MIN_CHARS_PYMUPDF = 200  # debajo de esto disparamos fallback


@dataclass(slots=True)
class ExtractResult:
    text: str
    pages: int
    method: str  # 'pymupdf' | 'tika' | 'empty'


def _normalize_whitespace(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_pymupdf(pdf_path: str | Path) -> ExtractResult:
    doc = pymupdf.open(str(pdf_path))
    try:
        chunks: list[str] = []
        for page in doc:
            chunks.append(page.get_text("text"))
        text = _normalize_whitespace("\n\n".join(chunks))
        return ExtractResult(text=text, pages=doc.page_count, method="pymupdf")
    finally:
        doc.close()


def _tika_available() -> bool:
    return shutil.which("java") is not None and bool(os.environ.get("TIKA_JAR"))


def extract_tika(pdf_path: str | Path) -> ExtractResult:
    """Llama a tika-app.jar (TIKA_JAR env var apunta al jar).

    Fallback puramente opcional: si el jar no está disponible, devolvemos
    el resultado de PyMuPDF aunque sea pobre, en lugar de fallar.
    """
    tika_jar = os.environ.get("TIKA_JAR")
    if not tika_jar:
        log.warning("extract.tika_unavailable", reason="TIKA_JAR no configurado")
        return extract_pymupdf(pdf_path)
    with tempfile.NamedTemporaryFile(mode="r", suffix=".txt", delete=False) as out:
        out_path = out.name
    try:
        cp = subprocess.run(
            ["java", "-jar", tika_jar, "--text", str(pdf_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if cp.returncode != 0:
            log.warning("extract.tika_failed", stderr=cp.stderr[:500])
            return extract_pymupdf(pdf_path)
        text = _normalize_whitespace(cp.stdout)
        # Pages: tika no las reporta en --text. Reusamos pymupdf rápido.
        try:
            doc = pymupdf.open(str(pdf_path))
            pages = doc.page_count
            doc.close()
        except Exception:
            pages = 0
        return ExtractResult(text=text, pages=pages, method="tika")
    finally:
        Path(out_path).unlink(missing_ok=True)


def extract(pdf_path: str | Path) -> ExtractResult:
    """Estrategia mixta. Tries PyMuPDF; si parece imagen escaneada, prueba Tika."""
    try:
        result = extract_pymupdf(pdf_path)
    except Exception as e:
        log.warning("extract.pymupdf_failed", path=str(pdf_path), error=str(e))
        result = ExtractResult(text="", pages=0, method="empty")
    if len(result.text) < MIN_CHARS_PYMUPDF and _tika_available():
        log.info("extract.tika_fallback", path=str(pdf_path), pymupdf_chars=len(result.text))
        try:
            result = extract_tika(pdf_path)
        except Exception as e:
            log.warning("extract.tika_error", error=str(e))
    return result
