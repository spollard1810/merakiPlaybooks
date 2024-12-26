import sys
from pathlib import Path

# Add the src directory to Python path
src_dir = Path(__file__).parent.parent
sys.path.insert(0, str(src_dir))

from meraki_auditor.gui import AuditorGUI

def main():
    app = AuditorGUI()
    app.run()

if __name__ == "__main__":
    main() 