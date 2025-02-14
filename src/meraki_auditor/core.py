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
        self.devices = {}
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
        
        # First, ensure we have devices cached if we need them
        if any(step.requires_device for step in self.current_playbook.api_calls):
            self.update_status("Caching devices from networks...")
            for network in self.connection.selected_networks:
                if network['id'] not in self.connection.devices:
                    try:
                        devices = self.connection.dashboard.networks.getNetworkDevices(networkId=network['id'])
                        self.connection.devices[network['id']] = [d for d in devices if 'serial' in d]
                        logger.info(f"Cached {len(devices)} devices from network {network['name']}")
                    except Exception as e:
                        logger.error(f"Failed to cache devices for network {network['name']}: {e}")
        
        for idx, step in enumerate(self.current_playbook.api_calls, 1):
            step_progress_base = (idx - 1) / total_steps * 100
            step_results = []
            
            self.update_status(f"Executing step {idx}/{total_steps}: {step.name}")
            
            try:
                if step.requires_device:
                    # Device-level API call - iterate through cached devices
                    step_results.extend(self._execute_device_call(step, step_progress_base))
                else:
                    # Network-level API call
                    step_results.extend(self._execute_network_call(step, step_progress_base))
                
                results[step.output_folder] = step_results
                
            except Exception as e:
                error_msg = f"Failed to execute step {step.name}: {str(e)}"
                logger.error(error_msg)
                results[step.output_folder] = [{'error': error_msg}]
            
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
                if api_parts[0] == 'networks':
                    if len(api_parts) == 2 and api_parts[1] == 'devices':
                        # Direct network endpoint for devices
                        api_endpoint = getattr(self.connection.dashboard.networks, step.method)
                    else:
                        # Network settings endpoints (like getNetworkSwitchSettings)
                        api_endpoint = getattr(self.connection.dashboard.networks, step.method)
                else:
                    raise ValueError(f"Unsupported network endpoint: {step.endpoint}")
                
                # Execute the API call
                params = {**step.parameters, 'networkId': network['id']}
                logger.info(f"API Call: {step.method} for network {network['name']}")
                result = api_endpoint(**params)
                
                # Cache devices if this is a device list call
                if step.endpoint == 'networks.devices':
                    self.devices[network['id']] = [d for d in result if 'serial' in d]
                
                results.append({
                    'network': network['name'],
                    'networkId': network['id'],
                    'data': result
                })
                
            except Exception as e:
                error_msg = f"Error in network {network['name']}: {str(e)}"
                logger.error(error_msg)
                results.append({
                    'network': network['name'],
                    'networkId': network['id'],
                    'error': str(e)
                })
            
            # Update progress within this step
            step_progress = base_progress + (idx / total_networks * (100 / len(self.current_playbook.api_calls)))
            self.update_progress(step_progress)
        
        return results
    
    def _execute_device_call(self, step: ApiCall, base_progress: float) -> List[Dict]:
        results = []
        devices_processed = 0
        
        # Get all devices from cache
        all_devices = []
        for network in self.connection.selected_networks:
            network_devices = self.connection.devices.get(network['id'], [])
            all_devices.extend((network, device) for device in network_devices)
        
        total_devices = len(all_devices)
        if total_devices == 0:
            logger.warning("No devices found for API calls")
            return results
        
        for network, device in all_devices:
            try:
                self.update_status(
                    f"Processing device {devices_processed + 1}/{total_devices}: "
                    f"{device.get('name', device['serial'])} in network {network['name']}"
                )
                
                # Get the appropriate API endpoint and method
                api_endpoint = self.connection.dashboard.devices
                method = getattr(api_endpoint, step.method)
                
                # Execute the API call for each device
                params = {**step.parameters, 'serial': device['serial']}
                logger.info(f"API Call: {step.method} for device {device.get('name', device['serial'])}")
                result = method(**params)
                
                # Apply output filter if specified
                filtered_result = step.filter_response(result)
                
                # Add device and network context to the results
                result_data = {
                    'network': network['name'],
                    'networkId': network['id'],
                    'deviceName': device.get('name', device['serial']),
                    'deviceSerial': device['serial'],
                    'deviceModel': device.get('model', ''),
                    'deviceType': device.get('productType', ''),
                    'data': filtered_result
                }
                
                results.append(result_data)
                logger.info(f"Successfully got data for device {device.get('name', device['serial'])}")
                
            except Exception as e:
                # Just log the error and continue
                error_msg = (f"Skipping device {device.get('name', device['serial'])} "
                           f"in network {network['name']}: {str(e)}")
                logger.info(error_msg)  # Changed to info since we expect some devices to fail
            
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
        
        # Create a log file for the execution
        log_file_path = report_dir / f'execution_log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
        with open(log_file_path, 'w') as log_file:
            # Write metadata
            log_file.write("=== Execution Metadata ===\n")
            for key, value in self.executor.results['metadata'].items():
                log_file.write(f"{key}: {value}\n")
                print(f"{key}: {value}")
            log_file.write("\n")
            print()
            
            # Process each result type
            for folder, data in self.executor.results['results'].items():
                folder_path = report_dir / folder
                folder_path.mkdir(exist_ok=True)
                
                log_file.write(f"\n=== {folder} Results ===\n")
                print(f"\n=== {folder} Results ===")
                
                flattened_data = []
                for result in data:
                    if 'error' in result:
                        error_msg = f"Error in network {result['network']}: {result['error']}"
                        log_file.write(f"{error_msg}\n")
                        print(error_msg)
                        continue
                    
                    # Start with the common device info
                    flat_result = {
                        'network': result['network'],
                        'deviceName': result.get('deviceName', ''),
                        'deviceSerial': result.get('deviceSerial', ''),
                        'deviceModel': result.get('deviceModel', ''),
                        'deviceType': result.get('deviceType', '')
                    }
                    
                    # Log device info
                    device_info = f"\nDevice: {flat_result['deviceName']} ({flat_result['deviceSerial']})"
                    device_info += f"\nNetwork: {flat_result['network']}"
                    device_info += f"\nModel: {flat_result['deviceModel']}"
                    device_info += f"\nType: {flat_result['deviceType']}"
                    log_file.write(f"{device_info}\n")
                    print(device_info)
                    
                    # Flatten and log the API response data
                    if isinstance(result['data'], dict):
                        log_file.write("Settings:\n")
                        print("Settings:")
                        for key, value in result['data'].items():
                            flat_result[key] = value
                            log_file.write(f"  {key}: {value}\n")
                            print(f"  {key}: {value}")
                    elif isinstance(result['data'], list):
                        if result['data'] and isinstance(result['data'][0], dict):
                            log_file.write("Settings:\n")
                            print("Settings:")
                            for key, value in result['data'][0].items():
                                flat_result[key] = value
                                log_file.write(f"  {key}: {value}\n")
                                print(f"  {key}: {value}")
                    
                    log_file.write("-" * 50 + "\n")
                    print("-" * 50)
                    flattened_data.append(flat_result)
                
                if flattened_data:
                    # Convert to DataFrame - this will automatically align all columns
                    df = pd.DataFrame(flattened_data)
                    
                    # Add timestamp
                    df['timestamp'] = datetime.now().isoformat()
                    
                    # Save to CSV
                    csv_path = folder_path / f'{folder}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
                    df.to_csv(csv_path, index=False)
                    
                    # Generate a schema file to document the columns
                    schema = {col: str(df[col].dtype) for col in df.columns}
                    with open(folder_path / 'schema.json', 'w') as f:
                        json.dump(schema, f, indent=2)
                    
                    log_file.write(f"\nGenerated CSV with columns: {list(df.columns)}\n")
                    print(f"\nGenerated CSV with columns: {list(df.columns)}")
        
        return report_dir 

