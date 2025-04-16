import os
import sys
from pathlib import Path

# Add the package root to the Python path
package_root = Path(__file__).parent.parent
sys.path.insert(0, str(package_root.parent))  # Add the parent directory to find the package 