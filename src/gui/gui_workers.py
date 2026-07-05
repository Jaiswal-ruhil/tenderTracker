import os
import re
import threading
import time
import asyncio
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pypdf
from concurrent.futures import ThreadPoolExecutor, as_completed

# Local imports
from config import (
    BG, PANEL, CARD, ACCENT, ACCENT2, MUTED, TEXT, TEXTSUB, SUCCESS, ERR, WARN, SEL_BG,
    FL, FB, FH, FT, TV_IDS
)
import db
import logger as _logger
from parser import split_blocks, parse_one, convert_pdf_text_to_markdown
from scraper import scrape_bid_page, _try_import_selenium, download_tender_pdf, scrape_portal_search
from vector_search import start_background_embedding_worker, pause_background_embedder, resume_background_embedder
import llm as _llm_module

_selenium_semaphore = threading.Semaphore(1)

def _block_dedupe_key(blk):
    cleaned = blk.strip().strip('"\'')
    m = re.search(r"GEM/\d{4}/[A-Z0-9]+/\d+", cleaned, re.I)
    if m:
        return m.group(0).upper()
    if "showbidDocument" in cleaned:
        return cleaned.rstrip("/").split("/")[-1]
    if cleaned.lower().endswith(".pdf"):
        if os.path.exists(cleaned):
            return os.path.normcase(os.path.abspath(cleaned))
        return cleaned.lower()
    return cleaned[:120]


def _parse_item_timeout(blk, settings):
    if blk.lower().endswith(".pdf"):
        return 60.0
    provider = settings.get("llm_provider", "Disabled")
    if provider != "Disabled" and settings.get("llm_use_parsing", False):
        return 180.0
    cleaned = blk.strip()
    if "showbidDocument" in cleaned or re.search(r"^GEM/\d{4}/", cleaned, re.I):
        return 120.0
    return 45.0


def _format_eta(seconds):
    if seconds <= 0:
        return "0s left"
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    if mins > 0:
        return f"~{mins}m {secs}s left"
    return f"~{secs}s left"


