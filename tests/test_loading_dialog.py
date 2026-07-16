import os
import sys
import unittest
import tkinter as tk
import time
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'core')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'gui')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'gui', 'dialogs')))

import loading_dialog

class TestLoadingDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def test_loading_dialog_step_status_advancement(self):
        steps = ["Step A", "Step B", "Step C"]
        dialog = loading_dialog.LoadingDialog(self.root, "Test", "Msg", steps=steps)
        
        # Initially Step A is running
        self.assertEqual(dialog.step_rows[0]["status"], "running")
        self.assertEqual(dialog.step_rows[1]["status"], "pending")
        
        # Simulate a warning log message on Step A
        dialog.append_checklist_item("warn", "A small warning occurred")
        dialog.update()
        self.assertEqual(dialog.step_rows[0]["status"], "warn")
        
        # Advance progress to Step B (percent = 50)
        # This should transition Step A to "ok" since it's now in the past and had no fatal error
        dialog.update_progress(50)
        dialog.update()
        self.assertEqual(dialog.step_rows[0]["status"], "ok")
        self.assertEqual(dialog.step_rows[1]["status"], "running")
        
        dialog.destroy()

    def test_loading_dialog_failure_keeps_window_open(self):
        # A task that raises an exception
        def failing_task(progress_cb):
            raise ValueError("Fatal error!")
            
        dialog = loading_dialog.LoadingDialog(self.root, "Test", "Msg", task_fn=failing_task)
        
        # Let the thread run and update the UI loop
        dialog.update()
        for _ in range(30):
            dialog.update()
            time.sleep(0.05)
            if getattr(dialog, 'task_finished', False):
                break
                
        # Run event loop one more time to process the queued _handle_failure
        time.sleep(0.1)
        dialog.update()
        
        self.assertIsNotNone(dialog.exception)
        self.assertTrue(dialog.winfo_exists()) # Window remains open
        
        # Verify the close button is packed/created
        children = dialog.frame.winfo_children()
        button_exists = any(isinstance(c, tk.Button) and c.cget("text") == "Close" for c in children)
        self.assertTrue(button_exists)
        
        dialog.destroy()

    def test_loading_dialog_shows_running_sub_processes(self):
        steps = ["Step A", "Step B"]
        dialog = loading_dialog.LoadingDialog(self.root, "Test", "Msg", steps=steps)
        
        # Verify initial text
        row = dialog.step_rows[0]
        self.assertEqual(row["text"].cget("text"), "Step A")
        
        # Send info level message, simulating sub-process log
        dialog.append_checklist_item("info", "[INFO] Validating document integrity...")
        dialog.update()
        
        # Verify step label text includes sub-process in parentheses
        self.assertEqual(row["text"].cget("text"), "Step A (Validating document integrity...)")
        
        dialog.destroy()

    def test_loading_dialog_copy_logs(self):
        steps = ["Step A"]
        dialog = loading_dialog.LoadingDialog(self.root, "Test", "Msg", steps=steps)
        dialog.append_checklist_item("info", "Verification test log entry")
        dialog.update()
        
        copy_btn = None
        def find_button(parent):
            nonlocal copy_btn
            for child in parent.winfo_children():
                if isinstance(child, tk.Button) and child.cget("text") == "Copy Logs":
                    copy_btn = child
                    return
                find_button(child)
                
        find_button(dialog)
        self.assertIsNotNone(copy_btn, "Copy Logs button not found in dialog")
        
        copy_btn.invoke()
        dialog.update()
        
        clipboard_text = dialog.clipboard_get()
        self.assertIn("Verification test log entry", clipboard_text)
        
        dialog.destroy()
