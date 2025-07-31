import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from tkinter.scrolledtext import ScrolledText
import threading
import urllib.request
import json
import os

MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
MISSING_SERVERS_URL = "https://magicdippyegg.github.io/Minecraft-Version-Downloader/missing_servers.json"
MISSING_CLIENTS_URL = "https://magicdippyegg.github.io/Minecraft-Version-Downloader/missing_clients.json"

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Minecraft Version Downloader")
        self.geometry("900x600")
        self.style = ttk.Style(self)
        self.style.configure('Treeview', rowheight=24)

        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=0)
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=2)

        # Progress bar for loading versions (spans both columns)
        self.load_progress = ttk.Progressbar(self, mode='indeterminate')
        self.load_progress.grid(row=0, column=0, columnspan=2, sticky='ew', padx=10, pady=10)

        # Search bar frame
        search_frame = ttk.Frame(self)
        search_frame.grid(row=1, column=0, columnspan=2, sticky='ew', padx=10, pady=(0, 10))
        search_frame.columnconfigure(0, weight=1)
        search_frame.columnconfigure(1, weight=0)

        self.search_entry = ttk.Entry(search_frame)
        self.search_entry.grid(row=0, column=0, sticky='ew', padx=(0, 5))
        self.search_entry.bind("<Return>", self.perform_search_event)

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
        self.missing_versions_map = {} # Stores missing_servers data: id -> server_url
        # NEW: Stores missing_clients data: id -> client_url & above (initially)
        self.custom_client_versions = []

        threading.Thread(target=self.load_versions, daemon=True).start()

    def load_versions(self):
        try:
            self.load_progress.start(10)
            mojang_versions = []
            try:
                # Load main manifest
                resp = urllib.request.urlopen(MANIFEST_URL)
                manifest = json.load(resp)
                mojang_versions = manifest["versions"]
            except Exception as e:
                messagebox.showwarning("Warning", f"Could not load official Mojang manifest:\n{e}. Only custom versions may be available.")

            # Load missing servers manifest
            try:
                resp_missing_servers = urllib.request.urlopen(MISSING_SERVERS_URL)
                missing_data_servers = json.load(resp_missing_servers)
                for entry in missing_data_servers.get("versions", []):
                    self.missing_versions_map[entry["id"]] = entry["server_url"]
            except Exception as e:
                print(f"Warning: Failed to load fallback server list: {e}")
                messagebox.showwarning("Warning", f"Could not load fallback server list:\n{e}")

            # NEW: Load missing clients manifest
            try:
                resp_missing_clients = urllib.request.urlopen(MISSING_CLIENTS_URL)
                missing_data_clients = json.load(resp_missing_clients)
                # Store custom clients to be merged and sorted
                self.custom_client_versions = missing_data_clients.get("versions", [])
            except Exception as e:
                print(f"Warning: Failed to load custom client list: {e}")
                messagebox.showwarning("Warning", f"Could not load custom client list:\n{e}")

            # NEW: Merge and sort all versions (Mojang + custom clients)
            self.all_versions = self._merge_and_sort_versions(mojang_versions, self.custom_client_versions)

            self.update_version_list(self.all_versions)
        except Exception as e:
            messagebox.showerror("Error", f"An unexpected error occurred during loading:\n{e}")
        finally:
            self.load_progress.stop()
            self.load_progress.grid_remove()

    def _merge_and_sort_versions(self, mojang_versions, custom_versions):
        """
        Merges Mojang versions and custom client versions, then sorts them
        respecting the 'above' dependency for custom clients.
        Custom versions will generally appear *before* their 'above' target if possible,
        or at the beginning if no 'above' target is found or if the target is not in the list.
        """
        # Create a dictionary for quick lookup of all versions (official + custom, by ID)
        all_versions_map = {v["id"]: v for v in mojang_versions}
        for v in custom_versions:
            all_versions_map[v["id"]] = v # Custom versions can overwrite or add new IDs

        final_ordered_versions = []
        # Keep track of versions already added to the final list to avoid duplicates
        added_to_final = set()

        # Simple approach for sorting:
        # First, add all official Mojang versions.
        for v in mojang_versions:
            final_ordered_versions.append(v)
            added_to_final.add(v["id"])

        # Now, iterate through custom versions and try to insert them based on 'above'.
        # We need a robust way to insert. We can build a graph for a proper topological sort,
        # but for simple 'above' cases, we can repeatedly try to insert until no more can be placed.

        # Create a list of custom versions that still need to be placed.
        unplaced_custom_versions = [v for v in custom_versions if v["id"] not in added_to_final]

        # Loop to try placing versions that have an 'above' dependency.
        # This will run as long as we successfully place versions in an iteration.
        placed_this_iteration = True
        while placed_this_iteration and unplaced_custom_versions:
            placed_this_iteration = False
            next_unplaced_custom = [] # Collect versions that still can't be placed this round

            for custom_v in unplaced_custom_versions:
                custom_id = custom_v["id"]
                above_id = custom_v.get("above")

                if above_id and above_id in added_to_final:
                    # Find the index of the 'above_id' version in the current final list
                    insert_index = -1
                    for i, v_in_final in enumerate(final_ordered_versions):
                        if v_in_final["id"] == above_id:
                            insert_index = i
                            break

                    if insert_index != -1:
                        # Insert the custom version directly before its 'above' target
                        final_ordered_versions.insert(insert_index, custom_v)
                        added_to_final.add(custom_id)
                        placed_this_iteration = True
                    else:
                        # Should not happen if above_id is in added_to_final, but for safety
                        next_unplaced_custom.append(custom_v)
                elif not above_id:
                    # If no 'above' specified, or 'above' target not found in the manifest,
                    # simply append it to the beginning of the list.
                    # This will put them at the very top if no 'above' constraint pulls them down.
                    final_ordered_versions.insert(0, custom_v)
                    added_to_final.add(custom_id)
                    placed_this_iteration = True
                else: # above_id is specified but not yet in the final list
                    next_unplaced_custom.append(custom_v)

            unplaced_custom_versions = next_unplaced_custom # Update for the next iteration

        # Any remaining custom versions that could not be placed due to missing 'above' targets
        # or complex unresolvable dependencies will be appended to the very end.
        for v in unplaced_custom_versions:
            if v["id"] not in added_to_final: # Double check to avoid accidental duplicates
                final_ordered_versions.append(v)
                added_to_final.add(v["id"])


        return final_ordered_versions

    def update_version_list(self, versions_to_display):
        """Clears and repopulates the Treeview with the given list of versions."""
        for item in self.vers_list.get_children():
            self.vers_list.delete(item)
        self.current_display_versions = versions_to_display
        for idx, v in enumerate(self.current_display_versions):
            # Ensure custom client versions have 'type' and 'releaseTime' for display
            display_type = v.get("type", "Custom Client") # Default type for custom
            display_time = v.get("releaseTime", "N/A")    # Default time for custom
            self.vers_list.insert("", "end", iid=idx,
                values=(v["id"], display_type, display_time))

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
               search_term in v.get("type", "").lower() # Handle missing 'type' for custom versions
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

        # Reset state and show loading message immediately
        self.show_details(f"Loading details for {v['id']}...")
        self.download_server_btn.config(state=tk.DISABLED)
        self.download_client_btn.config(state=tk.DISABLED)
        self.tech_btn.config(state=tk.DISABLED)

        # Store the currently selected version's raw data for the thread
        self.current_selected_version_data = v

        # Start a new thread to load version details
        threading.Thread(target=self._load_version_details_thread, daemon=True).start()

    def _load_version_details_thread(self):
        # Retrieve the version data that was stored by on_select
        v = self.current_selected_version_data

        vjson = {} # Details from Mojang's full version JSON
        client_url = None
        server_url = None
        tech_info = []
        mojang_details_loaded = False
        message_prefix = "" # To prepend to details text if there's a warning

        # Try to load full Mojang details if this version has a 'url' field (which Mojang versions do)
        if 'url' in v:
            try:
                resp = urllib.request.urlopen(v["url"])
                vjson = json.load(resp)
                downloads = vjson.get('downloads', {})
                client_url = downloads.get('client', {}).get('url')
                server_url = downloads.get('server', {}).get('url')
                mojang_details_loaded = True
            except Exception as e:
                # Only show a warning if Mojang details failed to load AND it was expected to have them
                message_prefix = f"Warning: Could not load full Mojang details for {v['id']}:\n{e}\nChecking fallback lists...\n\n"
        # else: Removed: "Displaying custom client details for [VERSION]"
            # This is likely a custom client version without a Mojang URL, no special prefix needed now.


        # --- EXISTING FALLBACK LOGIC for Server URL ---
        if not server_url and v["id"] in self.missing_versions_map:
            server_url = self.missing_versions_map[v["id"]]

        # --- Use client_url from custom_client_versions if available and not already set by Mojang ---
        # Find this version in our custom_client_versions list to get its specific client_url
        custom_v_details = next((item for item in self.custom_client_versions if item["id"] == v["id"]), None)
        if custom_v_details and "client_url" in custom_v_details and not client_url:
            client_url = custom_v_details["client_url"]

        lines = [
            f"ID: {v.get('id', 'N/A')}",
            f"Type: {v.get('type', 'Unknown Type')}", # Default type changed
            f"Release Time: {v.get('releaseTime', 'N/A')}" # Default time for custom clients
        ]

        # Add details from Mojang's vjson if it was successfully loaded
        if mojang_details_loaded:
            if 'mainClass' in vjson:
                lines.append(f"Main Class: {vjson['mainClass']}")
            if 'complianceLevel' in vjson:
                lines.append(f"Compliance Level: {vjson['complianceLevel']}")

        # Report client jar info if available
        if client_url:
            # Determine source of client URL
            client_source = "Mojang Servers"
            if custom_v_details and client_url == custom_v_details.get('client_url'):
                client_source = "Not from Mojang's Servers" # Changed from "Custom Client List"
            elif not mojang_details_loaded: # If Mojang details weren't loaded but a URL was found (e.g., from fallback not handled above)
                client_source = "Unknown Source (Not Mojang)"


            # If client URL came from Mojang's downloads, get its size
            if mojang_details_loaded and client_url == vjson.get('downloads', {}).get('client', {}).get('url'):
                 client_size = vjson.get('downloads', {}).get('client', {}).get('size', 'n/a')
                 lines.append(f"Client Jar Size: {client_size} bytes (Source: {client_source})")
            else:
                 lines.append(f"Client Jar: Available (Source: {client_source})")

        # Report server jar info if available (can be from Mojang or fallback)
        if server_url:
            server_source = "Mojang Servers"
            if v["id"] in self.missing_versions_map and server_url == self.missing_versions_map[v["id"]]:
                server_source = "Not from Mojang's Servers (Fallback)" # Changed similar to client
            elif not mojang_details_loaded:
                server_source = "Unknown Source (Not Mojang)"


            if mojang_details_loaded and server_url == vjson.get('downloads', {}).get('server', {}).get('url'):
                 server_size = vjson.get('downloads', {}).get('server', {}).get('size', 'n/a')
                 lines.append(f"Server Jar Size: {server_size} bytes (Source: {server_source})")
            else:
                 lines.append(f"Server Jar: Available (Source: {server_source})")


        # prepare technical info ONLY from Mojang's vjson, as fallback only provides URL
        if mojang_details_loaded:
            ai = vjson.get('assetIndex', {})
            if ai:
                tech_info.append(f"AssetIndex URL: {ai.get('url')}")
                tech_info.append(f"AssetIndex SHA1: {ai.get('sha1')}")
            for part in ('client','server'):
                info = vjson.get('downloads', {}).get(part, {})
                if info and info.get('url'): # Check if URL exists in Mojang data
                    tech_info.append(f"{part.capitalize()} URL: {info.get('url')}")
                    tech_info.append(f"{part.capitalize()} SHA1: {info.get('sha1')}")
            tech_info.append(f"Libraries Count: {len(vjson.get('libraries', []))}")

        # Add custom client's URL to tech info if it exists
        if custom_v_details and "client_url" in custom_v_details:
             tech_info.append(f"Client URL (Not from Mojang): {custom_v_details['client_url']}") # Renamed for tech info

        # Schedule the UI update on the main thread using self.after()
        self.after(0, self._update_ui_after_details_load,
                   message_prefix + "\n".join(lines), client_url, server_url, tech_info)

    def _update_ui_after_details_load(self, details_text, client_url, server_url, tech_info):
        """
        Updates the UI elements on the main thread after version details have been loaded.
        """
        self.show_details(details_text)

        # Update instance variables
        self.client_url = client_url
        self.server_url = server_url
        self.tech_info = tech_info

        # Re-enable/disable buttons based on the newly loaded URLs and tech info
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
                    # Re-trigger on_select to re-evaluate button states
                    # This is cleaner than re-implementing the logic here
                    self.on_select(None) # Pass None as event as we are not reacting to a real event
            else:
                self.download_server_btn.config(state=tk.DISABLED)
                self.download_client_btn.config(state=tk.DISABLED)
                self.tech_btn.config(state=tk.DISABLED)

            self.search_button.config(state=tk.NORMAL)
            self.search_entry.config(state=tk.NORMAL)


if __name__ == "__main__":
    App().mainloop()