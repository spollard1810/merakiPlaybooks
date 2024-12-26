from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional
import yaml
from pathlib import Path
import meraki
import json
import logging
from .playbook import Playbook, ApiCall, PlaybookConfig
from .utils import DirectoryManager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ReportMetadata:
    name: str
    type: str
    version: str
    description: str
    author: str
    date: datetime
    duration: float
    playbook_name: str

class MerakiConnection:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.networks = []
        self.selected_networks = []
        self.dashboard = meraki.DashboardAPI(api_key, output_log=False, print_console=False)
        self.progress_callback = None
        self.status_callback = None
    
    def set_callbacks(self, progress_callback=None, status_callback=None):
        """Set callbacks for progress and status updates"""
        self.progress_callback = progress_callback
        self.status_callback = status_callback
    
    def update_progress(self, progress: float):
        """Update progress bar"""
        if self.progress_callback:
            self.progress_callback(progress)
    
    def update_status(self, status: str):
        """Update status message"""
        if self.status_callback:
            self.status_callback(status)
        logger.info(status)
    
    def authenticate(self) -> bool:
        try:
            self.update_status("Authenticating with Meraki Dashboard...")
            self.update_progress(0)
            
            # Test authentication by getting organizations
            logger.info("API Call: getOrganizations")
            self.dashboard.organizations.getOrganizations()
            
            self.update_status("Authentication successful")
            self.update_progress(100)
            return True
            
        except meraki.APIError as e:
            error_msg = f"Authentication failed: {str(e)}"
            logger.error(error_msg)
            self.update_status(error_msg)
            return False
    
    def load_networks(self) -> List[Dict]:
        try:
            self.update_status("Loading organizations...")
            self.update_progress(0)
            
            logger.info("API Call: getOrganizations")
            orgs = self.dashboard.organizations.getOrganizations()
            
            self.update_status(f"Found {len(orgs)} organizations")
            self.update_progress(20)
            
            networks = []
            for idx, org in enumerate(orgs, 1):
                self.update_status(f"Loading networks for organization {idx}/{len(orgs)}: {org['name']}")
                
                logger.info(f"API Call: getOrganizationNetworks for org {org['name']}")
                org_networks = self.dashboard.organizations.getOrganizationNetworks(org['id'])
                networks.extend(org_networks)
                
                # Update progress (20-90% range for loading networks)
                progress = 20 + (idx / len(orgs) * 70)
                self.update_progress(progress)
            
            self.networks = networks
            
            self.update_status(f"Loaded {len(networks)} networks from {len(orgs)} organizations")
            self.update_progress(100)
            
            return networks
            
        except meraki.APIError as e:
            error_msg = f"Failed to load networks: {str(e)}"
            logger.error(error_msg)
            self.update_status(error_msg)
            raise ConnectionError(error_msg)
    
    def select_networks(self, network_ids: List[str]):
        """Select networks and cache their devices"""
        self.selected_networks = [n for n in self.networks if n['id'] in network_ids]
        self.update_status(f"Selected {len(self.selected_networks)} networks")
        
        # Pre-cache devices for selected networks
        for network in self.selected_networks:
            try:
                devices = self.dashboard.networks.getNetworkDevices(networkId=network['id'])
                self.devices[network['id']] = devices
                self.update_status(f"Loaded {len(devices)} devices from {network['name']}")
            except Exception as e:
                logger.error(f"Failed to load devices for network {network['name']}: {e}")

