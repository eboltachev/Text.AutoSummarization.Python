import os

from dotenv import load_dotenv

load_dotenv()

authorization = "Authorization" if not os.environ.get("DEBUG") else "user_id"