class PlaybookConfig:
    def __init__(self, name: str, description: str, version: str, author: str):
        self.name = name
        self.description = description
        self.version = version
        self.author = author

    @classmethod
    def from_dict(cls, data: Dict) -> 'PlaybookConfig':
        return cls(
            name=data.get('name', ''),
            description=data.get('description', ''),
            version=data.get('version', ''),
            author=data.get('author', '')
        )

class ApiCall:
    def __init__(self, name: str, endpoint: str, method: str, output_folder: str, 
                 parameters: Dict = None, filters: Dict = None, output_filter: List[str] = None,
                 requires_device: bool = False):
        self.name = name
        self.endpoint = endpoint
        self.method = method
        self.output_folder = output_folder
        self.parameters = parameters or {}
        self.filters = filters or {}
        self.output_filter = output_filter or []
        self.requires_device = requires_device or endpoint.startswith('devices.')

    def filter_response(self, response: Any) -> Dict:
        """Filter the API response based on output_filter if specified."""
        if not self.output_filter or not isinstance(response, dict):
            return response
            
        filtered_data = {}
        for field in self.output_filter:
            # Handle nested fields with dot notation (e.g., 'staticDns.ip')
            parts = field.split('.')
            value = response
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    value = None
                    break
            filtered_data[field] = value
        return filtered_data

    @classmethod
    def from_dict(cls, data: Dict) -> 'ApiCall':
        api_data = data.get('api', {})
        return cls(
            name=data.get('name', ''),
            endpoint=api_data.get('endpoint', ''),
            method=api_data.get('method', ''),
            output_folder=data.get('output', ''),
            parameters=api_data.get('parameters', {}),
            filters=api_data.get('filters', {}),
            output_filter=api_data.get('output_filter', []),
            requires_device=api_data.get('requires_device', False)
        ) 

class Playbook:
    def __init__(self, config: PlaybookConfig, api_calls: List[ApiCall]):
        self.config = config
        self.api_calls = api_calls

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> 'Playbook':
        """Load a playbook from a YAML file."""
        try:
            with open(yaml_path, 'r') as f:
                data = yaml.safe_load(f)
            
            config = PlaybookConfig.from_dict(data.get('config', {}))
            api_calls = [ApiCall.from_dict(call) for call in data.get('api_calls', [])]
            
            return cls(config=config, api_calls=api_calls)
            
        except Exception as e:
            logger.error(f"Failed to load playbook {yaml_path}: {e}")
            raise ValueError(f"Invalid playbook format: {e}") 