class PlaybookExecutor:
    def __init__(self, connection: MerakiConnection):
        self.connection = connection
        self.current_playbook: Optional[Playbook] = None
        self.results: Dict[str, Any] = {}
        self.devices: Dict[str, List[Dict]] = {}
        self.progress_callback = None
        self.status_callback = None
    
    def set_callbacks(self, progress_callback=None, status_callback=None):
        """Set callbacks for progress and status updates"""
        self.progress_callback = progress_callback
        self.status_callback = status_callback
    
    def update_progress(self, progress: float):
        """Update progress bar"""
        if self.progress_callback:
            self.progress_callback(progress)
    
    def update_status(self, status: str):
        """Update status message"""
        if self.status_callback:
            self.status_callback(status)
        logger.info(status)
    
    def load_playbook(self, playbook_path: Path) -> Playbook:
        playbook = Playbook(playbook_path)
        playbook.load()
        if not playbook.validate():
            raise ValueError("Invalid playbook structure")
        self.current_playbook = playbook
        return playbook
    
    def execute(self) -> Dict[str, Any]:
        if not self.current_playbook:
            raise ValueError("No playbook loaded")
        
        start_time = datetime.now()
        results = {}
        total_steps = len(self.current_playbook.api_calls)
        
        self.update_status(f"Starting execution of playbook: {self.current_playbook.config.name}")
        self.update_progress(0)
        
        for idx, step in enumerate(self.current_playbook.api_calls, 1):
            step_progress_base = (idx - 1) / total_steps * 100
            step_results = []
            
            self.update_status(f"Executing step {idx}/{total_steps}: {step.name}")
            
            # Handle network-level API calls
            if step.endpoint.startswith('networks.'):
                step_results.extend(self._execute_network_call(step, step_progress_base))
            
            # Handle device-level API calls
            elif step.endpoint.startswith('devices.'):
                step_results.extend(self._execute_device_call(step, step_progress_base))
            
            results[step.output_folder] = step_results
            self.update_progress(idx / total_steps * 100)
        
        execution_time = (datetime.now() - start_time).total_seconds()
        self.update_status(f"Playbook execution completed in {execution_time:.2f} seconds")
        
        self.results = {
            'metadata': {
                'playbook_name': self.current_playbook.config.name,
                'start_time': start_time.isoformat(),
                'end_time': datetime.now().isoformat(),
                'execution_time_seconds': execution_time,
                'networks': [n['name'] for n in self.connection.selected_networks]
            },
            'results': results
        }
        
        return self.results
    
    def _execute_network_call(self, step: ApiCall, base_progress: float) -> List[Dict]:
        results = []
        total_networks = len(self.connection.selected_networks)
        
        for idx, network in enumerate(self.connection.selected_networks, 1):
            try:
                self.update_status(f"Processing network {idx}/{total_networks}: {network['name']}")
                
                # Get the appropriate API endpoint
                api_parts = step.endpoint.split('.')
                api_endpoint = self.connection.dashboard
                for part in api_parts:
                    api_endpoint = getattr(api_endpoint, part)
                
                # Execute the API call
                params = {**step.parameters, 'networkId': network['networkId']}
                logger.info(f"API Call: {step.method} for network {network['name']}")
                result = getattr(api_endpoint, step.method)(**params)
                
                # Cache devices if this is a device list call
                if step.endpoint == 'networks.devices':
                    self.devices[network['networkId']] = result
                
                results.append({
                    'network': network['name'],
                    'networkId': network['networkId'],
                    'data': result
                })
                
            except Exception as e:
                error_msg = f"Error in network {network['name']}: {str(e)}"
                logger.error(error_msg)
                results.append({
                    'network': network['name'],
                    'networkId': network['networkId'],
                    'error': str(e)
                })
            
            # Update progress within this step
            step_progress = base_progress + (idx / total_networks * (100 / len(self.current_playbook.api_calls)))
            self.update_progress(step_progress)
        
        return results
    
    def _execute_device_call(self, step: ApiCall, base_progress: float) -> List[Dict]:
        results = []
        total_networks = len(self.connection.selected_networks)
        devices_processed = 0
        total_devices = sum(len(self.devices.get(n['networkId'], [])) 
                          for n in self.connection.selected_networks)
        
        for network_idx, network in enumerate(self.connection.selected_networks, 1):
            network_devices = self.devices.get(network['networkId'], [])
            
            for device_idx, device in enumerate(network_devices, 1):
                try:
                    self.update_status(
                        f"Processing device {devices_processed + 1}/{total_devices}: "
                        f"{device.get('name', device['serial'])} in network {network['name']}"
                    )
                    
                    # Get the appropriate API endpoint
                    api_parts = step.endpoint.split('.')
                    api_endpoint = self.connection.dashboard
                    for part in api_parts:
                        api_endpoint = getattr(api_endpoint, part)
                    
                    # Execute the API call for each device
                    params = {**step.parameters, 'serial': device['serial']}
                    logger.info(f"API Call: {step.method} for device {device.get('name', device['serial'])}")
                    result = getattr(api_endpoint, step.method)(**params)
                    
                    # Add device and network context to the results
                    if isinstance(result, list):
                        for item in result:
                            item.update({
                                'deviceName': device.get('name', device['serial']),
                                'deviceSerial': device['serial'],
                                'deviceModel': device.get('model', ''),
                                'network': network['name'],
                                'networkId': network['networkId']
                            })
                    
                    results.append({
                        'network': network['name'],
                        'networkId': network['networkId'],
                        'device': device['name'] if 'name' in device else device['serial'],
                        'data': result
                    })
                    
                except Exception as e:
                    error_msg = (f"Error processing device {device.get('name', device['serial'])} "
                               f"in network {network['name']}: {str(e)}")
                    logger.error(error_msg)
                    results.append({
                        'network': network['name'],
                        'networkId': network['networkId'],
                        'device': device['name'] if 'name' in device else device['serial'],
                        'error': str(e)
                    })
                
                devices_processed += 1
                # Update progress within this step
                step_progress = base_progress + (devices_processed / total_devices * 
                                               (100 / len(self.current_playbook.api_calls)))
                self.update_progress(step_progress)
        
        return results

class ReportGenerator:
    def __init__(self, executor: PlaybookExecutor):
        self.executor = executor
        self.metadata = None
    
    def generate_report(self, report_type: str, report_name: str) -> Path:
        if not self.executor.results:
            raise ValueError("No results to generate report from")
        
        if report_type == 'csv':
            return self._generate_csv_report(report_name)
        else:
            raise ValueError(f"Unsupported report type: {report_type}")
    
    def _generate_csv_report(self, report_name: str) -> Path:
        import pandas as pd
        from itertools import chain
        
        # Create report directory
        report_dir = DirectoryManager().create_report_directory(report_name)
        
        # Save metadata
        with open(report_dir / 'metadata.json', 'w') as f:
            json.dump(self.executor.results['metadata'], f, indent=2)
        
        # Process each result type
        for folder, data in self.executor.results['results'].items():
            folder_path = report_dir / folder
            folder_path.mkdir(exist_ok=True)
            
            # Extract all data points to determine all possible columns
            all_data = []
            for result in data:
                if isinstance(result.get('data'), list):
                    # If the data is a list, extend it
                    all_data.extend(result['data'])
                elif isinstance(result.get('data'), dict):
                    # If it's a single dict, append it
                    all_data.append(result['data'])
                
                # Handle errors if any
                if 'error' in result:
                    all_data.append({'error': result['error'], 'network': result['network']})
            
            if all_data:
                # Convert to DataFrame with dynamic columns
                df = pd.json_normalize(all_data)
                
                # Add timestamp column
                df['timestamp'] = datetime.now().isoformat()
                
                # Save to CSV with all headers
                csv_path = folder_path / f'{folder}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
                df.to_csv(csv_path, index=False)
                
                # Generate a schema file to document the columns
                schema = {col: str(df[col].dtype) for col in df.columns}
                with open(folder_path / 'schema.json', 'w') as f:
                    json.dump(schema, f, indent=2)
        
        return report_dir 