import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from tkinter.scrolledtext import ScrolledText
import threading
import urllib.request
import json
import os

MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Minecraft Version Downloader")
        self.geometry("900x600")
        self.style = ttk.Style(self)
        self.style.configure('Treeview', rowheight=24)

        # Layout: progress at top, then search, then list/details below
        self.rowconfigure(0, weight=0) # For progress bar
        self.rowconfigure(1, weight=0) # For search bar
        self.rowconfigure(2, weight=1) # For main content
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=2)

        # Progress bar for loading versions (spans both columns)
        self.load_progress = ttk.Progressbar(self, mode='indeterminate')
        self.load_progress.grid(row=0, column=0, columnspan=2, sticky='ew', padx=10, pady=10)

        # Search bar frame
        search_frame = ttk.Frame(self)
        search_frame.grid(row=1, column=0, columnspan=2, sticky='ew', padx=10, pady=(0, 10))
        search_frame.columnconfigure(0, weight=1) # Search entry
        search_frame.columnconfigure(1, weight=0) # Search button

        self.search_entry = ttk.Entry(search_frame)
        self.search_entry.grid(row=0, column=0, sticky='ew', padx=(0, 5))
        self.search_entry.bind("<Return>", self.perform_search_event) # Bind Enter key

        self.search_button = ttk.Button(search_frame, text="Search", command=self.search_versions)
        self.search_button.grid(row=0, column=1, sticky='e')


        # Frame to hold version list and scrollbar
        list_frame = ttk.Frame(self)
        list_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        # Version list on left
        cols = ("Version", "Type", "Release Time")
        self.vers_list = ttk.Treeview(list_frame, columns=cols, show="headings", selectmode='browse')
        for col in cols:
            self.vers_list.heading(col, text=col)
            self.vers_list.column(col, anchor="w", width=200)
        self.vers_list.grid(row=0, column=0, sticky="nsew")
        self.vers_list.bind("<<TreeviewSelect>>", self.on_select)

        # Scrollbar for version list
        list_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.vers_list.yview)
        list_scroll.grid(row=0, column=1, sticky="ns")
        self.vers_list.configure(yscrollcommand=list_scroll.set)

        # Details panel on right
        detail_frame = ttk.Frame(self, padding=(10,10))
        detail_frame.grid(row=2, column=1, sticky="nsew")
        detail_frame.columnconfigure(0, weight=1)
        detail_frame.rowconfigure(1, weight=1)

        # Details text
        self.details = ScrolledText(detail_frame, wrap=tk.WORD, height=15)
        self.details.grid(row=0, column=0, sticky="nsew")
        self.details.configure(state=tk.DISABLED)

        # Download progress bar under details
        self.download_progress = ttk.Progressbar(detail_frame, mode='determinate', maximum=100)
        self.download_progress.grid(row=1, column=0, sticky='ew', pady=(5,10))
        self.download_progress.grid_remove()

        # Buttons
        btn_frame = ttk.Frame(detail_frame)
        btn_frame.grid(row=2, column=0, pady=(0,10), sticky="ew")
        btn_frame.columnconfigure((0,1,2), weight=1)

        self.download_server_btn = ttk.Button(
            btn_frame, text="Download Server Jar", command=self.download_server, state=tk.DISABLED)
        self.download_server_btn.grid(row=0, column=0, sticky="ew", padx=(0,5))

        self.download_client_btn = ttk.Button(
            btn_frame, text="Download Client Jar", command=self.download_client, state=tk.DISABLED)
        self.download_client_btn.grid(row=0, column=1, sticky="ew", padx=5)

        self.tech_btn = ttk.Button(
            btn_frame, text="Show Technical Details", command=self.show_technical, state=tk.DISABLED)
        self.tech_btn.grid(row=0, column=2, sticky="ew", padx=(5,0))

        self.all_versions = [] # Store the complete list of versions
        self.current_display_versions = [] # Store the currently filtered/displayed versions

        threading.Thread(target=self.load_versions, daemon=True).start()

    def load_versions(self):
        try:
            self.load_progress.start(10)
            resp = urllib.request.urlopen(MANIFEST_URL)
            manifest = json.load(resp)
            self.all_versions = manifest["versions"] # Store all versions
            self.update_version_list(self.all_versions) # Display all initially
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load manifest:\n{e}")
        finally:
            self.load_progress.stop()
            self.load_progress.grid_remove()

    def update_version_list(self, versions_to_display):
        """Clears and repopulates the Treeview with the given list of versions."""
        for item in self.vers_list.get_children():
            self.vers_list.delete(item)
        self.current_display_versions = versions_to_display # Update the list of currently displayed versions
        for idx, v in enumerate(self.current_display_versions):
            self.vers_list.insert("", "end", iid=idx,
                values=(v["id"], v["type"], v["releaseTime"]))

    def perform_search_event(self, event):
        """Called when Enter key is pressed in the search entry."""
        self.search_versions()

    def search_versions(self):
        search_term = self.search_entry.get().strip().lower()
        if not search_term:
            self.update_version_list(self.all_versions) # Show all if search is empty
            return

        filtered_versions = [
            v for v in self.all_versions
            if search_term in v["id"].lower() or
               search_term in v["type"].lower()
        ]
        self.update_version_list(filtered_versions)
        self.show_details("") # Clear details when search changes
        # Disable buttons until a new selection is made
        self.download_server_btn.config(state=tk.DISABLED)
        self.download_client_btn.config(state=tk.DISABLED)
        self.tech_btn.config(state=tk.DISABLED)


    def on_select(self, ev):
        sel = self.vers_list.selection()
        if not sel:
            # Clear details and disable buttons if nothing is selected (e.g., after a search)
            self.show_details("")
            self.download_server_btn.config(state=tk.DISABLED)
            self.download_client_btn.config(state=tk.DISABLED)
            self.tech_btn.config(state=tk.DISABLED)
            return

        idx = int(sel[0])
        # Ensure we access the correct version from the currently displayed list
        if idx >= len(self.current_display_versions):
            return # Index out of bounds if selection was made on old list
        v = self.current_display_versions[idx]
        try:
            resp = urllib.request.urlopen(v["url"])
            self.vjson = json.load(resp)
        except Exception as e:
            self.show_details(f"Error loading details:\n{e}")
            # Ensure buttons are disabled on error
            self.download_server_btn.config(state=tk.DISABLED)
            self.download_client_btn.config(state=tk.DISABLED)
            self.tech_btn.config(state=tk.DISABLED)
            return

        lines = [
            f"ID: {self.vjson.get('id')}",
            f"Type: {self.vjson.get('type')}",
            f"Release Time: {self.vjson.get('releaseTime')}"
        ]
        if 'mainClass' in self.vjson:
            lines.append(f"Main Class: {self.vjson['mainClass']}")
        if 'complianceLevel' in self.vjson:
            lines.append(f"Compliance Level: {self.vjson['complianceLevel']}")

        downloads = self.vjson.get('downloads', {})
        self.client_url = downloads.get('client', {}).get('url')
        self.server_url = downloads.get('server', {}).get('url')
        if self.client_url:
            size = downloads['client'].get('size', 'n/a')
            lines.append(f"Client Jar Size: {size} bytes")
        if self.server_url:
            size = downloads['server'].get('size', 'n/a')
            lines.append(f"Server Jar Size: {size} bytes")

        self.show_details("\n".join(lines))
        # prepare technical info
        self.tech_info = []
        ai = self.vjson.get('assetIndex', {})
        if ai:
            self.tech_info.append(f"AssetIndex URL: {ai.get('url')}")
            self.tech_info.append(f"AssetIndex SHA1: {ai.get('sha1')}")
        for part in ('client','server'):
            info = downloads.get(part, {})
            if info:
                self.tech_info.append(f"{part.capitalize()} URL: {info.get('url')}")
                self.tech_info.append(f"{part.capitalize()} SHA1: {info.get('sha1')}")
        self.tech_info.append(f"Libraries Count: {len(self.vjson.get('libraries', []))}")

        self.download_server_btn.config(state=tk.NORMAL if self.server_url else tk.DISABLED)
        self.download_client_btn.config(state=tk.NORMAL if self.client_url else tk.DISABLED)
        self.tech_btn.config(state=tk.NORMAL if self.tech_info else tk.DISABLED)

    def show_details(self, text):
        self.details.configure(state=tk.NORMAL)
        self.details.delete("1.0", tk.END)
        self.details.insert(tk.END, text)
        self.details.configure(state=tk.DISABLED)

    def show_technical(self):
        messagebox.showinfo("Technical Details", "\n".join(self.tech_info))

    def download_server(self):
        self._download(self.server_url)

    def download_client(self):
        self._download(self.client_url)

    def _download(self, url):
        default_name = os.path.basename(url)
        path = filedialog.asksaveasfilename(
            defaultextension=".jar",
            initialfile=default_name,
            filetypes=[("Java Archive", "*.jar"), ("All files","*.*")]
        )
        if not path:
            return
        # show determinate progress bar
        self.download_progress.grid()
        self.download_progress['value'] = 0
        # Disable all action buttons during download
        self.download_server_btn.config(state=tk.DISABLED)
        self.download_client_btn.config(state=tk.DISABLED)
        self.tech_btn.config(state=tk.DISABLED)
        self.search_button.config(state=tk.DISABLED)
        self.search_entry.config(state=tk.DISABLED)
        threading.Thread(target=self._download_thread, args=(url, path), daemon=True).start()

    def _report_hook(self, block_num, block_size, total_size):
        if total_size > 0:
            percent = block_num * block_size * 100 / total_size
            self.download_progress['value'] = min(percent, 100)
            self.update_idletasks()

    def _download_thread(self, url, path):
        try:
            urllib.request.urlretrieve(url, path, reporthook=self._report_hook)
            messagebox.showinfo("Downloaded", f"Saved to: {path}")
        except Exception as e:
            messagebox.showerror("Error", f"Download failed:\n{e}")
        finally:
            # hide download progress and restore buttons based on current selection
            self.download_progress.grid_remove()
            # Re-enable buttons based on current selection if any
            sel = self.vers_list.selection()
            if sel:
                idx = int(sel[0])
                if idx < len(self.current_display_versions): # Check bounds
                    v = self.current_display_versions[idx]
                    try:
                        resp = urllib.request.urlopen(v["url"])
                        self.vjson = json.load(resp)
                        downloads = self.vjson.get('downloads', {})
                        self.client_url = downloads.get('client', {}).get('url')
                        self.server_url = downloads.get('server', {}).get('url')

                        self.download_server_btn.config(state=tk.NORMAL if self.server_url else tk.DISABLED)
                        self.download_client_btn.config(state=tk.NORMAL if self.client_url else tk.DISABLED)
                        self.tech_btn.config(state=tk.NORMAL if hasattr(self, 'tech_info') and self.tech_info else tk.DISABLED)
                    except Exception:
                        # Fallback to disabled if re-loading info fails
                        self.download_server_btn.config(state=tk.DISABLED)
                        self.download_client_btn.config(state=tk.DISABLED)
                        self.tech_btn.config(state=tk.DISABLED)
            else:
                self.download_server_btn.config(state=tk.DISABLED)
                self.download_client_btn.config(state=tk.DISABLED)
                self.tech_btn.config(state=tk.DISABLED)

            self.search_button.config(state=tk.NORMAL)
            self.search_entry.config(state=tk.NORMAL)


if __name__ == "__main__":
    App().mainloop()