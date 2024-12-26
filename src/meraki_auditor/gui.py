import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Optional, Dict
from .core import MerakiConnection, PlaybookExecutor, ReportGenerator
from .playbook import Playbook
from .utils import DirectoryManager
from datetime import datetime

class AuditorGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Meraki Network Auditor")
        
        # Initialize variables first
        self.status_var = tk.StringVar(value="Ready")
        self.progress_var = tk.DoubleVar(value=0)
        
        # Initialize other attributes
        self.connection: Optional[MerakiConnection] = None
        self.executor: Optional[PlaybookExecutor] = None
        self.report_generator: Optional[ReportGenerator] = None
        self.networks: List[Dict] = []
        self.selected_networks: List[str] = []
        
    def prompt_api_key(self) -> Optional[str]:
        """Prompt user for Meraki API key"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Enter API Key")
        dialog.geometry("400x150")
        dialog.transient(self.root)
        dialog.grab_set()  # Make dialog modal
        
        # Center the dialog
        dialog.geometry("+%d+%d" % (
            self.root.winfo_rootx() + 50,
            self.root.winfo_rooty() + 50))
        
        label = ttk.Label(dialog, text="Please enter your Meraki API key:")
        label.pack(pady=10)
        
        api_key = tk.StringVar()
        entry = ttk.Entry(dialog, textvariable=api_key, width=50)
        entry.pack(pady=10)
        
        result = None
        
        def on_submit():
            nonlocal result
            if api_key.get().strip():
                result = api_key.get().strip()
                dialog.destroy()
            else:
                messagebox.showerror("Error", "API key cannot be empty")
        
        submit_btn = ttk.Button(dialog, text="Submit", command=on_submit)
        submit_btn.pack(pady=10)
        
        # Wait for dialog to close
        dialog.wait_window()
        return result
    
    def select_networks(self) -> List[str]:
        """Show network selection dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Networks")
        dialog.geometry("600x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Create frame for the network list
        frame = ttk.Frame(dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create treeview for networks
        tree = ttk.Treeview(frame, columns=("name", "id"), show="headings")
        tree.heading("name", text="Network Name")
        tree.heading("id", text="Network ID")
        tree.column("name", width=300)
        tree.column("id", width=250)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack the treeview and scrollbar
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Insert networks into treeview
        for network in self.networks:
            tree.insert("", tk.END, values=(network['name'], network['id']))
        
        selected_networks = []
        
        def on_submit():
            nonlocal selected_networks
            selected_items = tree.selection()
            selected_networks = [tree.item(item)["values"][1] for item in selected_items]
            dialog.destroy()
        
        # Add buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        select_all_btn = ttk.Button(btn_frame, text="Select All", 
                                  command=lambda: tree.selection_set(tree.get_children()))
        select_all_btn.pack(side=tk.LEFT, padx=5)
        
        clear_btn = ttk.Button(btn_frame, text="Clear Selection", 
                             command=lambda: tree.selection_remove(tree.selection()))
        clear_btn.pack(side=tk.LEFT, padx=5)
        
        submit_btn = ttk.Button(btn_frame, text="Submit", command=on_submit)
        submit_btn.pack(side=tk.RIGHT, padx=5)
        
        # Wait for dialog to close
        dialog.wait_window()
        return selected_networks
    
    def initialize_connection(self):
        """Initialize Meraki connection with API key"""
        api_key = self.prompt_api_key()
        if not api_key:
            messagebox.showerror("Error", "API key is required")
            self.root.quit()
            return False
        
        self.connection = MerakiConnection(api_key)
        
        # Set up callbacks for connection
        self.connection.set_callbacks(
            progress_callback=lambda p: self.progress_var.set(p),
            status_callback=lambda s: self.status_var.set(s)
        )
        
        try:
            if not self.connection.authenticate():
                messagebox.showerror("Error", "Invalid API key")
                return False
            
            self.networks = self.connection.load_networks()
            if not self.networks:
                messagebox.showwarning("Warning", "No networks found")
                return False
            
            selected_networks = self.select_networks()
            if not selected_networks:
                messagebox.showwarning("Warning", "No networks selected")
                return False
            
            self.connection.select_networks(selected_networks)
            self.executor = PlaybookExecutor(self.connection)
            self.report_generator = ReportGenerator(self.executor)
            return True
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to initialize: {str(e)}")
            return False
    
    def run(self):
        """Start the application"""
        if not self.initialize_connection():
            return
        
        self.setup_ui()
        self.root.mainloop()
    
    def setup_ui(self):
        """Setup the main UI after successful initialization"""
        # Configure main window
        self.root.geometry("1200x800")
        
        # Create main container with three panels
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # ===== NETWORK PANEL (LEFT) =====
        network_panel = ttk.LabelFrame(main_frame, text="Selected Networks and Devices", padding="5")
        network_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Network tree frame
        tree_frame = ttk.Frame(network_panel)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create network devices treeview
        network_tree = ttk.Treeview(tree_frame, columns=("type", "model", "serial"), show="tree headings")
        network_tree.heading("type", text="Type")
        network_tree.heading("model", text="Model")
        network_tree.heading("serial", text="Serial")
        network_tree.column("type", width=100)
        network_tree.column("model", width=150)
        network_tree.column("serial", width=150)
        
        # Add scrollbar to network tree
        network_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=network_tree.yview)
        network_tree.configure(yscrollcommand=network_scroll.set)
        
        network_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        network_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Populate network tree
        for network in self.networks:
            if network['id'] in self.selected_networks:
                network_node = network_tree.insert("", tk.END, text=network['name'], open=True)
                try:
                    devices = self.connection.dashboard.networks.getNetworkDevices(networkId=network['id'])
                    for device in devices:
                        device_values = (
                            device.get('productType', 'Unknown'),
                            device.get('model', 'Unknown'),
                            device.get('serial', 'Unknown')
                        )
                        network_tree.insert(network_node, tk.END, text=device.get('name', 'Unnamed'), 
                                          values=device_values)
                except Exception as e:
                    network_tree.insert(network_node, tk.END, text=f"Error loading devices: {str(e)}")
        
        # Add export button frame below tree
        network_button_frame = ttk.Frame(network_panel)
        network_button_frame.pack(fill=tk.X, pady=5)

        def export_device_inventory():
            """Export all devices from selected networks to CSV"""
            try:
                self.status_var.set("Exporting device inventory...")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                dir_manager = DirectoryManager()
                report_path = dir_manager.create_report_directory("device_inventory")
                
                all_devices = []
                for network in self.networks:
                    if network['id'] in self.selected_networks:
                        try:
                            devices = self.connection.dashboard.networks.getNetworkDevices(networkId=network['id'])
                            for device in devices:
                                device['networkName'] = network['name']
                                device['networkId'] = network['id']
                                all_devices.append(device)
                        except Exception as e:
                            messagebox.showerror("Error", 
                                               f"Failed to get devices for network {network['name']}: {str(e)}")
                
                if all_devices:
                    import pandas as pd
                    df = pd.DataFrame(all_devices)
                    
                    # Reorder columns to put important info first
                    important_cols = ['networkName', 'name', 'model', 'serial', 'productType', 
                                    'networkId', 'mac', 'lanIp', 'firmware', 'status']
                    cols = [col for col in important_cols if col in df.columns] + \
                          [col for col in df.columns if col not in important_cols]
                    df = df[cols]
                    
                    csv_path = report_path / f'device_inventory_{timestamp}.csv'
                    df.to_csv(csv_path, index=False)
                    
                    self.status_var.set("Device inventory exported successfully!")
                    messagebox.showinfo("Success", f"Device inventory exported to:\n{csv_path}")
                else:
                    messagebox.showwarning("Warning", "No devices found in selected networks")
                    
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export device inventory: {str(e)}")
                self.status_var.set("Export failed")
            finally:
                self.status_var.set("Ready")

        # Add export button
        export_btn = ttk.Button(network_button_frame, text="Export Device Inventory", 
                               command=export_device_inventory)
        export_btn.pack(side=tk.LEFT, padx=5)
        
        # ===== PLAYBOOK PANEL (MIDDLE) =====
        playbook_panel = ttk.LabelFrame(main_frame, text="Available Playbooks", padding="5")
        playbook_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        
        # Create playbook listbox
        playbook_frame = ttk.Frame(playbook_panel)
        playbook_frame.pack(fill=tk.BOTH, expand=True)
        
        playbook_list = tk.Listbox(playbook_frame, width=30)
        playbook_list.pack(side=tk.LEFT, fill=tk.Y)
        
        # Add scrollbar to playbook list
        playbook_scroll = ttk.Scrollbar(playbook_frame, orient=tk.VERTICAL, command=playbook_list.yview)
        playbook_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        playbook_list.configure(yscrollcommand=playbook_scroll.set)
        
        # Create execution panel (modified from original)
        execution_panel = ttk.Frame(main_frame)
        execution_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Add device filter (new)
        filter_frame = ttk.LabelFrame(execution_panel, text="Device Filters", padding="5")
        filter_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Device type filter
        type_frame = ttk.Frame(filter_frame)
        type_frame.pack(fill=tk.X, pady=2)
        ttk.Label(type_frame, text="Device Type:").pack(side=tk.LEFT)
        type_var = tk.StringVar(value="all")
        type_combo = ttk.Combobox(type_frame, textvariable=type_var, 
                                 values=["all"] + list(set(d.get('productType', '') 
                                                         for n in self.networks 
                                                         for d in self.connection.dashboard.networks.getNetworkDevices(networkId=n['id']))))
        type_combo.pack(side=tk.LEFT, padx=5)
        
        def apply_device_filter(*args):
            """Filter devices in tree based on selected type"""
            filter_type = type_var.get()
            for network_id in network_tree.get_children():
                for device_id in network_tree.get_children(network_id):
                    device_type = network_tree.item(device_id)['values'][0]
                    if filter_type == "all" or device_type == filter_type:
                        network_tree.item(device_id, tags=())  # Show
                    else:
                        network_tree.item(device_id, tags=('hidden',))  # Hide
            
            network_tree.tag_configure('hidden', hide=True)
        
        type_combo.bind('<<ComboboxSelected>>', apply_device_filter)
        
        # Add filter button
        ttk.Button(filter_frame, text="Clear Filters", 
                   command=lambda: [type_var.set("all"), apply_device_filter()]).pack(pady=5)
        
        # Preview section
        preview_frame = ttk.LabelFrame(execution_panel, text="Playbook Preview", padding="5")
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        # Preview text widget
        preview_text = tk.Text(preview_frame, wrap=tk.WORD, height=10, width=50)
        preview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        preview_scroll = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL, command=preview_text.yview)
        preview_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        preview_text.configure(yscrollcommand=preview_scroll.set)
        preview_text.configure(state='disabled')
        
        # Execution section
        execution_frame = ttk.LabelFrame(execution_panel, text="Execution", padding="5")
        execution_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Status label
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(execution_frame, textvariable=self.status_var)
        status_label.pack(fill=tk.X, pady=5)
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(execution_frame, mode='determinate', variable=self.progress_var)
        progress_bar.pack(fill=tk.X, pady=5)
        
        # Button frame
        button_frame = ttk.Frame(execution_panel)
        button_frame.pack(fill=tk.X, pady=5)
        
        # Load available playbooks
        dir_manager = DirectoryManager()
        playbooks = dir_manager.get_playbooks()
        
        for playbook_name in playbooks.keys():
            playbook_list.insert(tk.END, playbook_name)
        
        def update_preview(*args):
            """Update preview when a playbook is selected"""
            selection = playbook_list.curselection()
            if not selection:
                return
            
            playbook_name = playbook_list.get(selection[0])
            playbook_path = playbooks[playbook_name]
            
            try:
                playbook = Playbook(playbook_path)
                playbook.load()
                
                preview_text.configure(state='normal')
                preview_text.delete(1.0, tk.END)
                
                # Format preview content
                preview_content = f"Name: {playbook.config.name}\n"
                preview_content += f"Description: {playbook.config.description}\n"
                preview_content += f"Version: {playbook.config.version}\n"
                preview_content += f"Author: {playbook.config.author}\n\n"
                preview_content += "API Calls:\n"
                
                for call in playbook.api_calls:
                    preview_content += f"\n- {call.name}:\n"
                    preview_content += f"  Endpoint: {call.endpoint}\n"
                    preview_content += f"  Method: {call.method}\n"
                    if call.filters:
                        preview_content += f"  Filters: {call.filters}\n"
                    preview_content += f"  Output: {call.output}\n"
                
                preview_text.insert(1.0, preview_content)
                preview_text.configure(state='disabled')
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load playbook: {str(e)}")
        
        def execute_playbook():
            """Modified execute_playbook to consider device filters and show progress"""
            selection = playbook_list.curselection()
            if not selection:
                messagebox.showwarning("Warning", "Please select a playbook")
                return
            
            playbook_name = playbook_list.get(selection[0])
            playbook_path = playbooks[playbook_name]
            
            # Get filtered devices
            filtered_type = type_var.get()
            if filtered_type != "all":
                # Update connection's device cache with only filtered devices
                for network_id in self.connection.selected_networks:
                    devices = self.connection.dashboard.networks.getNetworkDevices(networkId=network_id)
                    self.connection.devices[network_id] = [
                        d for d in devices if d.get('productType', '') == filtered_type
                    ]
            
            try:
                self.status_var.set("Loading playbook...")
                self.progress_var.set(0)
                
                self.executor.load_playbook(playbook_path)
                
                # Set up callbacks
                self.executor.set_callbacks(
                    progress_callback=lambda p: self.progress_var.set(p),
                    status_callback=lambda s: self.status_var.set(s)
                )
                
                results = self.executor.execute()
                
                self.status_var.set("Generating report...")
                self.progress_var.set(90)
                
                report_path = self.report_generator.generate_report('csv', playbook_name)
                
                self.status_var.set("Complete!")
                self.progress_var.set(100)
                
                messagebox.showinfo("Success", 
                                  f"Playbook executed successfully!\nReport saved to: {report_path}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to execute playbook: {str(e)}")
                self.status_var.set("Failed")
            finally:
                self.progress_var.set(0)
        
        # Bind playbook selection to preview update
        playbook_list.bind('<<ListboxSelect>>', update_preview)
        
        # Add execute button
        execute_btn = ttk.Button(button_frame, text="Execute Playbook", command=execute_playbook)
        execute_btn.pack(side=tk.RIGHT, padx=5)
        
        # Add refresh button
        refresh_btn = ttk.Button(button_frame, text="Refresh Playbooks", 
                               command=lambda: [playbook_list.delete(0, tk.END)] + 
                                            [playbook_list.insert(tk.END, name) 
                                             for name in dir_manager.get_playbooks().keys()])
        refresh_btn.pack(side=tk.RIGHT, padx=5) 