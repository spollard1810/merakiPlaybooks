from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from pathlib import Path
import yaml

@dataclass
class ApiCall:
    name: str
    endpoint: str
    method: str
    filters: Dict[str, Any]
    output: str
    requires_device: bool = False

class PlaybookConfig:
    def __init__(self, data: Dict[str, Any]):
        self.name = data.get('name', '')
        self.description = data.get('description', '')
        self.version = data.get('version', '1.0')
        self.author = data.get('author', '')

class Playbook:
    def __init__(self, path: Path):
        self.path = path
        self.config: Optional[PlaybookConfig] = None
        self.api_calls: List[ApiCall] = []
        
    def load(self):
        """Load and parse YAML configuration"""
        try:
            with open(self.path, 'r') as f:
                data = yaml.safe_load(f)
            
            self.config = PlaybookConfig(data.get('config', {}))
            
            for call in data.get('api_calls', []):
                api_data = call.get('api', {})
                self.api_calls.append(ApiCall(
                    name=call.get('name', ''),
                    endpoint=api_data.get('endpoint', ''),
                    method=api_data.get('method', ''),
                    filters=api_data.get('filters', {}),
                    output=call.get('output', ''),
                    requires_device=api_data.get('requires_device', False)
                ))
        except Exception as e:
            raise ValueError(f"Failed to load playbook: {e}")
    
    def validate(self) -> bool:
        """Validate playbook structure"""
        if not self.config or not self.api_calls:
            return False
        
        for call in self.api_calls:
            if not all([call.name, call.endpoint, call.method, call.output]):
                return False
        return True 