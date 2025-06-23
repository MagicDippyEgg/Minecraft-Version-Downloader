import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from tkinter.scrolledtext import ScrolledText
import threading
import urllib.request
import json
import os

# Define the Fabric API endpoints
FABRIC_API_BASE = "https://meta.fabricmc.net/v2/versions/"
GAME_VERSIONS_URL = f"{FABRIC_API_BASE}game"
LOADER_VERSIONS_URL_TPL = f"{FABRIC_API_BASE}loader/{{}}" # Template for game version
INSTALLER_META_URL = f"{FABRIC_API_BASE}installer"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Fabric Version Downloader")
        self.geometry("900x600")
        self.style = ttk.Style(self)
        self.style.configure('Treeview', rowheight=24)

        # Layout:
        self.rowconfigure(0, weight=0) # For progress bar
        self.rowconfigure(1, weight=0) # For game version selector
        self.rowconfigure(2, weight=0) # For search bar
        self.rowconfigure(3, weight=1) # For main content
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=2)

        # Progress bar for loading (spans both columns)
        self.load_progress = ttk.Progressbar(self, mode='indeterminate')
        self.load_progress.grid(row=0, column=0, columnspan=2, sticky='ew', padx=10, pady=10)

        # Frame for Minecraft version selection
        game_select_frame = ttk.Frame(self)
        game_select_frame.grid(row=1, column=0, columnspan=2, sticky='ew', padx=10, pady=(0, 10))
        game_select_frame.columnconfigure(1, weight=1)
        
        ttk.Label(game_select_frame, text="Select Minecraft Version:").grid(row=0, column=0, padx=(0,5))
        self.game_version_combo = ttk.Combobox(game_select_frame, state='readonly')
        self.game_version_combo.grid(row=0, column=1, sticky='ew')
        self.game_version_combo.bind("<<ComboboxSelected>>", self.on_game_select)

        # Search bar frame
        search_frame = ttk.Frame(self)
        search_frame.grid(row=2, column=0, columnspan=2, sticky='ew', padx=10, pady=(0, 10))
        search_frame.columnconfigure(0, weight=1)

        self.search_entry = ttk.Entry(search_frame)
        self.search_entry.grid(row=0, column=0, sticky='ew', padx=(0, 5))
        self.search_entry.bind("<Return>", self.perform_search_event)

        self.search_button = ttk.Button(search_frame, text="Search", command=self.search_loaders)
        self.search_button.grid(row=0, column=1, sticky='e')

        # Frame to hold loader list and scrollbar
        list_frame = ttk.Frame(self)
        list_frame.grid(row=3, column=0, sticky="nsew", padx=10, pady=5)
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        # Loader version list on left
        cols = ("Loader Version", "Stability")
        self.vers_list = ttk.Treeview(list_frame, columns=cols, show="headings", selectmode='browse')
        self.vers_list.heading("Loader Version", text="Loader Version")
        self.vers_list.column("Loader Version", anchor="w", width=150)
        self.vers_list.heading("Stability", text="Stability")
        self.vers_list.column("Stability", anchor="w", width=100)
        self.vers_list.grid(row=0, column=0, sticky="nsew")
        self.vers_list.bind("<<TreeviewSelect>>", self.on_loader_select)

        list_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.vers_list.yview)
        list_scroll.grid(row=0, column=1, sticky="ns")
        self.vers_list.configure(yscrollcommand=list_scroll.set)

        # Details panel on right
        detail_frame = ttk.Frame(self, padding=(10, 10))
        detail_frame.grid(row=3, column=1, sticky="nsew")
        detail_frame.columnconfigure(0, weight=1)
        detail_frame.rowconfigure(1, weight=1)

        self.details = ScrolledText(detail_frame, wrap=tk.WORD, height=15)
        self.details.grid(row=0, column=0, sticky="nsew")
        self.details.configure(state=tk.DISABLED)
        
        # Download progress bar under details
        self.download_progress = ttk.Progressbar(detail_frame, mode='determinate', maximum=100)
        self.download_progress.grid(row=1, column=0, sticky='ew', pady=(5,10))
        self.download_progress.grid_remove()

        # Buttons
        btn_frame = ttk.Frame(detail_frame)
        btn_frame.grid(row=2, column=0, pady=(0, 10), sticky="ew")
        btn_frame.columnconfigure(0, weight=1)
        
        self.download_installer_btn = ttk.Button(
            btn_frame, text="Download Fabric Installer", command=self.download_installer, state=tk.DISABLED)
        self.download_installer_btn.grid(row=0, column=0, sticky="ew")

        self.all_loaders = []
        self.installer_info = {}

        threading.Thread(target=self.load_game_versions, daemon=True).start()

    def load_game_versions(self):
        """Loads the list of supported Minecraft versions into the Combobox."""
        try:
            self.load_progress.start(10)
            resp = urllib.request.urlopen(GAME_VERSIONS_URL)
            game_versions = json.load(resp)
            # We only need the version string from each object
            self.game_version_combo['values'] = [v['version'] for v in game_versions]
            # Pre-select the first (latest) version
            if self.game_version_combo['values']:
                self.game_version_combo.current(0)
                self.on_game_select(None) # Trigger loading loaders for the default selection
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load Minecraft versions:\n{e}")
        finally:
            # The progress bar will be stopped by the subsequent loader loading
            pass
    
    def on_game_select(self, event):
        """Called when a new Minecraft version is selected."""
        game_version = self.game_version_combo.get()
        if not game_version:
            return
        
        # Clear previous state
        self.update_loader_list([])
        self.show_details("")
        self.download_installer_btn.config(state=tk.DISABLED)
        
        # Start loading the corresponding loader versions in a new thread
        self.load_progress.grid()
        self.load_progress.start(10)
        threading.Thread(target=self.load_loader_versions, args=(game_version,), daemon=True).start()

    def load_loader_versions(self, game_version):
        """Loads loader versions for a specific game version."""
        try:
            url = LOADER_VERSIONS_URL_TPL.format(game_version)
            resp = urllib.request.urlopen(url)
            self.all_loaders = json.load(resp)
            self.update_loader_list(self.all_loaders)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load Fabric loaders for MC {game_version}:\n{e}")
        finally:
            self.load_progress.stop()
            self.load_progress.grid_remove()

    def update_loader_list(self, loaders_to_display):
        """Clears and repopulates the Treeview with Fabric loader versions."""
        for item in self.vers_list.get_children():
            self.vers_list.delete(item)
        for v in loaders_to_display:
            # The actual version info is nested inside a 'loader' object
            loader_info = v.get('loader', {})
            self.vers_list.insert("", "end", values=(loader_info.get('version'), "✅ Stable" if loader_info.get('stable') else "❌ Unstable"))

    def perform_search_event(self, event):
        self.search_loaders()

    def search_loaders(self):
        search_term = self.search_entry.get().strip().lower()
        if not search_term:
            self.update_loader_list(self.all_loaders)
            return

        filtered_loaders = [
            v for v in self.all_loaders
            if search_term in v.get('loader', {}).get('version', '').lower()
        ]
        self.update_loader_list(filtered_loaders)
        self.show_details("")
        self.download_installer_btn.config(state=tk.DISABLED)

    def on_loader_select(self, ev):
        """Called when a loader is selected from the list."""
        if not self.vers_list.selection():
            return
        
        # No need to fetch more data, just enable the button
        self.show_details(f"Ready to download the universal Fabric Installer.\n\nThis installer can be used to create client profiles or set up a server for the selected Minecraft version ({self.game_version_combo.get()}).")
        self.download_installer_btn.config(state=tk.NORMAL)

    def show_details(self, text):
        self.details.configure(state=tk.NORMAL)
        self.details.delete("1.0", tk.END)
        self.details.insert(tk.END, text)
        self.details.configure(state=tk.DISABLED)

    def download_installer(self):
        """Prepares and initiates the installer download."""
        self.download_installer_btn.config(state=tk.DISABLED)
        self.game_version_combo.config(state=tk.DISABLED)
        self.search_button.config(state=tk.DISABLED)
        self.search_entry.config(state=tk.DISABLED)
        
        self.download_progress.grid()
        self.download_progress['value'] = 0
        
        # Start a thread to first get the installer URL, then download the file
        threading.Thread(target=self._download_installer_thread, daemon=True).start()

    def _download_installer_thread(self):
        """Fetches the installer URL and then downloads it."""
        try:
            # Step 1: Fetch the installer metadata
            resp = urllib.request.urlopen(INSTALLER_META_URL)
            installer_data = json.load(resp)
            # Find the stable universal installer
            installer_url = ""
            for item in installer_data:
                if item.get("stable"):
                    installer_url = item.get("url")
                    break
            
            if not installer_url:
                raise ValueError("Could not find a stable installer URL.")

            # Step 2: Ask user for save location and download
            default_name = os.path.basename(installer_url)
            self.after(0, self._ask_save_and_download, installer_url, default_name)

        except Exception as e:
            messagebox.showerror("Error", f"Could not get installer info:\n{e}")
            self.after(0, self._reset_ui_after_download)

    def _ask_save_and_download(self, url, default_name):
        """Runs in the main thread to open the file dialog."""
        path = filedialog.asksaveasfilename(
            defaultextension=".jar",
            initialfile=default_name,
            filetypes=[("Java Archive", "*.jar"), ("All files", "*.*")]
        )
        if path:
            # Start the actual download in another thread
            threading.Thread(target=self._download_file_thread, args=(url, path), daemon=True).start()
        else:
            # User cancelled, so reset UI
            self._reset_ui_after_download()
            
    def _report_hook(self, block_num, block_size, total_size):
        if total_size > 0:
            percent = (block_num * block_size * 100) / total_size
            self.download_progress['value'] = min(percent, 100)
            self.update_idletasks() # Safe to call for progress bar updates

    def _download_file_thread(self, url, path):
        """The final download thread."""
        try:
            urllib.request.urlretrieve(url, path, reporthook=self._report_hook)
            messagebox.showinfo("Downloaded", f"Fabric Installer saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"Download failed:\n{e}")
        finally:
            # Schedule UI reset on the main thread
            self.after(0, self._reset_ui_after_download)

    def _reset_ui_after_download(self):
        """Resets the UI elements to their active state."""
        self.download_progress.grid_remove()
        if self.vers_list.selection():
            self.download_installer_btn.config(state=tk.NORMAL)
        self.game_version_combo.config(state=tk.NORMAL)
        self.search_button.config(state=tk.NORMAL)
        self.search_entry.config(state=tk.NORMAL)


if __name__ == "__main__":
    App().mainloop()