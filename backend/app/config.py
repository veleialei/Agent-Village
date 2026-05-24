import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
LLM_API_KEY = os.environ["LLM_API_KEY"]
PORT = int(os.getenv("PORT", "3000"))
SCHEDULER_INTERVAL = int(os.getenv("SCHEDULER_INTERVAL", "300"))
