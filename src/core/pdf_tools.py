"""
pdf_tools.py
~~~~~~~~~~~~
Client wrapper for Stirling-PDF (iLovePDF Docker container at http://localhost:8080)
with automatic fallback to local PyMuPDF (fitz) / pypdf libraries.

ON-DEMAND CONTAINER LIFECYCLE:
The container is spun up only when needed (e.g. during heavy PDF compression/merging)
and shut down immediately afterwards to free RAM/CPU resources.

Supported Operations:
1. compress_pdf — Reduce PDF size under target (e.g. GeM 10MB limit)
2. merge_pdfs — Combine multiple PDFs into a single document
3. split_pdf — Split PDF into individual pages
4. start_stirling_pdf_container — Spin up PDF container on-demand
5. stop_stirling_pdf_container — Shut down PDF container to free RAM
"""

import os
import time
import json
import subprocess
import urllib.request
import urllib.parse
from typing import List, Tuple, Optional
from contextlib import contextmanager

STIRLING_URL = os.getenv("STIRLING_PDF_URL", "http://localhost:8080")


def is_stirling_pdf_online() -> bool:
    """Check if Stirling-PDF Docker container is running at http://localhost:8080."""
    try:
        req = urllib.request.Request(f"{STIRLING_URL}/api/v1/info", headers={"User-Agent": "TenderTracker"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def start_stirling_pdf_container(timeout_sec: int = 15) -> bool:
    """
    Spins up the Stirling-PDF Docker container on-demand if it's not already running.
    Waits up to timeout_sec for http://localhost:8080 to respond.
    """
    if is_stirling_pdf_online():
        return True

    try:
        # Try docker compose profile command or docker start
        subprocess.run(
            ["docker", "compose", "--profile", "pdf-tools", "up", "-d", "stirling-pdf"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
        )
    except Exception:
        try:
            subprocess.run(
                ["docker", "start", "tendertracker_pdf"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
            )
        except Exception:
            return False

    # Poll until ready or timeout
    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        if is_stirling_pdf_online():
            return True
        time.sleep(0.5)

    return False


def stop_stirling_pdf_container() -> bool:
    """
    Destroys & removes the Stirling-PDF Docker container immediately after use
    to save 100% of RAM, CPU, and compute resources.
    """
    try:
        subprocess.run(
            ["docker", "compose", "--profile", "pdf-tools", "down"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
        )
        subprocess.run(
            ["docker", "rm", "-f", "tendertracker_pdf"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
        )
        return True
    except Exception:
        return False


@contextmanager
def stirling_pdf_session(auto_stop: bool = True):
    """
    Context manager that starts the Stirling-PDF container on-demand before executing
    PDF operations, and automatically stops it afterwards to release system resources.
    """
    started_by_us = False
    if not is_stirling_pdf_online():
        started_by_us = start_stirling_pdf_container()

    try:
        yield is_stirling_pdf_online()
    finally:
        if started_by_us and auto_stop:
            stop_stirling_pdf_container()


def compress_pdf(input_path: str, output_path: str, target_max_mb: float = 10.0, auto_start_container: bool = True) -> Tuple[bool, str, float]:
    """
    Compress PDF file if its size exceeds target_max_mb.
    Attempts Stirling-PDF REST API first, falling back to local PyMuPDF (fitz).
    
    Returns:
        Tuple[bool, str, float]: (success, output_path, final_size_mb)
    """
    if not os.path.exists(input_path):
        return False, "Input file not found", 0.0

    current_size_mb = os.path.getsize(input_path) / (1024 * 1024)
    if current_size_mb <= target_max_mb:
        if input_path != output_path:
            import shutil
            shutil.copy2(input_path, output_path)
        return True, output_path, current_size_mb

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    # Use on-demand container session if enabled
    with stirling_pdf_session(auto_stop=auto_start_container):
        if is_stirling_pdf_online():
            try:
                import requests
                url = f"{STIRLING_URL}/api/v1/misc/compress-pdf"
                with open(input_path, "rb") as f:
                    files = {"fileInput": f}
                    data = {"optimizeLevel": "2"}
                    resp = requests.post(url, files=files, data=data, timeout=35)
                    if resp.status_code == 200 and len(resp.content) > 100:
                        with open(output_path, "wb") as out_f:
                            out_f.write(resp.content)
                        out_size = os.path.getsize(output_path) / (1024 * 1024)
                        return True, output_path, out_size
            except Exception:
                pass

    # Fallback to local PyMuPDF (fitz) compression
    try:
        import fitz
        doc = fitz.open(input_path)
        doc.save(
            output_path,
            garbage=4,
            deflate=True,
            deflate_images=True,
            deflate_fonts=True,
            clean=True
        )
        doc.close()
        out_size = os.path.getsize(output_path) / (1024 * 1024)
        return True, output_path, out_size
    except Exception as e:
        return False, f"Compression failed: {e}", current_size_mb


def merge_pdfs(pdf_paths: List[str], output_path: str, auto_start_container: bool = True) -> Tuple[bool, str]:
    """
    Merge multiple PDF files into a single PDF document.
    Attempts Stirling-PDF API first, falling back to local PyMuPDF / pypdf.
    """
    valid_paths = [p for p in pdf_paths if p and os.path.exists(p)]
    if not valid_paths:
        return False, "No valid input PDF files provided"

    if len(valid_paths) == 1:
        import shutil
        shutil.copy2(valid_paths[0], output_path)
        return True, output_path

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    with stirling_pdf_session(auto_stop=auto_start_container):
        if is_stirling_pdf_online():
            try:
                import requests
                url = f"{STIRLING_URL}/api/v1/general/merge-pdfs"
                files = [("fileInput", (os.path.basename(p), open(p, "rb"), "application/pdf")) for p in valid_paths]
                resp = requests.post(url, files=files, timeout=45)
                for _, f_obj, _ in files:
                    f_obj.close()
                if resp.status_code == 200 and len(resp.content) > 100:
                    with open(output_path, "wb") as out_f:
                        out_f.write(resp.content)
                    return True, output_path
            except Exception:
                pass

    # Fallback to local PyMuPDF (fitz)
    try:
        import fitz
        merged_doc = fitz.open()
        for p in valid_paths:
            src_doc = fitz.open(p)
            merged_doc.insert_pdf(src_doc)
            src_doc.close()
        merged_doc.save(output_path, garbage=4, deflate=True)
        merged_doc.close()
        return True, output_path
    except Exception:
        pass

    # Fallback to local pypdf
    try:
        import pypdf
        writer = pypdf.PdfWriter()
        for p in valid_paths:
            writer.append(p)
        with open(output_path, "wb") as out_f:
            writer.write(out_f)
        return True, output_path
    except Exception as e:
        return False, f"Merge failed: {e}"


def split_pdf(input_path: str, output_dir: str) -> List[str]:
    """
    Split a multi-page PDF into single page PDF files inside output_dir.
    """
    if not os.path.exists(input_path):
        return []

    os.makedirs(output_dir, exist_ok=True)
    generated_files = []

    try:
        import fitz
        doc = fitz.open(input_path)
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        for page_num in range(len(doc)):
            page_doc = fitz.open()
            page_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
            out_file = os.path.join(output_dir, f"{base_name}_page_{page_num+1}.pdf")
            page_doc.save(out_file)
            page_doc.close()
            generated_files.append(out_file)
        doc.close()
    except Exception:
        pass

    return generated_files
