import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from tkinter.scrolledtext import ScrolledText
import threading
import urllib.request
import json
import os

# Define the LiteLoader versions API URL
LITELOADER_VERSIONS_URL = "http://dl.liteloader.com/versions/versions.json"
# Base URL for the Jenkins LiteLoader Installer builds
JENKINS_INSTALLER_BASE_URL = "http://jenkins.liteloader.com/job/"

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LiteLoader Version Downloader")
        self.geometry("900x600")
        self.style = ttk.Style(self)
        self.style.configure('Treeview', rowheight=24)

        # Layout: progress at top, then MC version/search, then list/details below
        self.rowconfigure(0, weight=0) # For progress bar
        self.rowconfigure(1, weight=0) # For MC version selector
        self.rowconfigure(2, weight=0) # For search bar
        self.rowconfigure(3, weight=1) # For main content (loader list / details)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=2)

        # Progress bar for loading (spans both columns)
        self.load_progress = ttk.Progressbar(self, mode='indeterminate')
        self.load_progress.grid(row=0, column=0, columnspan=2, sticky='ew', padx=10, pady=10)

        # Game version selection frame
        game_version_frame = ttk.Frame(self)
        game_version_frame.grid(row=1, column=0, columnspan=2, sticky='ew', padx=10, pady=(0, 10))
        tk.Label(game_version_frame, text="Minecraft Version:").pack(side=tk.LEFT, padx=(0, 5))
        self.game_version_combo = ttk.Combobox(game_version_frame, state='readonly')
        self.game_version_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.game_version_combo.bind("<<ComboboxSelected>>", self._on_game_version_selected)
        
        # Search bar
        search_frame = ttk.Frame(self)
        search_frame.grid(row=2, column=0, columnspan=2, sticky='ew', padx=10, pady=(0, 10))
        tk.Label(search_frame, text="Search LiteLoader Versions:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_entry = ttk.Entry(search_frame)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.search_entry.bind("<KeyRelease>", self._apply_search_filter)

        # LiteLoader versions list (Treeview)
        self.vers_list = ttk.Treeview(self, columns=('Version', 'File', 'MD5'), show='headings')
        self.vers_list.heading('Version', text='LiteLoader Version')
        self.vers_list.heading('File', text='File Name (from JSON)')
        self.vers_list.heading('MD5', text='MD5 Checksum')
        self.vers_list.column('Version', width=150, stretch=tk.NO)
        self.vers_list.column('File', width=250, stretch=tk.YES)
        self.vers_list.column('MD5', width=200, stretch=tk.NO)
        self.vers_list.grid(row=3, column=0, sticky='nsew', padx=(10, 5), pady=(0, 10))
        self.vers_list.bind("<<TreeviewSelect>>", self._on_liteloader_version_selected)

        # Scrollbar for versions list
        scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.vers_list.yview)
        self.vers_list.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=3, column=0, sticky='nse', padx=(0, 10), pady=(0, 10)) # Adjusted to be next to treeview

        # Details/Download frame
        details_frame = ttk.LabelFrame(self, text="LiteLoader Details and Download")
        details_frame.grid(row=3, column=1, sticky='nsew', padx=(5, 10), pady=(0, 10))
        details_frame.columnconfigure(0, weight=1)

        self.details_text = ScrolledText(details_frame, wrap=tk.WORD, state=tk.DISABLED, height=10)
        self.details_text.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.download_installer_btn = ttk.Button(details_frame, text="Download LiteLoader Installer (via Jenkins)", command=self._start_download_installer, state=tk.DISABLED)
        self.download_installer_btn.pack(pady=5)
        
        # Progress bar for downloads - now uses pack
        self.download_progress = ttk.Progressbar(details_frame, mode='determinate')
        self.download_progress.pack(pady=5, fill=tk.X, padx=10)
        self.download_progress.pack_forget() # Hide initially


        self.game_versions = {} # Stores fetched LiteLoader data
        self.current_liteloader_versions = [] # Stores LiteLoader versions for the selected MC version

        self._load_game_versions()


    def _load_game_versions(self):
        self.load_progress.start()
        self.load_progress.grid() # Ensure it's visible when starting
        self.game_version_combo.config(state=tk.DISABLED)
        threading.Thread(target=self._fetch_game_versions_from_url, daemon=True).start()

    def _fetch_game_versions_from_url(self):
        try:
            with urllib.request.urlopen(LITELOADER_VERSIONS_URL) as response:
                liteloader_data = json.loads(response.read().decode('utf-8'))
            
            # The JSON structure has a "versions" key with Minecraft versions
            self.game_versions = liteloader_data.get('versions', {})
            mc_versions = sorted(self.game_versions.keys(), reverse=True, key=self._sort_version_string) # Sort MC versions naturally

            self.after(0, lambda: self._update_game_versions_ui(mc_versions))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", f"Failed to load LiteLoader versions from {LITELOADER_VERSIONS_URL}:\n{e}\n\nPlease check your internet connection or if the LiteLoader API is down."))
            self.after(0, self.load_progress.stop)
            self.after(0, self.load_progress.grid_remove) # Hide on error
            self.after(0, lambda: self.game_version_combo.config(state='readonly'))

    def _update_game_versions_ui(self, mc_versions):
        self.game_version_combo['values'] = mc_versions
        if mc_versions:
            self.game_version_combo.set(mc_versions[0]) # Set default to latest MC version
            self._on_game_version_selected(event=None) # Trigger loading of LiteLoader versions for default
        self.load_progress.stop()
        self.load_progress.grid_remove() # Hide the progress bar
        self.game_version_combo.config(state='readonly')

    def _on_game_version_selected(self, event):
        selected_mc_version = self.game_version_combo.get()
        if selected_mc_version:
            self.load_progress.start()
            self.load_progress.grid() # Show when new selection made
            self.vers_list.delete(*self.vers_list.get_children()) # Clear previous entries
            self.download_installer_btn.config(state=tk.DISABLED) # Disable download button
            self.details_text.config(state=tk.NORMAL)
            self.details_text.delete(1.0, tk.END)
            self.details_text.config(state=tk.DISABLED)
            threading.Thread(target=self._fetch_liteloader_versions, args=(selected_mc_version,), daemon=True).start()

    def _fetch_liteloader_versions(self, mc_version):
        self.current_liteloader_versions = []
        liteloader_for_mc = self.game_versions.get(mc_version, {})
        
        versions_to_display = []

        for key_type in ['artefacts', 'snapshots']:
            if key_type in liteloader_for_mc:
                artefacts = liteloader_for_mc[key_type].get('com.mumfrey:liteloader', {})
                for liteloader_build_id, build_info in artefacts.items():
                    if liteloader_build_id == 'latest': # Skip 'latest' as we'll show actual builds
                        continue
                    
                    version = build_info.get('version')
                    file_name = build_info.get('file') # This is the file name for the core mod from JSON
                    md5 = build_info.get('md5')
                    
                    maven_download_url = None
                    jenkins_download_url = None

                    # Construct the old Maven repository URL (may be broken for direct download)
                    repo_url = liteloader_for_mc.get('repo', {}).get('url')
                    if repo_url and file_name and version:
                        cleaned_repo_url = repo_url.replace('\\', '')
                        group_path = "com/mumfrey/liteloader".replace('.', '/')
                        maven_download_url = f"{cleaned_repo_url}{group_path}/{version}/{file_name}"
                    
                    # Construct the Jenkins installer URL based on user's feedback
                    if mc_version:
                        # Extract the base MC version part (e.g., "1.12.2" from "1.12.2-SNAPSHOT")
                        base_mc_version_for_installer = mc_version.split('-')[0]
                        
                        jenkins_job_name = f"LiteLoaderInstaller%20{base_mc_version_for_installer}/"
                        jenkins_artifact_path = "lastSuccessfulBuild/artifact/build/libs/"
                        # This filename pattern assumes '00-SNAPSHOT' for the installer build
                        jenkins_installer_filename = f"liteloader-installer-{base_mc_version_for_installer}-00-SNAPSHOT.jar"
                        
                        jenkins_download_url = f"{JENKINS_INSTALLER_BASE_URL}{jenkins_job_name}{jenkins_artifact_path}{jenkins_installer_filename}"

                    if version and file_name: # Only add if we have basic info
                        versions_to_display.append({
                            'mc_version': mc_version,
                            'liteloader_version': version,
                            'file_name': file_name, # Original file name from JSON
                            'md5': md5,
                            'maven_download_url': maven_download_url,
                            'jenkins_download_url': jenkins_download_url,
                            'details': build_info
                        })

        # Sort LiteLoader versions naturally
        self.current_liteloader_versions = sorted(versions_to_display, key=lambda x: self._sort_version_string(x['liteloader_version']), reverse=True)
        self.after(0, self._populate_liteloader_list)
        self.after(0, self.load_progress.stop)
        self.after(0, self.load_progress.grid_remove) # Hide the progress bar after populating

    def _populate_liteloader_list(self):
        for iid in self.vers_list.get_children():
            self.vers_list.delete(iid)
        
        for version_info in self.current_liteloader_versions:
            self.vers_list.insert('', tk.END, values=(
                version_info['liteloader_version'], 
                version_info['file_name'], # Display file name from JSON
                version_info['md5']
            ))
        self._apply_search_filter() # Apply any existing search filter

    def _apply_search_filter(self, event=None):
        search_term = self.search_entry.get().strip().lower()
        
        for iid in self.vers_list.get_children():
            self.vers_list.delete(iid) # Clear all entries

        filtered_versions = [
            v for v in self.current_liteloader_versions
            if search_term in v['liteloader_version'].lower() or
               search_term in v['file_name'].lower()
        ]

        for version_info in filtered_versions:
            self.vers_list.insert('', tk.END, values=(
                version_info['liteloader_version'],
                version_info['file_name'],
                version_info['md5']
            ))

    def _on_liteloader_version_selected(self, event):
        selected_items = self.vers_list.selection()
        if selected_items:
            item_values = self.vers_list.item(selected_items[0], 'values')
            selected_liteloader_version_str = item_values[0] 
            selected_file_name = item_values[1] # Original file name from JSON

            selected_version_data = next((v for v in self.current_liteloader_versions
                                           if v['liteloader_version'] == selected_liteloader_version_str and 
                                              v['file_name'] == selected_file_name), None)

            if selected_version_data:
                # Enable download button if Jenkins URL exists
                self.download_installer_btn.config(state=tk.NORMAL if selected_version_data.get('jenkins_download_url') else tk.DISABLED)
                self._display_details(selected_version_data)
            else:
                self.download_installer_btn.config(state=tk.DISABLED)
                self._display_details(None)
        else:
            self.download_installer_btn.config(state=tk.DISABLED)
            self._display_details(None)

    def _display_details(self, version_data):
        self.details_text.config(state=tk.NORMAL)
        self.details_text.delete(1.0, tk.END)
        if version_data:
            details_str = f"Minecraft Version: {version_data.get('mc_version')}\n"
            details_str += f"LiteLoader Version: {version_data.get('liteloader_version')}\n"
            details_str += f"File Name (from JSON): {version_data.get('file_name')}\n"
            details_str += f"MD5: {version_data.get('md5', 'N/A')}\n\n"
            
            details_str += f"Maven Download URL (Core Mod - may be broken): {version_data.get('maven_download_url', 'N/A')}\n"
            details_str += f"Jenkins Installer URL (Recommended): {version_data.get('jenkins_download_url', 'N/A')}\n\n"
            
            # Add more detailed info from the 'details' dict if available
            raw_details = version_data.get('details', {})
            details_str += "Raw Details:\n"
            for key, value in raw_details.items():
                if key not in ['file', 'version', 'md5']: # Avoid re-listing basic info
                    details_str += f"  {key}: {value}\n"

        else:
            details_str = "Select a LiteLoader version to see details."
        self.details_text.insert(tk.END, details_str)
        self.details_text.config(state=tk.DISABLED)

    def _start_download_installer(self):
        selected_items = self.vers_list.selection()
        if not selected_items:
            messagebox.showerror("Error", "Please select a LiteLoader version to download.")
            return

        item_values = self.vers_list.item(selected_items[0], 'values')
        selected_liteloader_version_str = item_values[0]
        selected_file_name_from_json = item_values[1]

        selected_version_data = next((v for v in self.current_liteloader_versions
                                       if v['liteloader_version'] == selected_liteloader_version_str and
                                          v['file_name'] == selected_file_name_from_json), None)

        download_url = selected_version_data.get('jenkins_download_url') if selected_version_data else None

        if not download_url:
            messagebox.showerror("Error", "Could not find a valid Jenkins Installer download URL for the selected LiteLoader version.")
            return

        # Derive initial filename from the Jenkins URL for saving
        initial_filename = download_url.split('/')[-1] if download_url else "liteloader-installer.jar"
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".jar",
            initialfile=initial_filename,
            filetypes=[("JAR Files", "*.jar"), ("All Files", "*.*")]
        )

        if file_path:
            self.download_installer_btn.config(state=tk.DISABLED)
            self.game_version_combo.config(state=tk.DISABLED)
            self.download_progress.config(mode='determinate', value=0) # Set to determinate and reset value
            self.download_progress.pack(pady=5, fill=tk.X, padx=10) # Make it visible
            
            # Start download in a new thread to keep UI responsive
            threading.Thread(target=self._download_file_thread, args=(download_url, file_path), daemon=True).start()
        else:
            # User cancelled, so reset UI
            self._reset_ui_after_download()

    def _report_hook(self, block_num, block_size, total_size):
        """Callback for urllib.request.urlretrieve to update progress bar."""
        if total_size > 0:
            percent = (block_num * block_size * 100) / total_size
            self.download_progress['value'] = min(percent, 100)
            self.update_idletasks() # Safe to call for progress bar updates

    def _download_file_thread(self, url, path):
        """The final download thread."""
        try:
            # No need to set mode to determinate here, already set in _start_download_installer
            urllib.request.urlretrieve(url, path, reporthook=self._report_hook)
            messagebox.showinfo("Downloaded", f"LiteLoader Installer saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"Download failed:\n{e}\n\nNote: This might be due to the LiteLoader API being offline or the specific file no longer existing at the URL. Please check the 'Jenkins Installer URL' in the details pane and try manually if necessary, or report it if the issue persists across versions.")
        finally:
            # Schedule UI reset on the main thread
            self.after(0, self._reset_ui_after_download)

    def _reset_ui_after_download(self):
        """Resets the UI elements to their active state."""
        self.download_progress.stop()
        self.download_progress.pack_forget()
        # Re-enable download button only if an item is still selected in the list
        if self.vers_list.selection():
            self.download_installer_btn.config(state=tk.NORMAL)
        else:
             self.download_installer_btn.config(state=tk.DISABLED) # Ensure it's disabled if nothing selected
        self.game_version_combo.config(state='readonly')
        self.load_progress.grid_remove() # Ensure load progress is hidden after all operations

    def _sort_version_string(self, version_str):
        """Helper for natural sorting of version strings."""
        parts = []
        temp_num = ""
        for char in version_str:
            if char.isdigit():
                temp_num += char
            else:
                if temp_num:
                    parts.append(int(temp_num))
                    temp_num = ""
                parts.append(char)
        if temp_num:
            parts.append(int(temp_num))
        return parts

if __name__ == "__main__":
    App().mainloop()