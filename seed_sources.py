"""Seed the sources table with the 6 Tavily topic configurations.
Idempotent: uses upsert on the topic UNIQUE constraint.
Topic strings must match the keys used in newsletter.py SECTIONS exactly
(emoji-prefixed) — get_source_id() does a direct equality lookup.
"""
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv("supabase.env")
client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

# Copied verbatim from newsletter.py SECTIONS — topic label and query must stay in sync.
SOURCES = [
    {
        "topic":         "🚨 Top News",
        "tavily_query":  "biggest breaking top news today site:reuters.com OR site:apnews.com OR site:bbc.com",
        "domain_filter": ["reuters.com", "apnews.com", "bbc.com"],
    },
    {
        "topic":         "🌍 Geopolitics & World Affairs",
        "tavily_query":  "geopolitics international conflict diplomacy world news today",
        "domain_filter": None,
    },
    {
        "topic":         "💼 Business & Finance",
        "tavily_query":  "stock market economy business earnings finance news today",
        "domain_filter": None,
    },
    {
        "topic":         "🔬 Science & Technology",
        "tavily_query":  "AI artificial intelligence science technology innovation research news today",
        "domain_filter": None,
    },
    {
        "topic":         "🎾 Sports & Entertainment",
        "tavily_query":  "sports major games results entertainment celebrity news today",
        "domain_filter": None,
    },
    {
        "topic":         "🏛 Society & Culture",
        "tavily_query":  "society culture politics social trends education news today",
        "domain_filter": None,
    },
]

for src in SOURCES:
    client.table("sources").upsert(src, on_conflict="topic").execute()
    print(f"Upserted: {src['topic']}")
