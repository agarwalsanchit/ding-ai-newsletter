"""Smoke test: insert one source, read it back, delete it."""
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv("supabase.env")

client = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_ROLE_KEY"],  # service role for writes
)

# Insert
inserted = client.table("sources").insert({
    "topic": "Test Topic",
    "tavily_query": "test query",
    "domain_filter": ["example.com"],
    "active": False,
}).execute()
print("Inserted:", inserted.data)
source_id = inserted.data[0]["id"]

# Read back
fetched = client.table("sources").select("*").eq("id", source_id).execute()
print("Fetched:", fetched.data)

# Clean up
client.table("sources").delete().eq("id", source_id).execute()
print("Cleaned up.")