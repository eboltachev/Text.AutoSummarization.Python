import sys
from pathlib import Path

package_dir = Path(__file__).resolve().parent
if str(package_dir) not in sys.path:
    sys.path.append(str(package_dir))
