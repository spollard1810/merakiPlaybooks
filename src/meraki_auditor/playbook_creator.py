import tkinter as tk
from tkinter import ttk, messagebox
import yaml
from pathlib import Path
from typing import Dict, List, Optional
import meraki
from .utils import DirectoryManager

class PlaybookCreatorGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Meraki Playbook Creator")
        self.root.geometry("1000x800")
        
        # Initialize Meraki API documentation
        self.api_endpoints = {
            "networks": {
                "devices": {
                    "method": "getNetworkDevices",
                    "description": "List the devices in a network",
                    "parameters": ["networkId"]
                },
                "clients": {
                    "method": "getNetworkClients",
                    "description": "List the clients in a network",
                    "parameters": ["networkId", "timespan"]
                },
                "vlans": {
                    "method": "getNetworkVlans",
                    "description": "List the VLANs in a network",
                    "parameters": ["networkId"]
                },
                "switch": {
                    "settings": {
                        "method": "getNetworkSwitchSettings",
                        "description": "Get switch network settings",
                        "parameters": ["networkId"]
                    },
                    "dhcp": {
                        "method": "getNetworkSwitchDhcpServerPolicy",
                        "description": "Get DHCP server policy",
                        "parameters": ["networkId"]
                    },
                    "mtu": {
                        "method": "getNetworkSwitchMtu",
                        "description": "Get switch MTU configuration",
                        "parameters": ["networkId"]
                    },
                    "stormControl": {
                        "method": "getNetworkSwitchStormControl",
                        "description": "Get storm control configuration",
                        "parameters": ["networkId"]
                    }
                }
            },
            "devices": {
                "switch": {
                    "ports": {
                        "method": "getDeviceSwitchPorts",
                        "description": "List the switch ports for a device",
                        "parameters": ["serial"]
                    },
                    "portSchedules": {
                        "method": "getDeviceSwitchPortSchedules",
                        "description": "List port schedules for a switch",
                        "parameters": ["serial"]
                    },
                    "routingInterfaces": {
                        "method": "getDeviceSwitchRoutingInterfaces",
                        "description": "List switch routing interfaces",
                        "parameters": ["serial"]
                    },
                    "dhcp": {
                        "method": "getDeviceSwitchWarmSpare",
                        "description": "Get switch DHCP settings",
                        "parameters": ["serial"]
                    },
                    "poe": {
                        "method": "getDeviceSwitchPortsStatuses",
                        "description": "Get PoE status for all ports",
                        "parameters": ["serial"]
                    }
                },
                "management": {
                    "interface": {
                        "method": "getDeviceManagementInterface",
                        "description": "Get device management interface settings",
                        "parameters": ["serial"]
                    }
                },
                "lldp": {
                    "cdp": {
                        "method": "getDeviceLldpCdp",
                        "description": "Get LLDP and CDP information",
                        "parameters": ["serial"]
                    }
                }
            },
            "organizations": {
                "networks": {
                    "method": "getOrganizationNetworks",
                    "description": "List the networks in an organization",
                    "parameters": ["organizationId"]
                },
                "devices": {
                    "method": "getOrganizationDevices",
                    "description": "List the devices in an organization",
                    "parameters": ["organizationId"]
                },
                "inventory": {
                    "method": "getOrganizationInventoryDevices",
                    "description": "List organization inventory devices",
                    "parameters": ["organizationId"]
                },
                "licenses": {
                    "method": "getOrganizationLicenses",
                    "description": "List organization licenses",
                    "parameters": ["organizationId"]
                }
            },
            "switch": {
                "accessPolicies": {
                    "method": "getNetworkSwitchAccessPolicies",
                    "description": "List access policies for a network",
                    "parameters": ["networkId"]
                },
                "portSchedules": {
                    "method": "getNetworkSwitchPortSchedules",
                    "description": "List network port schedules",
                    "parameters": ["networkId"]
                },
                "qosRules": {
                    "method": "getNetworkSwitchQosRules",
                    "description": "List QoS rules",
                    "parameters": ["networkId"]
                },
                "stp": {
                    "method": "getNetworkSwitchStp",
                    "description": "Get STP settings",
                    "parameters": ["networkId"]
                }
            },
            "monitoring": {
                "devices": {
                    "uplink": {
                        "method": "getOrganizationDevicesUplinksLossAndLatency",
                        "description": "Get uplink loss and latency for devices",
                        "parameters": ["organizationId", "timespan"]
                    },
                    "status": {
                        "method": "getOrganizationDevicesStatuses",
                        "description": "Get device statuses",
                        "parameters": ["organizationId"]
                    }
                },
                "alerts": {
                    "method": "getOrganizationAlertsProfiles",
                    "description": "List alert configurations",
                    "parameters": ["organizationId"]
                }
            }
        }
        
        self.setup_ui()
    
    def setup_ui(self):
        # Create main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left panel - API Browser
        api_frame = ttk.LabelFrame(main_frame, text="API Endpoints", padding="5")
        api_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # API Treeview
        self.api_tree = ttk.Treeview(api_frame)
        self.api_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Populate API tree
        self._populate_api_tree()
        
        # Right panel - Playbook Builder
        builder_frame = ttk.LabelFrame(main_frame, text="Playbook Builder", padding="5")
        builder_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Playbook metadata
        metadata_frame = ttk.LabelFrame(builder_frame, text="Playbook Metadata", padding="5")
        metadata_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Name
        ttk.Label(metadata_frame, text="Name:").grid(row=0, column=0, sticky="e", padx=5)
        self.name_var = tk.StringVar()
        ttk.Entry(metadata_frame, textvariable=self.name_var).grid(row=0, column=1, sticky="ew")
        
        # Description
        ttk.Label(metadata_frame, text="Description:").grid(row=1, column=0, sticky="e", padx=5)
        self.desc_var = tk.StringVar()
        ttk.Entry(metadata_frame, textvariable=self.desc_var).grid(row=1, column=1, sticky="ew")
        
        # Author
        ttk.Label(metadata_frame, text="Author:").grid(row=2, column=0, sticky="e", padx=5)
        self.author_var = tk.StringVar()
        ttk.Entry(metadata_frame, textvariable=self.author_var).grid(row=2, column=1, sticky="ew")
        
        # API Calls List
        calls_frame = ttk.LabelFrame(builder_frame, text="API Calls", padding="5")
        calls_frame.pack(fill=tk.BOTH, expand=True)
        
        # Calls Treeview
        columns = ("name", "endpoint", "method", "output")
        self.calls_tree = ttk.Treeview(calls_frame, columns=columns, show="headings")
        for col in columns:
            self.calls_tree.heading(col, text=col.title())
        self.calls_tree.pack(fill=tk.BOTH, expand=True)
        
        # Buttons
        button_frame = ttk.Frame(builder_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Add Call", 
                  command=self._add_api_call).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Remove Call", 
                  command=self._remove_api_call).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Save Playbook", 
                  command=self._save_playbook).pack(side=tk.RIGHT, padx=5)
    
    def _populate_api_tree(self):
        """Populate the API endpoint tree"""
        def add_node(parent, key, value):
            node = self.api_tree.insert(parent, "end", text=key)
            if isinstance(value, dict):
                if "method" in value:
                    # This is an endpoint
                    self.api_tree.item(node, tags=("endpoint",))
                else:
                    # This is a category
                    for k, v in value.items():
                        add_node(node, k, v)
        
        for key, value in self.api_endpoints.items():
            add_node("", key, value)
    
    def _add_api_call(self):
        """Add selected API endpoint to the playbook"""
        selected = self.api_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an API endpoint")
            return
        
        item = self.api_tree.item(selected[0])
        if "endpoint" not in item.get("tags", []):
            messagebox.showwarning("Warning", "Please select an endpoint (leaf node)")
            return
        
        # Get the full endpoint path and data
        path = []
        parent = selected[0]
        while parent:
            path.insert(0, self.api_tree.item(parent)["text"])
            parent = self.api_tree.parent(parent)
        
        endpoint_data = self.api_endpoints
        for part in path:
            endpoint_data = endpoint_data[part]
        
        if "method" not in endpoint_data:
            messagebox.showerror("Error", "Invalid endpoint selected")
            return
        
        endpoint = ".".join(path)
        
        # Show dialog for additional details
        dialog = tk.Toplevel(self.root)
        dialog.title("Add API Call")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Create a frame for the form with scrollbar
        canvas = tk.Canvas(dialog)
        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        form_frame = ttk.Frame(canvas, padding="10")
        
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Pack the scrollbar and canvas
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        
        # Create window in canvas
        canvas.create_window((0, 0), window=form_frame, anchor="nw")
        
        # Name
        ttk.Label(form_frame, text="Name:").pack(anchor=tk.W, pady=(0, 2))
        name_var = tk.StringVar(value=f"get_{path[-1]}")
        ttk.Entry(form_frame, textvariable=name_var).pack(fill=tk.X, pady=(0, 10))
        
        # Output Folder
        ttk.Label(form_frame, text="Output Folder:").pack(anchor=tk.W, pady=(0, 2))
        output_var = tk.StringVar(value=path[-1])
        ttk.Entry(form_frame, textvariable=output_var).pack(fill=tk.X, pady=(0, 10))
        
        # Parameters section
        ttk.Label(form_frame, text="Parameters:", font=("", 0, "bold")).pack(anchor=tk.W, pady=(10, 5))
        
        # Check if this is a device-specific endpoint
        requires_device = endpoint.startswith("devices.")
        if requires_device:
            ttk.Label(form_frame, text="⚠️ This endpoint requires device serial numbers", 
                     foreground="orange").pack(anchor=tk.W, pady=(0, 5))
        
        # Parameter configuration
        param_vars = {}
        for param in endpoint_data.get('parameters', []):
            param_frame = ttk.Frame(form_frame)
            param_frame.pack(fill=tk.X, pady=2)
            
            if param == "serial" and requires_device:
                ttk.Label(param_frame, text=f"{param}:").pack(side=tk.LEFT)
                ttk.Label(param_frame, text="(Auto-populated from device list)", 
                         foreground="gray").pack(side=tk.LEFT, padx=5)
                continue
            
            if param == "networkId":
                ttk.Label(param_frame, text=f"{param}:").pack(side=tk.LEFT)
                ttk.Label(param_frame, text="(Auto-populated from selected networks)", 
                         foreground="gray").pack(side=tk.LEFT, padx=5)
                continue
            
            ttk.Label(param_frame, text=f"{param}:").pack(side=tk.LEFT)
            param_vars[param] = tk.StringVar()
            ttk.Entry(param_frame, textvariable=param_vars[param]).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Show endpoint details
        ttk.Label(form_frame, text="Endpoint Details:", font=("", 0, "bold")).pack(anchor=tk.W, pady=(10, 2))
        details_text = f"Endpoint: {endpoint}\n"
        details_text += f"Method: {endpoint_data['method']}\n"
        details_text += f"Description: {endpoint_data['description']}"
        
        details_label = ttk.Label(form_frame, text=details_text, wraplength=450, justify=tk.LEFT)
        details_label.pack(anchor=tk.W, pady=(0, 10))
        
        def add_call():
            # Create filters dictionary for any provided parameters
            filters = {k: v.get() for k, v in param_vars.items() if v.get()}
            
            self.calls_tree.insert("", "end", values=(
                name_var.get(),
                endpoint,
                endpoint_data['method'],
                output_var.get()
            ))
            
            # Update the saved call data to include requires_device flag
            call_data = {
                "name": name_var.get(),
                "api": {
                    "endpoint": endpoint,
                    "method": endpoint_data['method'],
                    "requires_device": requires_device
                },
                "output": output_var.get()
            }
            if filters:
                call_data["api"]["filters"] = filters
            
            dialog.destroy()
        
        # Add buttons
        button_frame = ttk.Frame(form_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(button_frame, text="Cancel", 
                   command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Add", 
                   command=add_call).pack(side=tk.RIGHT, padx=5)
        
        # Update scroll region after widgets are added
        form_frame.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))
    
    def _remove_api_call(self):
        """Remove selected API call from the playbook"""
        selected = self.calls_tree.selection()
        if selected:
            self.calls_tree.delete(selected[0])
    
    def _save_playbook(self):
        """Save the playbook to a YAML file"""
        if not self.name_var.get():
            messagebox.showerror("Error", "Playbook name is required")
            return
        
        playbook = {
            "config": {
                "name": self.name_var.get(),
                "description": self.desc_var.get(),
                "version": "1.0",
                "author": self.author_var.get()
            },
            "api_calls": []
        }
        
        for item in self.calls_tree.get_children():
            values = self.calls_tree.item(item)["values"]
            playbook["api_calls"].append({
                "name": values[0],
                "api": {
                    "endpoint": values[1],
                    "method": values[2]
                },
                "output": values[3]
            })
        
        # Save to file
        dir_manager = DirectoryManager()
        file_path = dir_manager.playbooks_dir / f"{self.name_var.get().lower().replace(' ', '_')}.yaml"
        
        with open(file_path, 'w') as f:
            yaml.dump(playbook, f, sort_keys=False)
        
        messagebox.showinfo("Success", f"Playbook saved to {file_path}")

def main():
    app = PlaybookCreatorGUI()
    app.root.mainloop()

if __name__ == "__main__":
    main() 