import sys
from pathlib import Path
import os

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
from dotenv import load_dotenv

load_dotenv()

authorization = "Authorization" if not os.environ.get("DEBUG") else "user_id"
