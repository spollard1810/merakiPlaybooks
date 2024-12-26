#!/usr/bin/env python3
import sys
from pathlib import Path

def run_creator():
    try:
        # Try relative import first
        from .playbook_creator import main
    except ImportError:
        # If that fails, try adding the src directory to path
        src_dir = Path(__file__).parent.parent
        sys.path.insert(0, str(src_dir))
        from meraki_auditor.playbook_creator import main
    
    main()

if __name__ == "__main__":
    # If running this file directly, we need to use the absolute import
    src_dir = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(src_dir))
    from meraki_auditor.playbook_creator import main
    main() 