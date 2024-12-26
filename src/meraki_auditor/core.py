from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional
import yaml
from pathlib import Path
import meraki
from .playbook import Playbook, ApiCall, PlaybookConfig
import json
from .utils import DirectoryManager

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
    
    def authenticate(self) -> bool:
        try:
            # Test authentication by getting organizations
            self.dashboard.organizations.getOrganizations()
            return True
        except meraki.APIError:
            return False
    
    def load_networks(self) -> List[Dict]:
        try:
            orgs = self.dashboard.organizations.getOrganizations()
            networks = []
            for org in orgs:
                org_networks = self.dashboard.organizations.getOrganizationNetworks(org['id'])
                networks.extend(org_networks)
            self.networks = networks
            return networks
        except meraki.APIError as e:
            raise ConnectionError(f"Failed to load networks: {e}")
    
    def select_networks(self, network_ids: List[str]):
        self.selected_networks = network_ids

class PlaybookExecutor:
    def __init__(self, connection: MerakiConnection):
        self.connection = connection
        self.current_playbook: Optional[Playbook] = None
        self.results: Dict[str, Any] = {}
        self.devices: Dict[str, List[Dict]] = {}  # Cache for devices by network
    
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
        
        for step in self.current_playbook.steps:
            step_results = []
            
            # Handle network-level API calls
            if step.endpoint.startswith('networks.'):
                step_results.extend(self._execute_network_call(step))
            
            # Handle device-level API calls
            elif step.endpoint.startswith('devices.'):
                step_results.extend(self._execute_device_call(step))
            
            results[step.output_folder] = step_results
        
        self.results = {
            'metadata': {
                'playbook_name': self.current_playbook.name,
                'start_time': start_time.isoformat(),
                'end_time': datetime.now().isoformat(),
                'networks': [n['name'] for n in self.connection.selected_networks]
            },
            'results': results
        }
        
        return self.results
    
    def _execute_network_call(self, step: ApiCall) -> List[Dict]:
        results = []
        for network in self.connection.selected_networks:
            try:
                # Get the appropriate API endpoint
                api_parts = step.endpoint.split('.')
                api_endpoint = self.connection.dashboard
                for part in api_parts:
                    api_endpoint = getattr(api_endpoint, part)
                
                # Execute the API call
                params = {**step.parameters, 'networkId': network['networkId']}
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
                results.append({
                    'network': network['name'],
                    'networkId': network['networkId'],
                    'error': str(e)
                })
        return results
    
    def _execute_device_call(self, step: ApiCall) -> List[Dict]:
        results = []
        
        # Iterate through networks and their devices
        for network in self.connection.selected_networks:
            network_devices = self.devices.get(network['networkId'], [])
            
            for device in network_devices:
                try:
                    # Get the appropriate API endpoint
                    api_parts = step.endpoint.split('.')
                    api_endpoint = self.connection.dashboard
                    for part in api_parts:
                        api_endpoint = getattr(api_endpoint, part)
                    
                    # Execute the API call for each device
                    params = {**step.parameters, 'serial': device['serial']}
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
                    results.append({
                        'network': network['name'],
                        'networkId': network['networkId'],
                        'device': device['name'] if 'name' in device else device['serial'],
                        'error': str(e)
                    })
        
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