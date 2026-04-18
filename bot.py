import os
import re
import json
import logging
import sqlite3
import requests
import feedparser
import yfinance as yf
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv
from google import genai
from google.genai import types

# ==========================================
# 1. SETUP & CONFIGURATION
# ==========================================
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
client = genai.Client(api_key=GEMINI_API_KEY)

# ==========================================
# 2. DATABASE & MEMORY LAYER
# ==========================================
def setup_db():
    conn = sqlite3.connect("chat_memory.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS messages 
                 (channel_id TEXT, author_id TEXT, author_name TEXT, content TEXT, timestamp TEXT)""")
    conn.commit()
    conn.close()

def save_message(channel_id, author_id, author_name, content):
    try:
        conn = sqlite3.connect("chat_memory.db")
        c = conn.cursor()
        ts = datetime.now().isoformat()
        c.execute("INSERT INTO messages VALUES (?, ?, ?, ?, ?)", 
                  (str(channel_id), str(author_id), author_name, content, ts))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"DB Write Error: {e}")

def get_chat_history(channel_id, target_user=None, limit=10):
    """Retrieves past messages to provide context for summaries."""
    try:
        conn = sqlite3.connect("chat_memory.db")
        c = conn.cursor()
        if target_user:
            # Clean mention ID if needed
            clean_id = re.sub(r'\D', '', target_user)
            c.execute("SELECT author_name, content FROM messages WHERE channel_id=? AND author_id=? ORDER BY timestamp DESC LIMIT ?", 
                      (str(channel_id), clean_id, limit))
        else:
            c.execute("SELECT author_name, content FROM messages WHERE channel_id=? ORDER BY timestamp DESC LIMIT ?", 
                      (str(channel_id), limit))
        rows = c.fetchall()
        conn.close()
        rows.reverse()
        return "\n".join([f"{name}: {msg}" for name, msg in rows])
    except: return ""

# ==========================================
# 3. REGIONAL NEWS SENTRY
# ==========================================
REGIONAL_FEEDS = {
    "UAE": ["https://www.thenationalnews.com/arc/outboundfeeds/rss/", "https://gulfnews.com/rss/news"],
    "NZ": ["https://www.rnz.co.nz/rss/news.xml", "https://www.nzherald.co.nz/arc/outboundfeeds/rss/section/nz/?outputType=xml"],
    "AUS": ["https://www.abc.net.au/news/feed/51120/rss.xml", "https://www.sbs.com.au/news/feed"],
    "Nepal": ["https://kathmandupost.com/rss", "https://english.onlinekhabar.com/feed"],
    "SEA": ["https://www.channelnewsasia.com/rss/cna-asia", "https://www.bangkokpost.com/rss/data/topstories.xml"],
    "Global": ["http://feeds.bbci.co.uk/news/rss.xml", "https://www.reutersagency.com/feed/"]
}

SENTRY_MAP = {
    "UAE": ["uae", "dubai", "emirates", "gulf"],
    "NZ": ["nz", "new zealand", "auckland", "wellington"],
    "AUS": ["aus", "australia", "sydney", "melbourne"],
    "Nepal": ["nepal", "kathmandu", "pokhara"],
    "SEA": ["sea", "singapore", "bangkok", "asia"]
}

def fetch_rss_news(region="Global", topic=None):
    urls = REGIONAL_FEEDS.get(region, REGIONAL_FEEDS["Global"])
    articles = []
    is_generic = not topic or any(x in topic.lower() for x in ["news", "latest", "update"])

    for url in urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                if is_generic or (topic.lower() in entry.title.lower()):
                    articles.append({"title": entry.title, "link": entry.link})
        except: continue
    return articles[:5]

# ==========================================
# 4. HYBRID AI & UTILITIES
# ==========================================
async def generate_hybrid_text(prompt):
    try:
        res = await client.aio.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return res.text.strip()
    except:
        try:
            res = requests.post("http://localhost:11434/api/generate", 
                                json={"model": "llama3", "prompt": prompt, "stream": False}, timeout=15)
            return res.json().get("response", "").strip()
        except: return "⚠️ AI system fallback failed."

async def analyze_intent(user_input):
    prompt = f"Analyze: '{user_input}'. Output ONLY JSON: {{\"intent\": \"news/market/distance/chat\", \"topic\": \"str\", \"ticker\": \"str\"}}"
    try:
        res = await client.aio.models.generate_content(model='gemini-2.5-flash', contents=prompt, 
                                                       config=types.GenerateContentConfig(response_mime_type="application/json"))
        return json.loads(res.text)
    except: return {"intent": "chat"}

def get_coords(place):
    url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": "BideshiNepaliBot/3.0"}
    try:
        res = requests.get(url, params={"q": place, "format": "json", "limit": 1}, headers=headers).json()
        if res: return float(res[0]["lat"]), float(res[0]["lon"]), res[0]["display_name"]
    except: return None

def calculate_distance(c1, c2):
    R = 6371
    lat1, lon1, lat2, lon2 = radians(c1[0]), radians(c1[1]), radians(c2[0]), radians(c2[1])
    # Haversine formula
    a = sin((lat2-lat1)/2)**2 + cos(lat1)*cos(lat2)*sin((lon2-lon1)/2)**2
    return R * (2 * atan2(sqrt(a), sqrt(1-a)))

# ==========================================
# 5. DISCORD BOT HANDLER
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    setup_db()
    logger.info(f"✅ Bot Online: {bot.user}")

@bot.event
async def on_message(message):
    if message.author == bot.user: return
    
    # LOG EVERY MESSAGE TO MEMORY
    save_message(message.channel.id, message.author.id, message.author.name, message.content)

    if bot.user in message.mentions:
        user_prompt = re.sub(r'<@!?\d+>', '', message.content).strip()
        
        async with message.channel.typing():
            # 1. REGIONAL SENTRY (Hard Override)
            target_region = "Global"
            found_region = False
            for reg, keywords in SENTRY_MAP.items():
                if any(k in user_prompt.lower() for k in keywords):
                    target_region, found_region = reg, True
                    break

            # 2. INTENT ANALYSIS
            analysis = await analyze_intent(user_prompt)
            intent = "news" if found_region else analysis.get("intent")
            
            # 3. MEMORY CHECK
            is_mem = any(x in user_prompt.lower() for x in ["saying", "said", "summarize", "history"])

            if is_mem:
                target_user = re.search(r'<@!?(\d+)>', user_prompt).group(0) if "<@" in user_prompt else None
                history = get_chat_history(message.channel.id, target_user)
                reply = await generate_hybrid_text(f"Context:\n{history}\n\nQuery: {user_prompt}")
                await message.channel.send(reply)

            elif intent == "news":
                news = fetch_rss_news(target_region, analysis.get("topic"))
                if news:
                    bullets = [f"{i}. **{a['title']}**\n   🔗 [Read Story]({a['link']})" for i, a in enumerate(news, 1)]
                    vibe = await generate_hybrid_text(f"Summarize these {target_region} headlines: " + " | ".join([n['title'] for n in news]))
                    await message.channel.send(f"📰 **Top {target_region} Headlines**\n*{vibe}*\n\n" + "\n\n".join(bullets))
                else:
                    await message.channel.send(f"No {target_region} matches found.")

            elif intent == "distance":
                try:
                    parts = re.split(r' to | and | between ', user_prompt.lower())
                    c1, c2 = get_coords(parts[-2].strip()), get_coords(parts[-1].strip())
                    dist = round(calculate_distance(c1, c2), 2)
                    map_url = f"https://www.openstreetmap.org/directions?route={c1[0]},{c1[1]};{c2[0]},{c2[1]}"
                    await message.channel.send(f"📏 Distance: {dist}km\n🗺️ **Route:** {map_url}")
                except: await message.channel.send("Coordinate resolution failed.")

            else:
                reply = await generate_hybrid_text(user_prompt)
                await message.channel.send(reply)

bot.run(DISCORD_TOKEN)
