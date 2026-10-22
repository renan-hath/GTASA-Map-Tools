import threading
import traceback

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

FONT_FAMILY = "Segoe UI"
POLL_MS = 200
STATUS_LABELS = {"ok": "OK", "fix": "WILL FIX", "error": "CANNOT FIX", "info": "INFO"}
STATUS_COLORS = {"ok": ("#1e7a34", "#7fd48f"), "fix": ("#9a5b00", "#f0b45a"), "error": ("#b3261e", "#f2b8b5"),
                 "info": ("gray35", "gray65")}


class InstallationWindow:
    """
    Lists what the installation check finds in the game folder, and applies the fixes or
    restores the last backup when asked.
    """

    def __init__(self, root, create_check):
        """create_check: makes an InstallationCheck of the game folder set in the settings."""
        self.create_check = create_check
        self.check = None
        self.findings = []
        self._thread = None
        self._status = ""
        self._show_ok = tk.BooleanVar(value=False)
        self._done = None

        window = ctk.CTkToplevel(root)
        window.title("Installation check")
        window.geometry("820x600")
        window.transient(root)
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(1, weight=1)
        self.window = window

        self.summary_label = ctk.CTkLabel(window, text="", anchor="w", justify="left", wraplength=780,
                                          font=(FONT_FAMILY, 13, "bold"))
        self.summary_label.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))

        self.text = ctk.CTkTextbox(window, wrap="word", font=(FONT_FAMILY, 12))
        self.text.grid(row=1, column=0, sticky="nsew", padx=16)

        for status, colors in STATUS_COLORS.items():
            self.text.tag_config(status, foreground=colors[0 if ctk.get_appearance_mode() == "Light" else 1])

        options = ctk.CTkFrame(window, fg_color="transparent")
        options.grid(row=2, column=0, sticky="ew", padx=16, pady=(6, 0))
        ctk.CTkCheckBox(options, text="Show the limits that are fine", variable=self._show_ok,
                        command=self._show_findings).pack(side="left")

        buttons = ctk.CTkFrame(window, fg_color="transparent")
        buttons.grid(row=3, column=0, sticky="ew", padx=16, pady=12)
        self.apply_button = ctk.CTkButton(buttons, text="Apply fixes", command=self.apply, width=140)
        self.apply_button.pack(side="left")
        self.restore_button = ctk.CTkButton(buttons, text="Restore last backup", command=self.restore, width=160)
        self.restore_button.pack(side="left", padx=8)
        self.check_button = ctk.CTkButton(buttons, text="Check again", command=self.run_check, width=120)
        self.check_button.pack(side="left")
        ctk.CTkButton(buttons, text="Close", command=window.destroy, width=90).pack(side="right")

        self.run_check()

    # Work apart from the window, which stays responsive

    def _start(self, work):
        if self._thread and self._thread.is_alive():
            return

        for button in (self.apply_button, self.restore_button, self.check_button):
            button.configure(state=tk.DISABLED)

        def run():
            try:
                work()
            except Exception as error:
                traceback.print_exc()
                self._status = f"Failed: {error}"

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()
        self._poll()

    def _progress(self, status):
        print(status)
        self._status = status

    def _poll(self):
        if not self.window.winfo_exists():
            return

        if self._thread.is_alive():
            self.summary_label.configure(text=self._status)
            self.window.after(POLL_MS, self._poll)
            return

        self.check_button.configure(state=tk.NORMAL)
        self._show_findings()

    # Actions

    def run_check(self):
        def work():
            self._status = "Checking the installation..."
            self.check = self.create_check()
            self.findings = self.check.run(self._progress)
            self._done = None

        self._start(work)

    def apply(self):
        fixes = [finding for finding in self.findings if finding.status == "fix"]

        if not fixes:
            return

        changes = [change.description for finding in fixes for change in finding.changes]
        text = "\n".join(f"- {change}" for change in changes[:25])

        if len(changes) > 25:
            text += f"\n... and {len(changes) - 25} more"

        if not messagebox.askyesno("Apply fixes", f"These changes will be made to the game folder:\n\n{text}\n\n"
                                   "Every file they touch is copied to a backup folder first, so "
                                   "\"Restore last backup\" can undo them.", parent=self.window):
            return

        def work():
            backup_dir = self.check.apply(self.findings, self._progress)
            self._progress("Checking again...")
            self.check = self.create_check()
            self.findings = self.check.run(self._progress)
            self._done = f"Fixes applied. The backup is at {backup_dir}."

        self._start(work)

    def restore(self):
        if not self.check:
            return

        backups = self.check.list_backups()

        if not backups:
            messagebox.showinfo("Restore last backup", "There is no backup in this game folder.", parent=self.window)
            return

        if not messagebox.askyesno("Restore last backup", f"Put back the files of {backups[-1]}, and remove what "
                                   "those fixes created?", parent=self.window):
            return

        def work():
            self.check.restore(backups[-1], self._progress)
            self.check = self.create_check()
            self.findings = self.check.run(self._progress)
            self._done = f"Restored {backups[-1]}."

        self._start(work)

    # Showing the findings

    def _show_findings(self):
        findings = self.findings
        fixes = [finding for finding in findings if finding.status == "fix"]
        errors = [finding for finding in findings if finding.status == "error"]

        if errors:
            summary = f"{len(errors)} problems this tool cannot fix, and {len(fixes)} it can."
        elif fixes:
            summary = f"{len(fixes)} things to fix. \"Apply fixes\" makes the changes listed under them."
        elif findings:
            summary = "The game can load every installed mod."
        else:
            summary = self._status

        done = getattr(self, '_done', None)
        self.summary_label.configure(text=f"{done}\n{summary}" if done else summary)
        self.apply_button.configure(state=tk.NORMAL if fixes else tk.DISABLED)
        self.restore_button.configure(state=tk.NORMAL if self.check and self.check.list_backups() else tk.DISABLED)

        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        order = {"error": 0, "fix": 1, "info": 2, "ok": 3}

        for finding in sorted(findings, key=lambda finding: order[finding.status]):
            if finding.status == "ok" and not self._show_ok.get():
                continue

            self.text.insert(tk.END, f"{STATUS_LABELS[finding.status]}  ", finding.status)
            line = finding.name

            if finding.needed:
                line += f": needs {finding.needed}, has {finding.current}"
            elif finding.current:
                line += f": {finding.current}"

            self.text.insert(tk.END, line + "\n")

            if finding.message:
                self.text.insert(tk.END, f"    {finding.message}\n")

            for change in finding.changes:
                self.text.insert(tk.END, f"    -> {change.description}\n")

            self.text.insert(tk.END, "\n")

        self.text.configure(state=tk.DISABLED)
