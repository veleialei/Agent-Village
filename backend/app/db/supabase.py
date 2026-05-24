from supabase import create_client, Client
from app.config import SUPABASE_URL, SUPABASE_SERVICE_KEY

# Service client for all backend operations — bypasses RLS
# The backend is the trusted layer; it enforces trust boundaries in code, not via DB policies.
db: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
