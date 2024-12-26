from pathlib import Path
import os
import yaml
from typing import Dict, Optional
from datetime import datetime

class DirectoryManager:
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path(__file__).parent.parent.parent
        self.playbooks_dir = self.base_dir / "playbooks"
        self.reports_dir = self.base_dir / "reports"
        self.ensure_directories()
    
    def ensure_directories(self):
        """Create necessary directories if they don't exist"""
        for directory in [self.playbooks_dir, self.reports_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def get_playbooks(self) -> Dict[str, Path]:
        """Return dictionary of available playbooks"""
        playbooks = {}
        for file in self.playbooks_dir.glob("*.yaml"):
            playbooks[file.stem] = file
        return playbooks
    
    def create_report_directory(self, report_name: str) -> Path:
        """Create a new directory for a report"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_dir = self.reports_dir / f"{report_name}_{timestamp}"
        report_dir.mkdir(parents=True, exist_ok=True)
        return report_dir 