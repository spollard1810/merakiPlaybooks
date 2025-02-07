#!/usr/bin/env python3
import sys
from pathlib import Path

# Add the src directory to the Python path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

from meraki_auditor.playbook_creator import main

if __name__ == "__main__":
    main() 