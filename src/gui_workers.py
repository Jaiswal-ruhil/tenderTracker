import os
import re
import threading
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
from parser import split_blocks, parse_one, convert_pdf_text_to_markdown
from scraper import scrape_bid_page, _try_import_selenium, download_tender_pdf, scrape_portal_search

class WorkersMixin:
    def _do_parse(self):
        raw = self.paste_txt.get("1.0","end").strip()
        if not raw: self._log("warn","Paste area is empty."); return
        self._log("info", f"--- Parse started {datetime.now().strftime('%H:%M:%S')} ---")
        self._set_prog(0,"Processing input…")

        def worker():
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
                
            total = len(blocks_to_process)
            self._log("info", f"Found {total} item(s) to process.")
            
            recs = []
            completed_count = 0
            
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
                            rec = parse_one(md_text)
                            if rec.get("bid_no"):
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
                
                # Parse block as text first
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
                if self._is_bid_in_dont_wants(id_to_check):
                    self.after(0, lambda: self._log("info", f"Skipping {id_to_check}: Already in database 'Don't Wants'"))
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
                            
                            if bid_url and "showbidDocument" in bid_url:
                                doc_id = bid_url.rstrip('/').split('/')[-1]
                                filename = f"GeM-Bidding-{doc_id}.pdf"
                                dest_path = os.path.abspath(os.path.join(dl_dir, filename))
                                
                                import urllib.request
                                req = urllib.request.Request(
                                    bid_url,
                                    headers={
                                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                                    }
                                )
                                with urllib.request.urlopen(req) as response:
                                    with open(dest_path, 'wb') as out_file:
                                        out_file.write(response.read())
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
                                pdf_rec = parse_one(md_text)
                                if bid_url and "bid_url" not in pdf_rec:
                                    pdf_rec["bid_url"] = bid_url
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
                    self.after(0, lambda: self._log("ok", f"Parsed details directly from text for {bid_no}"))
                    return rec
                    
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {executor.submit(process_one, idx, blk): (idx, blk) for idx, blk in enumerate(blocks_to_process, 1)}
                for fut in futures:
                    idx, blk = futures[fut]
                    try:
                        res_rec = fut.result(timeout=15.0)
                        if res_rec:
                            recs.append(res_rec)
                    except (TimeoutError, Exception) as e:
                        filename = os.path.basename(blk) if blk.lower().endswith(".pdf") else blk[:20]
                        self.after(0, lambda fn=filename, err=e: self._log("err", f"[{idx}/{total}] PDF read timed out or failed (skipped): {fn}: {err}"))
                    
                    completed_count += 1
                    prog_val = int(completed_count / total * 100)
                    self.after(0, lambda p=prog_val, c=completed_count: self._set_prog(p, f"Processed {c}/{total}…"))
                    
            self.after(0, lambda: self._set_prog(100, "Done."))
            self.after(0, lambda: self._add_rows(recs, total))
        threading.Thread(target=worker, daemon=True).start()

    def _add_rows(self, recs, total):
        added_count = 0
        updated_count = 0
        
        settings = db.load_settings()
        inc_raw = settings.get("include_keywords", "")
        exc_raw = settings.get("exclude_keywords", "")
        inc_kws = [k.strip().lower() for k in inc_raw.split(",") if k.strip()]
        exc_kws = [k.strip().lower() for k in exc_raw.split(",") if k.strip()]
        
        children = self.tv.get_children()
        records_by_bid = {}
        for iid in children:
            bid_no = self.tv.set(iid, "bid_no")
            if bid_no:
                matched_rec = None
                for r in self._records:
                    if r.get("bid_no") == bid_no:
                        matched_rec = r
                        break
                if matched_rec:
                    records_by_bid[bid_no] = (matched_rec, iid)

        new_wants = []
        for rec in recs:
            bid_no = rec.get("bid_no")
            if bid_no in records_by_bid:
                existing_rec, iid = records_by_bid[bid_no]
                merged_fields = []
                for k, v in rec.items():
                    if v and (k not in existing_rec or not str(existing_rec[k]).strip()):
                        existing_rec[k] = v
                        if k in TV_IDS:
                            self.tv.set(iid, k, v)
                        merged_fields.append(k)
                if merged_fields:
                    updated_count += 1
                    self.tv.item(iid, tags=("fetched",))
                    self._log("ok", f"Updated {bid_no} with {len(merged_fields)} new fields")
                else:
                    self._log("info", f"Skipped {bid_no}: Already exists with identical details")
            else:
                is_want = self._get_tender_status(rec, inc_kws, exc_kws)
                rec["is_want_derived"] = is_want
                self._records.append(rec)
                self._tv_insert(rec)
                added_count += 1
                
                if is_want:
                    new_wants.append(rec)
                    self._log("ok", f"Added {bid_no} to database (matches Wants)")
                else:
                    self._log("info", f"Added {bid_no} to database (Don't Want / Filtered)")

        db.save_all_tenders(self._records)
        self._refresh_table_view()
        
        if new_wants:
            w_count = len(new_wants)
            first_w = new_wants[0]
            first_bid = first_w.get('bid_no', '')
            first_item = first_w.get('items', '')
            desc = f"{first_bid}: {first_item[:30]}..." if w_count == 1 \
                   else f"{first_bid} and {w_count - 1} other(s)"
            self._show_toast("New Want Tender Match!", desc, "ok")
            
        skipped = total - (added_count + updated_count)
        msg = f"Parsed {total} block(s): {added_count} added"
        if updated_count:
            msg += f", {updated_count} updated"
        if skipped > 0:
            msg += f", {skipped} skipped"
        self._log("info", msg)
        self._set_status(msg, SUCCESS if (added_count or updated_count) else WARN)
        self._set_prog(100, "Done.")
        if recs: self.paste_txt.delete("1.0","end")
        try:
            if self.notebook.index(self.notebook.select()) == 1:
                self._update_calendar()
                self._update_details()
        except:
            pass

    def _do_portal_scrape_start(self):
        if self._scrape_running or self._fetch_running:
            self._log("warn", "An operation is already running (scrape or fetch). Please wait.")
            return

        query = self.scrape_query_var.get().strip()
        max_pages_str = self.scrape_max_pages_var.get().strip()
        
        try:
            max_pages = int(max_pages_str) if max_pages_str else 0
        except ValueError:
            messagebox.showerror("Invalid Input", "Max Pages must be an integer.", parent=self)
            return

        # Date filter validation
        date_filter_type = self.scrape_date_type_var.get()
        from_date_str = self.scrape_date_from_var.get().strip()
        to_date_str = self.scrape_date_to_var.get().strip()
        
        if date_filter_type in ("Start Date", "End Date"):
            if from_date_str:
                from_date_parsed = self._parse_date_str(from_date_str)
                if not from_date_parsed:
                    messagebox.showerror("Invalid Date", "From Date must be in DD-MM-YYYY format.", parent=self)
                    return
            if to_date_str:
                to_date_parsed = self._parse_date_str(to_date_str)
                if not to_date_parsed:
                    messagebox.showerror("Invalid Date", "To Date must be in DD-MM-YYYY format.", parent=self)
                    return

        if not _try_import_selenium():
            messagebox.showerror("Missing library",
                "Please install Selenium:\n\npip install selenium webdriver-manager", parent=self)
            return

        self._scrape_running = True
        self._stop_scrape_flag = False
        
        self.btn_start_scrape.configure(state="disabled")
        self.btn_stop_scrape.configure(state="normal")
        self.scrape_query_ent.configure(state="disabled")
        self.scrape_max_pages_ent.configure(state="disabled")
        self.scrape_filter_only_chk.configure(state="disabled")
        self.scrape_date_type_cb.configure(state="disabled")
        self.scrape_date_from_ent.configure(state="disabled")
        self.scrape_date_to_ent.configure(state="disabled")

        self._log("info", f"--- Portal Search & Scrape started: query='{query}', max_pages={max_pages} ---")
        if date_filter_type in ("Start Date", "End Date"):
            self._log("info", f"Date filter active: {date_filter_type} from {from_date_str or 'any'} to {to_date_str or 'any'}")
        self._set_status("Starting portal scraping...", ACCENT2)

        def worker():
            headless_opt = db.load_settings().get("selenium_headless", False)
            
            def stop_check():
                return self._stop_scrape_flag

            def record_callback(page_recs):
                recs = []
                date_filter_type = self.scrape_date_type_var.get()
                from_date_parsed = self._parse_date_str(self.scrape_date_from_var.get().strip())
                to_date_parsed = self._parse_date_str(self.scrape_date_to_var.get().strip())
                
                for blk in page_recs:
                    rec = parse_one(blk)
                    if rec.get("bid_no"):
                        # Date filter check
                        if date_filter_type in ("Start Date", "End Date"):
                            fld_key = "start_date" if date_filter_type == "Start Date" else "end_date"
                            bid_date_str = rec.get(fld_key)
                            bid_date = self._parse_date_str(bid_date_str)
                            if bid_date:
                                if from_date_parsed and bid_date < from_date_parsed:
                                    self._log("info", f"Skipping {rec['bid_no']}: {date_filter_type} {bid_date_str} < From Date")
                                    continue
                                if to_date_parsed and bid_date > to_date_parsed:
                                    self._log("info", f"Skipping {rec['bid_no']}: {date_filter_type} {bid_date_str} > To Date")
                                    continue
                            else:
                                if from_date_parsed or to_date_parsed:
                                    self._log("info", f"Skipping {rec['bid_no']}: {date_filter_type} missing/unparseable")
                                    continue

                        # Check if we should only save matches
                        if self.scrape_filter_only_var.get():
                            settings = db.load_settings()
                            inc_raw = settings.get("include_keywords", "")
                            exc_raw = settings.get("exclude_keywords", "")
                            inc_kws = [k.strip().lower() for k in inc_raw.split(",") if k.strip()]
                            exc_kws = [k.strip().lower() for k in exc_raw.split(",") if k.strip()]
                            
                            is_want = self._get_tender_status(rec, inc_kws, exc_kws)
                            if not is_want:
                                self._log("info", f"Skipping filtered bid: {rec['bid_no']}")
                                continue
                        recs.append(rec)
                if recs:
                    self.after(0, lambda r=recs: self._add_scraped_rows(r))

            scraped_total = scrape_portal_search(
                query=query,
                max_pages=max_pages,
                headless=headless_opt,
                log_fn=self._log,
                stop_check_fn=stop_check,
                record_callback=record_callback
            )

            def scrape_finished():
                self._scrape_running = False
                self.btn_start_scrape.configure(state="normal")
                self.btn_stop_scrape.configure(state="disabled")
                self.scrape_query_ent.configure(state="normal")
                self.scrape_max_pages_ent.configure(state="normal")
                self.scrape_filter_only_chk.configure(state="normal")
                self.scrape_date_type_cb.configure(state="readonly")
                self.scrape_date_from_ent.configure(state="normal")
                self.scrape_date_to_ent.configure(state="normal")
                
                msg = f"Portal scrape done: {scraped_total} bid(s) processed"
                self._set_status(msg, SUCCESS)
                try:
                    if self.notebook.index(self.notebook.select()) == 1:
                        self._update_calendar()
                        self._update_details()
                except:
                    pass

            self.after(0, scrape_finished)

        threading.Thread(target=worker, daemon=True).start()

    def _do_portal_scrape_stop(self):
        if self._scrape_running:
            self._log("info", "Stopping portal scraper... Please wait for Chrome to close.")
            self._stop_scrape_flag = True
            self.btn_stop_scrape.configure(state="disabled")

    def _add_scraped_rows(self, recs):
        added_count = 0
        updated_count = 0
        
        settings = db.load_settings()
        inc_raw = settings.get("include_keywords", "")
        exc_raw = settings.get("exclude_keywords", "")
        inc_kws = [k.strip().lower() for k in inc_raw.split(",") if k.strip()]
        exc_kws = [k.strip().lower() for k in exc_raw.split(",") if k.strip()]
        
        children = self.tv.get_children()
        records_by_bid = {}
        for iid in children:
            bid_no = self.tv.set(iid, "bid_no")
            if bid_no:
                matched_rec = None
                for r in self._records:
                    if r.get("bid_no") == bid_no:
                        matched_rec = r
                        break
                if matched_rec:
                    records_by_bid[bid_no] = (matched_rec, iid)

        for rec in recs:
            bid_no = rec.get("bid_no")
            is_want = self._get_tender_status(rec, inc_kws, exc_kws)
            rec["is_want_derived"] = is_want
            
            if bid_no in records_by_bid:
                existing_rec, iid = records_by_bid[bid_no]
                merged_fields = []
                for k, v in rec.items():
                    if v and (k not in existing_rec or not str(existing_rec[k]).strip()):
                        existing_rec[k] = v
                        if k in TV_IDS:
                            self.tv.set(iid, k, v)
                        merged_fields.append(k)
                if merged_fields:
                    updated_count += 1
                    self.tv.item(iid, tags=("fetched",))
            else:
                self._records.append(rec)
                self._tv_insert(rec)
                added_count += 1

        db.save_all_tenders(self._records)
        self._refresh_table_view()
        
        msg = f"Portal Scraper: {added_count} added, {updated_count} updated"
        self._log("ok", msg)

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
            
            completed_count = 0
            
            def fetch_one(idx, rec):
                bid = rec.get("bid_no","?")
                iid = iid_map.get(bid)
                url = rec["bid_url"]
                
                self.after(0, lambda: self._log("info", f"Fetching details for {bid}"))
                if iid: self.after(0, lambda i=iid: self.tv.item(i, tags=("fetching",)))
                
                try:
                    headless_opt = db.load_settings().get("selenium_headless", False)
                    extra = scrape_bid_page(url, log_fn=self._log, headless=headless_opt)
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
                except Exception as ex:
                    if iid: self.after(0, lambda i=iid: self.tv.item(i, tags=()))
                    self.after(0, lambda b=bid, err=ex: self._log("err", f"Failed to fetch details for {b}: {err}"))

            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = {executor.submit(fetch_one, idx, rec): rec for idx, rec in targets}
                for fut in as_completed(futures):
                    completed_count += 1
                    prog_val = int(completed_count / total * 100)
                    self.after(0, lambda p=prog_val, c=completed_count: self._set_prog(p, f"Fetched {c}/{total}…"))
                    
            self._fetch_running = False
            self.after(0, lambda: self._set_prog(100, "Fetch complete."))
            msg = f"Selenium fetch done: {total} URL(s) processed"
            self.after(0, lambda: self._log("info", f"--- {msg} ---"))
            
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