class WorkersMixin:
    def _do_parse(self, force_llm=None):
        raw = self.paste_txt.get("1.0","end").strip()
        if not raw: self._log("warn","Paste area is empty."); return
        
        # Pre-warm local LLM if enabled before starting the background parse worker
        settings = db.load_settings()
        provider = settings.get("llm_provider", "Disabled")
        if force_llm is not None:
            use_llm_parsing = force_llm
        else:
            use_llm_parsing = settings.get("llm_use_parsing", False)

        if force_llm and provider == "Disabled":
            messagebox.showwarning(
                "LLM Provider Disabled",
                "LLM provider is currently disabled. Please enable and configure an LLM provider in Settings first.",
                parent=self
            )
            return

        if provider == "Local LLM (LM Studio / Ollama)" and use_llm_parsing:
            api_key = settings.get("llm_api_key", "")
            base_url = settings.get("llm_base_url", "")
            model = settings.get("llm_model", "")
            
            from gui_dialogs import LoadingDialog
            def perform_prewarm():
                return _llm_module.prepare_local_llm(base_url, model, api_key)
                
            self._log("info", "Pre-warming local LLM...")
            dlg = LoadingDialog(self, "Pre-warming LLM", "Connecting to local LLM server and loading model...", perform_prewarm)
            self.wait_window(dlg)
            
            if dlg.exception:
                self._log("err", f"Local LLM pre-warm failed: {dlg.exception}")
            elif dlg.result:
                ok, msg = dlg.result
                level = "ok" if ok else "warn"
                self._log(level, f"Local LLM pre-warm: {msg}")

        self._log("info", f"--- Parse started {datetime.now().strftime('%H:%M:%S')} ---")
        self._set_prog(0,"Processing input…")
        _t0 = _logger.log_worker_start("ParseWorker")
 
        def worker():
            pause_background_embedder()
            try:
                settings = db.load_settings()
                provider = settings.get("llm_provider", "Disabled")
                if force_llm is not None:
                    use_llm_parsing = force_llm
                else:
                    use_llm_parsing = settings.get("llm_use_parsing", False)
                api_key = settings.get("llm_api_key", "")
                base_url = settings.get("llm_base_url", "")
                model = settings.get("llm_model", "")

                # Step 1: Split raw text into initial blocks.
                initial_blocks = split_blocks(raw)
                
                # Process each block from split_blocks:
                # If it starts with a BID NO label, process it as a single block.
                # Otherwise, split it by lines (handling lists of PDF paths, URLs, or raw bid numbers).
                blocks_to_process = []
                for blk in initial_blocks:
                    if re.match(r"^\s*BID\s*(?:NO|Number)(?:\.|\b)\s*:", blk, re.I):
                        blocks_to_process.append(blk)
                    else:
                        for line in blk.splitlines():
                            ln = line.strip().strip('"\'')
                            if ln:
                                blocks_to_process.append(ln)

                seen_keys = set()
                deduped_blocks = []
                for blk in blocks_to_process:
                    key = _block_dedupe_key(blk)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    deduped_blocks.append(blk)
                removed = len(blocks_to_process) - len(deduped_blocks)
                if removed:
                    self.after(0, lambda n=removed: self._log("info", f"Removed {n} duplicate item(s)."))
                blocks_to_process = deduped_blocks
                    
                total = len(blocks_to_process)
                self._log("info", f"Found {total} item(s) to process.")
                
                recs = []
                completed_count = 0
                self.after(0, lambda: self._set_prog(0, f"Processed 0/{total}…"))
                if provider != "Disabled" and use_llm_parsing:
                    max_workers = settings.get("llm_max_parallel", 8)
                else:
                    max_workers = 3

                def process_one(i, blk):
                    # Check if block is a local PDF path on disk
                    if blk.lower().endswith(".pdf"):
                        if os.path.exists(blk):
                            self.after(0, lambda f=blk: self._log("info", f"[{i}/{total}] Reading PDF: {os.path.basename(f)}"))
                            try:
                                reader = pypdf.PdfReader(blk)
                                pdf_text = ""
                                for page in reader.pages:
                                    t = page.extract_text()
                                    if t:
                                        pdf_text += t + "\n"
                                md_text = convert_pdf_text_to_markdown(pdf_text)
                                if provider != "Disabled" and use_llm_parsing:
                                    self.after(0, lambda: self._log("info", f"[{i}/{total}] Parsing PDF using LLM..."))
                                    try:
                                        rec = _llm_module.llm_parse_tender(md_text, provider, api_key, base_url, model)
                                    except Exception as ex:
                                        self.after(0, lambda: self._log("err", f"LLM parsing failed for PDF, falling back to regex: {ex}"))
                                        rec = parse_one(md_text)
                                else:
                                    rec = parse_one(md_text)
                                if rec.get("bid_no"):
                                    rec["pdf_path"] = os.path.abspath(blk)
                                    self.after(0, lambda b=rec['bid_no']: self._log("ok", f"Parsed PDF {b}"))
                                    return rec
                                else:
                                    self.after(0, lambda f=blk: self._log("warn", f"Failed to find Bid Number in PDF: {os.path.basename(f)}"))
                            except Exception as ex:
                                self.after(0, lambda f=blk, err=ex: self._log("err", f"Failed to read PDF {os.path.basename(f)}: {err}"))
                            return None
                        else:
                            self.after(0, lambda: self._log("warn", f"SKIP — PDF file does not exist on disk: {blk}"))
                            return None
                    
                    # Parse block
                    rec = None
                    if provider != "Disabled" and use_llm_parsing:
                        self.after(0, lambda: self._log("info", f"[{i}/{total}] Parsing text block using LLM..."))
                        try:
                            rec = _llm_module.llm_parse_tender(blk, provider, api_key, base_url, model)
                        except Exception as ex:
                            self.after(0, lambda err=ex: self._log("err", f"LLM parsing failed: {err}. Falling back to Regex."))
                            rec = parse_one(blk)
                    else:
                        rec = parse_one(blk)

                    bid_no = rec.get("bid_no")
                    bid_url = rec.get("bid_url")
                    
                    if not bid_no and not bid_url:
                        # Try to reconstruct from raw line if it's a URL or Bid Number
                        cleaned_blk = blk.strip().strip('"\'')
                        line_val = re.sub(r"^(?:BID\s*(?:NO|Number)(?:\.|\b)\s*:\s*)", "", cleaned_blk, flags=re.I).strip()
                        line_val = re.sub(r"\s+View\s+Corrigendum.*$", "", line_val, flags=re.I).strip()
                        
                        if "showbidDocument" in cleaned_blk:
                            bid_url = cleaned_blk
                            doc_id = cleaned_blk.rstrip('/').split('/')[-1]
                            bid_no = f"GEM/2026/B/{doc_id}"
                        elif re.match(r"^GEM/\d{4}/[A-Z0-9]+/\d+$", line_val, re.I):
                            bid_no = line_val
                        else:
                            snippet = blk.strip().replace("\n", " ")
                            if len(snippet) > 40:
                                snippet = snippet[:40] + "..."
                            self.after(0, lambda: self._log("warn", f"SKIP — No valid Bid Number or URL found in block: \"{snippet}\""))
                            return None
                    
                    # Check if it is in Don't Wants
                    id_to_check = bid_no if bid_no else bid_url
                    dont_want_rec = self._is_bid_in_dont_wants(id_to_check)
                    if dont_want_rec:
                        end_date_val = dont_want_rec.get("end_date")
                        date_str = f" (End Date: {end_date_val})" if end_date_val else ""
                        self.after(0, lambda d_str=date_str: self._log("info", f"Skipping {id_to_check}{d_str}: Already in database 'Don't Wants'"))
                        return None
                    
                    # Determine if we need to download the PDF:
                    has_details = any(rec.get(k) for k in ("items", "dept", "start_date", "end_date", "ministry", "category"))
                    
                    if not has_details:
                        # Need details. Check if we already have it fully parsed in database records
                        existing_rec = None
                        for r in self._records:
                            if bid_no and r.get("bid_no") == bid_no:
                                existing_rec = r
                                break
                            if bid_url and r.get("bid_url") == bid_url:
                                existing_rec = r
                                break
                                
                        if existing_rec and any(existing_rec.get(k) for k in ("items", "dept", "start_date")):
                            self.after(0, lambda: self._log("info", f"Using existing database details for {bid_no}"))
                            return existing_rec
                        else:
                            self.after(0, lambda: self._log("info", f"Downloading PDF to fetch details for {bid_no or bid_url}..."))
                            try:
                                dl_dir = os.path.dirname(db.DB_FILE)
                                dest_path = None
                                
                                with _selenium_semaphore:
                                    if bid_url and "showbidDocument" in bid_url:
                                        headless_opt = db.load_settings().get("selenium_headless", False)
                                        dest_path = download_tender_pdf(bid_url, dl_dir, log_fn=self._log, headless=headless_opt)
                                    elif bid_no:
                                        headless_opt = db.load_settings().get("selenium_headless", False)
                                        dest_path = download_tender_pdf(bid_no, dl_dir, log_fn=self._log, headless=headless_opt)
                                    
                                if dest_path and os.path.exists(dest_path):
                                    self.after(0, lambda: self._log("ok", f"PDF downloaded successfully for {bid_no}. Parsing..."))
                                    reader = pypdf.PdfReader(dest_path)
                                    pdf_text = ""
                                    for page in reader.pages:
                                        t = page.extract_text()
                                        if t:
                                            pdf_text += t + "\n"
                                    md_text = convert_pdf_text_to_markdown(pdf_text)
                                    if provider != "Disabled" and use_llm_parsing:
                                        self.after(0, lambda: self._log("info", f"Parsing downloaded PDF using LLM..."))
                                        try:
                                            pdf_rec = _llm_module.llm_parse_tender(md_text, provider, api_key, base_url, model)
                                        except Exception as ex:
                                            self.after(0, lambda: self._log("err", f"LLM parsing failed for downloaded PDF, falling back to regex: {ex}"))
                                            pdf_rec = parse_one(md_text)
                                    else:
                                        pdf_rec = parse_one(md_text)
                                    if bid_url and "bid_url" not in pdf_rec:
                                        pdf_rec["bid_url"] = bid_url
                                    pdf_rec["pdf_path"] = os.path.abspath(dest_path)
                                    msg = (
                                        f"--- Parsing Block ---\n"
                                        f"Input File: {os.path.basename(dest_path)}\n"
                                        f"----->\n"
                                        f"Parsed Output:\n"
                                        f"  - Bid No: {pdf_rec.get('bid_no', 'N/A')}\n"
                                        f"  - Items: {pdf_rec.get('items', 'N/A')}\n"
                                        f"  - Qty: {pdf_rec.get('quantity', 'N/A')}\n"
                                        f"  - Dept: {pdf_rec.get('dept', 'N/A')}\n"
                                        f"  - End Date: {pdf_rec.get('end_date', 'N/A')}"
                                    )
                                    self.after(0, lambda m=msg: self._log("ok", m))
                                    return pdf_rec
                                else:
                                    self.after(0, lambda: self._log("err", f"Failed to download PDF for {bid_no or bid_url}"))
                                    if not rec.get("bid_no") and bid_no:
                                        rec["bid_no"] = bid_no
                                    if not rec.get("bid_url") and bid_url:
                                        rec["bid_url"] = bid_url
                                    return rec
                            except Exception as dl_err:
                                self.after(0, lambda: self._log("err", f"Error downloading PDF for {bid_no}: {dl_err}"))
                                return rec
                    else:
                        msg = (
                            f"--- Parsing Block ---\n"
                            f"Input Block:\n{blk.strip()}\n"
                            f"----->\n"
                            f"Parsed Output:\n"
                            f"  - Bid No: {rec.get('bid_no', 'N/A')}\n"
                            f"  - Items: {rec.get('items', 'N/A')}\n"
                            f"  - Qty: {rec.get('quantity', 'N/A')}\n"
                            f"  - Dept: {rec.get('dept', 'N/A')}\n"
                            f"  - End Date: {rec.get('end_date', 'N/A')}"
                        )
                        self.after(0, lambda m=msg: self._log("ok", m))
                        return rec
                stats = {"added": 0, "updated": 0}
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {executor.submit(process_one, idx, blk): (idx, blk) for idx, blk in enumerate(blocks_to_process, 1)}
                    for fut in as_completed(futures):
                        idx, blk = futures[fut]
                        timeout = _parse_item_timeout(blk, settings)
                        try:
                            res_rec = fut.result(timeout=timeout)
                            if res_rec:
                                recs.append(res_rec)
                        except TimeoutError:
                            label = os.path.basename(blk) if blk.lower().endswith(".pdf") else blk[:40]
                            self.after(0, lambda fn=label, t=timeout, i=idx: self._log("err", f"[{i}/{total}] Timed out after {int(t)}s (skipped): {fn}"))
                        except Exception as e:
                            label = os.path.basename(blk) if blk.lower().endswith(".pdf") else blk[:40]
                            self.after(0, lambda fn=label, err=e, i=idx: self._log("err", f"[{i}/{total}] Failed (skipped): {fn}: {err}"))
                        
                        completed_count += 1
                        prog_val = int(completed_count / total * 100)
                        
                        elapsed = time.monotonic() - _t0
                        avg_time = elapsed / completed_count
                        rem_sec = avg_time * (total - completed_count)
                        eta_str = _format_eta(rem_sec)
                        
                        self.after(0, lambda p=prog_val, c=completed_count, eta=eta_str: self._set_prog(p, f"Processed {c}/{total} ({eta})…"))

                # Step 2: Run AI Reasoning & Classification on the structured + unstructured data
                if recs and provider != "Disabled":
                    self.after(0, lambda: self._log("info", f"Running AI Reasoning & Classification on {len(recs)} parsed tender(s) using local LLM..."))
                    try:
                        from llm_client import LMStudioClient
                        client = LMStudioClient()
                        import warnings
                        old_loop = None
                        try:
                            with warnings.catch_warnings():
                                warnings.simplefilter("ignore", DeprecationWarning)
                                old_loop = asyncio.get_event_loop()
                        except Exception:
                            pass
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            # Batch process with the async client (caching matches automatically)
                            classified_results = loop.run_until_complete(client.classify_bids_batch(recs))
                            classified_by_bid = {res.bid_no: res for res in classified_results if res}
                            for r in recs:
                                bid_no = r.get("bid_no")
                                if bid_no in classified_by_bid:
                                    res = classified_by_bid[bid_no]
                                    r["is_want_derived"] = 1 if res.recommended else 0
                                    r["remarks"] = f"AI Classification: {res.category} / {res.subcategory}\nRelevance Score: {res.confidence}\nSummary: {res.summary}"
                        finally:
                            loop.run_until_complete(client.close())
                            loop.close()
                            asyncio.set_event_loop(old_loop)
                    except Exception as llm_err:
                        self.after(0, lambda err=llm_err: self._log("warn", f"AI classification failed: {err}"))

                # Step 3: Add to UI table view
                for r in recs:
                    self.after(0, lambda r_item=r: self._add_single_row_immediate(r_item, stats))

                # Step 4: Save final structured data to SQLite database
                if recs:
                    try:
                        db.upsert_tenders(recs)
                    except Exception as db_err:
                        self.after(0, lambda err=db_err: self._log("err", f"Failed to save tenders to database: {err}"))
                self.after(0, lambda: self._finalize_parse(recs, stats, total, _t0))
            finally:
                resume_background_embedder()
        threading.Thread(target=worker, daemon=True).start()

    def _add_single_row_immediate(self, rec, stats):
        bid_no = rec.get("bid_no")
        bid_url = rec.get("bid_url")
        if not bid_no and not bid_url:
            return
            
        settings = db.load_settings()
        inc_raw = settings.get("include_keywords", "")
        exc_raw = settings.get("exclude_keywords", "")
        inc_kws = [k.strip().lower() for k in inc_raw.split(",") if k.strip()]
        exc_kws = [k.strip().lower() for k in exc_raw.split(",") if k.strip()]
        
        children = self.tv.get_children()
        existing_iid = None
        existing_rec = None

        # Find existing record in memory first
        for r in self._records:
            if (bid_no and r.get("bid_no") == bid_no) or (bid_url and r.get("bid_url") == bid_url):
                existing_rec = r
                break

        # If the record exists, find its corresponding treeview item
        if existing_rec:
            target_bid_no = existing_rec.get("bid_no")
            target_bid_url = existing_rec.get("bid_url")
            for iid in children:
                b_no = self.tv.set(iid, "bid_no")
                if target_bid_no and b_no == target_bid_no:
                    existing_iid = iid
                    break
                # Fallback: if row has no bid_no, resolve its url via self._records to match
                if not b_no and target_bid_url:
                    row_url = ""
                    for r_cand in self._records:
                        if not r_cand.get("bid_no") and r_cand.get("items") == self.tv.set(iid, "items"):
                            row_url = r_cand.get("bid_url") or ""
                            break
                    if row_url == target_bid_url:
                        existing_iid = iid
                        break

        if existing_rec and existing_iid:
            merged_fields = []
            for k, v in rec.items():
                if v and (k not in existing_rec or not str(existing_rec[k]).strip()):
                    existing_rec[k] = v
                    if k in TV_IDS:
                        self.tv.set(existing_iid, k, v)
                    merged_fields.append(k)
            if merged_fields:
                stats["updated"] += 1
                self.tv.item(existing_iid, tags=("fetched",))
                self._log("ok", f"Updated {bid_no or bid_url} with {len(merged_fields)} new fields")
        else:
            is_want = self._get_tender_status(rec, inc_kws, exc_kws)
            rec["is_want_derived"] = is_want
            self._records.append(rec)
            self._tv_insert(rec)
            stats["added"] += 1
            
            if is_want:
                self._log("ok", f"Added {bid_no or bid_url} to database (matches Wants)")
                self._show_toast("New Want Tender Match!", f"{bid_no or 'GEM Bid'}: {rec.get('items', '')[:35]}...", "ok")
            else:
                self._log("info", f"Added {bid_no or bid_url} to database (Don't Want / Filtered)")

        # Refresh Kanban if active
        try:
            self._update_kanban()
        except Exception:
            pass

    def _finalize_parse(self, recs, stats, total, start_time):
        added_count = stats.get("added", 0)
        updated_count = stats.get("updated", 0)
        skipped = total - (added_count + updated_count)
        
        elapsed = time.monotonic() - start_time
        avg_time = elapsed / total if total > 0 else 0
        avg_str = f"{avg_time:.2f}s" if avg_time >= 1.0 else f"{avg_time * 1000:.0f}ms"
        
        msg = f"Parsed {total} block(s): {added_count} added"
        if updated_count:
            msg += f", {updated_count} updated"
        if skipped > 0:
            msg += f", {skipped} skipped"
        msg += f" (Avg: {avg_str}/block)"
            
        self._log("info", msg)
        self._set_status(msg, SUCCESS if (added_count or updated_count) else WARN)
        self._set_prog(100, "Done.")
        if recs:
            self.paste_txt.delete("1.0", "end")
            
        # Rebuild vector search index
        start_background_embedding_worker(callback_fn=self._refresh_table_view)
        
        try:
            if self.notebook.index(self.notebook.select()) == 1:
                self._update_calendar()
                self._update_details()
        except Exception:
            pass



    def _do_fetch_all(self):
        """Fetch details for ALL records that have a bid_url."""
        targets = [(i, r) for i,r in enumerate(self._records) if r.get("bid_url")]
        self._run_fetch(targets, "all")

    def _do_fetch_sel(self):
        """Fetch details for SELECTED rows only."""
        sel = self.tv.selection()
        if not sel:
            self._log("warn","No rows selected."); return
        targets = []
        for iid in sel:
            bid_no = self.tv.set(iid, "bid_no")
            if bid_no:
                for idx, r in enumerate(self._records):
                    if r.get("bid_no") == bid_no and r.get("bid_url"):
                        targets.append((idx, r))
                        break
        if not targets:
            self._log("warn","Selected rows have no Bid URL."); return
        self._run_fetch(targets, "selected")

    def _run_fetch(self, targets, label):
        if self._fetch_running:
            self._log("warn","A fetch is already running. Please wait."); return
        if not targets:
            self._log("warn","No rows with Bid URL to fetch."); return

        if not _try_import_selenium():
            messagebox.showerror("Missing library",
                "Please install Selenium:\n\npip install selenium webdriver-manager")
            return

        self._fetch_running = True
        self._log("info", f"--- Selenium fetch started: {len(targets)} {label} row(s) ---")
        self._set_prog(0, f"Fetching 0/{len(targets)}…")

        iid_map = {self.tv.set(iid, "bid_no"): iid for iid in self.tv.get_children() if self.tv.set(iid, "bid_no")}

        def worker():
            total = len(targets)
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            _t0 = time.monotonic()
            completed_count = 0
            
            def fetch_one(idx, rec):
                bid = rec.get("bid_no","?")
                iid = iid_map.get(bid)
                url = rec["bid_url"]
                
                self.after(0, lambda: self._log("info", f"Fetching details for {bid}"))
                if iid: self.after(0, lambda i=iid: self.tv.item(i, tags=("fetching",)))
                
                extra = None
                try:
                    headless_opt = db.load_settings().get("selenium_headless", False)
                    with _selenium_semaphore:
                        extra = scrape_bid_page(url, log_fn=self._log, headless=headless_opt)
                except Exception as ex:
                    self.after(0, lambda b=bid, err=ex: self._log("err", f"Selenium scraping error for {b}: {err}"))
                    
                # LLM Rescue if Selenium failed or returned incomplete/empty results
                if not extra:
                    try:
                        settings = db.load_settings()
                        provider = settings.get("llm_provider", "Disabled")
                        if provider != "Disabled":
                            self.after(0, lambda: self._log("info", f"Selenium failed. Attempting LLM rescue via PDF download for {bid}..."))
                            dl_dir = os.path.dirname(db.DB_FILE)
                            with _selenium_semaphore:
                                pdf_path = download_tender_pdf(url, dl_dir, log_fn=self._log, headless=headless_opt)
                            if pdf_path and os.path.exists(pdf_path):
                                reader = pypdf.PdfReader(pdf_path)
                                pdf_text = ""
                                for page in reader.pages:
                                    t = page.extract_text()
                                    if t:
                                        pdf_text += t + "\n"
                                md_text = convert_pdf_text_to_markdown(pdf_text)
                                import llm
                                api_key = settings.get("llm_api_key", "")
                                base_url = settings.get("llm_base_url", "")
                                model = settings.get("llm_model", "")
                                parsed = llm.llm_parse_tender(md_text, provider, api_key, base_url, model)
                                if parsed and isinstance(parsed, dict) and parsed.get("bid_no"):
                                    extra = parsed
                                    rec["pdf_path"] = os.path.abspath(pdf_path)
                    except Exception as rescue_err:
                        self.after(0, lambda b=bid, err=rescue_err: self._log("err", f"LLM rescue failed for {b}: {err}"))
                
                if extra:
                    rec.update(extra)
                    rec["is_fetched"] = True
                    
                    def update_tv(i=iid, r=rec, e=extra):
                        if i:
                            for cid in TV_IDS:
                                if cid in r:
                                    self.tv.set(i, cid, r[cid])
                            self.tv.item(i, tags=("fetched",))
                        db.upsert_tender(r)
                        
                    self.after(0, update_tv)
                    self.after(0, lambda e_len=len(extra): self._log("ok", f"{bid} — merged {e_len} extra fields"))
                else:
                    if iid: self.after(0, lambda i=iid: self.tv.item(i, tags=()))
                    self.after(0, lambda: self._log("warn", f"{bid} — no extra data scraped"))

            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = {executor.submit(fetch_one, idx, rec): rec for idx, rec in targets}
                for fut in as_completed(futures):
                    completed_count += 1
                    prog_val = int(completed_count / total * 100)
                    
                    elapsed = time.monotonic() - _t0
                    avg_time = elapsed / completed_count
                    rem_sec = avg_time * (total - completed_count)
                    eta_str = _format_eta(rem_sec)
                    
                    self.after(0, lambda p=prog_val, c=completed_count, eta=eta_str: self._set_prog(p, f"Fetched {c}/{total} ({eta})…"))
                    
            # Run AI Reasoning & Classification on the fetched structured + unstructured data
            fetched_recs = [rec for idx, rec in targets if rec.get("is_fetched")]
            settings = db.load_settings()
            provider = settings.get("llm_provider", "Disabled")
            if fetched_recs and provider != "Disabled":
                self.after(0, lambda: self._log("info", f"Running AI Reasoning & Classification on {len(fetched_recs)} fetched tender(s) using local LLM..."))
                try:
                    from llm_client import LMStudioClient
                    client = LMStudioClient()
                    import warnings
                    old_loop = None
                    try:
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore", DeprecationWarning)
                            old_loop = asyncio.get_event_loop()
                    except Exception:
                        pass
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        # Batch process with the async client
                        classified_results = loop.run_until_complete(client.classify_bids_batch(fetched_recs))
                        classified_by_bid = {res.bid_no: res for res in classified_results if res}
                        for r in fetched_recs:
                            bid_no = r.get("bid_no")
                            if bid_no in classified_by_bid:
                                res = classified_by_bid[bid_no]
                                r["is_want_derived"] = 1 if res.recommended else 0
                                r["remarks"] = f"AI Classification: {res.category} / {res.subcategory}\nRelevance Score: {res.confidence}\nSummary: {res.summary}"
                                
                                # Update UI and Database with final LLM result
                                iid = iid_map.get(bid_no)
                                def update_llm_fields(i=iid, rec_item=r):
                                    if i:
                                        self.tv.set(i, "remarks", rec_item["remarks"])
                                        # Force a cell tag update in treeview if status changed
                                        is_want = rec_item.get("is_want_derived", 0)
                                        # Use standard wants keywords checks to derive tag style or custom AI tag
                                        # but keep fetched tag as base or alternative
                                    db.upsert_tender(rec_item)
                                self.after(0, update_llm_fields)
                    finally:
                        loop.run_until_complete(client.close())
                        loop.close()
                        asyncio.set_event_loop(old_loop)
                except Exception as llm_err:
                    self.after(0, lambda err=llm_err: self._log("warn", f"AI classification failed: {err}"))

            self._fetch_running = False
            self.after(0, lambda: self._set_prog(100, "Fetch complete."))
            msg = f"Selenium fetch done: {total} URL(s) processed"
            self.after(0, lambda: self._log("info", f"--- {msg} ---"))
            start_background_embedding_worker(callback_fn=self._refresh_table_view)
            
            # Show toast when fetch is done
            self._show_toast("Detail Fetching Complete", f"Successfully processed {total} URL(s).", "info")
            
            def fetch_finished():
                self._set_status(msg, SUCCESS)
                try:
                    if self.notebook.index(self.notebook.select()) == 1:
                        self._update_calendar()
                        self._update_details()
                except:
                    pass
            self.after(0, fetch_finished)

        threading.Thread(target=worker, daemon=True).start()
