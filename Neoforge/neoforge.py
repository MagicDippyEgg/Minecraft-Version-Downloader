import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import threading
import urllib.request
import json
import os
import xml.etree.ElementTree as ET

# Define the NeoForge Maven metadata URL
NEOFORGE_MAVEN_METADATA_URL = "https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml"
# Corrected Base URL for the installer download based on Maven repository structure
NEOFORGE_INSTALLER_BASE_URL = "https://maven.neoforged.net/releases/net/neoforged/neoforge/{neoforge_version}/neoforge-{neoforge_version}-installer.jar"

# Helper function for natural sorting of version strings
def sort_version_string(version_str):
    """
    Splits version strings (e.g., "1.20.1" or "25w14craftmine") into comparable components.
    Numbers are converted to integers, non-numbers remain strings.
    This allows for "natural" sorting (e.g., 1.10, 1.10.2, 1.11, 1.20.1, 25w14craftmine).
    """
    parts = []
    temp_num = ""
    for char in version_str:
        if char.isdigit():
            temp_num += char
        else:
            if temp_num:
                parts.append(int(temp_num))
                temp_num = ""
            parts.append(char) # Add non-digit char
    if temp_num:
        parts.append(int(temp_num))
    return parts

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("NeoForge Version Downloader")
        self.geometry("900x600")
        self.style = ttk.Style(self)
        self.style.configure('Treeview', rowheight=24)

        # Layout:
        self.rowconfigure(0, weight=0) # For progress bar
        self.rowconfigure(1, weight=0) # For game version selector
        # self.rowconfigure(2, weight=0) # REMOVED: For search bar
        self.rowconfigure(2, weight=1) # Adjusted: For main content (was row 3)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=2)

        # Progress bar for loading (spans both columns)
        self.load_progress = ttk.Progressbar(self, mode='indeterminate')
        self.load_progress.grid(row=0, column=0, columnspan=2, sticky='ew', padx=10, pady=10)

        # Frame for controls (Game Version)
        controls_frame = ttk.Frame(self)
        # Adjusted row to 1 (was row 1)
        controls_frame.grid(row=1, column=0, columnspan=2, sticky='ew', padx=10, pady=(0, 10))
        controls_frame.columnconfigure(1, weight=1)

        # Minecraft Version Selector
        ttk.Label(controls_frame, text="Select Minecraft Version:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.game_version_combobox = ttk.Combobox(controls_frame, state='readonly')
        self.game_version_combobox.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        self.game_version_combobox.bind("<<ComboboxSelected>>", self._on_game_version_selected)

        # Main content area (NeoForge versions list and details/buttons)
        main_frame = ttk.Frame(self)
        # Adjusted row to 2 (was row 3)
        main_frame.grid(row=2, column=0, columnspan=2, sticky='nsew', padx=10, pady=10)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=0) # For download button column
        main_frame.rowconfigure(0, weight=1)

        # NeoForge Versions Treeview
        self.vers_list = ttk.Treeview(main_frame, columns=("Version", "Stability"), show="headings", selectmode="browse")
        self.vers_list.heading("Version", text="NeoForge Version")
        self.vers_list.heading("Stability", text="Stability")
        self.vers_list.column("Version", width=200, anchor="w")
        self.vers_list.column("Stability", width=100, anchor="center")
        self.vers_list.grid(row=0, column=0, sticky='nsew', padx=(0, 10))
        self.vers_list.bind("<<TreeviewSelect>>", self._on_neoforge_version_selected)

        # Scrollbar for Treeview
        vers_scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=self.vers_list.yview)
        vers_scrollbar.grid(row=0, column=0, sticky='nse', padx=(0, 10))
        self.vers_list.configure(yscrollcommand=vers_scrollbar.set)

        # Download button frame (right side)
        download_frame = ttk.Frame(main_frame)
        download_frame.grid(row=0, column=1, sticky='ns')

        self.download_installer_btn = ttk.Button(download_frame, text="Download Installer", command=self._download_installer_btn_clicked, state=tk.DISABLED)
        self.download_installer_btn.pack(pady=5, fill='x')

        # Progress bar for download (initially hidden)
        self.download_progress = ttk.Progressbar(self, orient='horizontal', mode='determinate')
        # This will be gridded dynamically when a download starts

        # Start fetching versions in a separate thread
        self.after(100, self._start_fetch_versions) # Small delay to ensure UI is ready

    def _start_fetch_versions(self):
        self.load_progress.start()
        self.game_version_combobox.config(state=tk.DISABLED)
        # self.search_entry.config(state=tk.DISABLED) # REMOVED
        threading.Thread(target=self._fetch_neoforge_versions_thread, daemon=True).start()

    def _fetch_neoforge_versions_thread(self):
        """Fetches all NeoForge versions from the Maven metadata and populates the game version combobox."""
        try:
            with urllib.request.urlopen(NEOFORGE_MAVEN_METADATA_URL) as response:
                xml_data = response.read()
            root = ET.fromstring(xml_data)

            all_neoforge_versions = []
            # Using findall with or without namespace to be robust
            versions_element = root.find(".//{http://maven.apache.org/POM/4.0.0}versions")
            if versions_element is None: # Fallback without namespace if it fails
                versions_element = root.find(".//versions")

            # Corrected: Use 'is not None' for truthiness check
            if versions_element is not None:
                for version_elem in versions_element.findall("{http://maven.apache.org/POM/4.0.0}version") or versions_element.findall("version"):
                    all_neoforge_versions.append(version_elem.text)

            # Process versions: group by MC version and determine stability
            mc_versions = set()
            processed_versions = {} # {mc_version: [{version: str, stability: str}, ...]}

            for full_version in all_neoforge_versions:
                parts = full_version.split('-')
                if len(parts) >= 2:
                    mc_ver = parts[0]
                    
                    # Determine stability based on version string (simple check for common terms)
                    stability = "Stable"
                    if any(term in full_version.lower() for term in ["beta", "rc", "pre", "alpha"]):
                        stability = "Experimental"

                    mc_versions.add(mc_ver)
                    if mc_ver not in processed_versions:
                        processed_versions[mc_ver] = []
                    processed_versions[mc_ver].append({
                        "version": full_version,
                        "stability": stability
                    })

            # Sort Minecraft versions using the custom natural sort key
            sorted_mc_versions = sorted(list(mc_versions), key=sort_version_string, reverse=True)

            self.neoforge_versions_by_mc = processed_versions

            self.after(0, lambda: self._update_game_versions_ui(sorted_mc_versions))

        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", f"Failed to fetch NeoForge versions: {e}"))
            self.after(0, self.load_progress.stop)
            self.after(0, self.load_progress.grid_remove) # Hide on error
            self.after(0, lambda: self.game_version_combobox.config(state=tk.NORMAL))
            # self.after(0, lambda: self.search_entry.config(state=tk.NORMAL)) # REMOVED
            print(f"Error fetching NeoForge versions: {e}") # For debugging
        finally:
            self.after(0, self.load_progress.stop)
            self.after(0, self.load_progress.grid_remove) # Hide when done


    def _update_game_versions_ui(self, mc_versions):
        """Updates the game version combobox on the main thread."""
        self.game_version_combobox['values'] = mc_versions
        if mc_versions:
            self.game_version_combobox.set(mc_versions[0]) # Select the latest by default
            self._on_game_version_selected(None) # Manually trigger population of NeoForge versions
        else:
            messagebox.showinfo("No Versions", "No NeoForge versions found.")

        self.game_version_combobox.config(state='readonly')
        # self.search_entry.config(state=tk.NORMAL) # REMOVED


    def _on_game_version_selected(self, event):
        """Called when a Minecraft version is selected in the combobox."""
        selected_mc_version = self.game_version_combobox.get()
        self.vers_list.delete(*self.vers_list.get_children()) # Clear current items

        if selected_mc_version in self.neoforge_versions_by_mc:
            # Sort NeoForge versions for the selected MC version (e.g., 47.1.3 before 47.1.4)
            sorted_neoforge_versions = sorted(
                self.neoforge_versions_by_mc[selected_mc_version],
                key=lambda x: sort_version_string(x['version'].split('-', 1)[1]), # Split only once to get the NeoForge version part
                reverse=True
            )
            self.current_display_neoforge_versions = sorted_neoforge_versions
            self._populate_neoforge_treeview(sorted_neoforge_versions)
        else:
            self.current_display_neoforge_versions = []
            messagebox.showinfo("No Versions", f"No NeoForge versions found for Minecraft {selected_mc_version}.")


        self.download_installer_btn.config(state=tk.DISABLED) # Disable download button until a specific version is selected


    def _populate_neoforge_treeview(self, versions_to_display):
        """Populates the Treeview with the given list of NeoForge versions."""
        self.vers_list.delete(*self.vers_list.get_children())
        for version_info in versions_to_display:
            self.vers_list.insert("", "end", values=(version_info['version'], version_info['stability']))


    # _filter_neoforge_versions method REMOVED


    def _on_neoforge_version_selected(self, event):
        """Enable/disable download button based on selection."""
        selected_item = self.vers_list.focus()
        if selected_item:
            self.download_installer_btn.config(state=tk.NORMAL)
        else:
            self.download_installer_btn.config(state=tk.DISABLED)

    def _download_installer_btn_clicked(self):
        selected_item = self.vers_list.focus()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select a NeoForge version to download.")
            return

        # Get the full NeoForge version string from the selected item
        neoforge_full_version = self.vers_list.item(selected_item, "values")[0]
        
        # Construct the download URL using ONLY the full NeoForge version
        download_url = NEOFORGE_INSTALLER_BASE_URL.format(neoforge_version=neoforge_full_version)

        # Ask user for save location
        # The default filename should also correctly use the full neoforge version
        default_filename = f"neoforge-{neoforge_full_version}-installer.jar"
        file_path = filedialog.asksaveasfilename(
            defaultextension=".jar",
            filetypes=[("JAR Files", "*.jar"), ("All Files", "*.*")],
            initialfile=default_filename
        )

        if file_path:
            self.download_installer_btn.config(state=tk.DISABLED)
            self.download_progress.grid(row=2, column=0, columnspan=2, sticky='ew', padx=10, pady=10) # Adjusted row for progress bar
            self.download_progress['value'] = 0
            self.download_progress.start()
            threading.Thread(target=self._download_file_thread, args=(download_url, file_path), daemon=True).start()
        else:
            messagebox.showinfo("Cancelled", "Download cancelled by user.")

    def _report_hook(self, block_num, block_size, total_size):
        """Callback for urllib.request.urlretrieve to update progress bar."""
        if total_size > 0:
            percent = (block_num * block_size * 100) / total_size
            self.download_progress['value'] = min(percent, 100)
            self.update_idletasks()

    def _download_file_thread(self, url, path):
        """The actual file download thread."""
        try:
            self.after(0, lambda: self.download_progress.config(mode='determinate'))
            urllib.request.urlretrieve(url, path, reporthook=self._report_hook)
            messagebox.showinfo("Downloaded", f"NeoForge Installer saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"Download failed:\n{e}")
        finally:
            # Schedule UI reset on the main thread
            self.after(0, self._reset_ui_after_download)

    def _reset_ui_after_download(self):
        """Resets the UI elements to their active state."""
        self.download_progress.stop()
        self.download_progress.grid_remove()
        # Re-enable download button only if an item is still selected in the list
        if self.vers_list.selection():
            self.download_installer_btn.config(state=tk.NORMAL)
        else:
             self.download_installer_btn.config(state=tk.DISABLED) # Ensure it's disabled if nothing selected
        self.game_version_combobox.config(state='readonly')
        # self.search_entry.config(state=tk.NORMAL) # REMOVED


if __name__ == "__main__":
    App().mainloop()