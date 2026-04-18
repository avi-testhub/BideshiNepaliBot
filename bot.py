import os
import re
import json
import logging
import sqlite3
import requests
import feedparser
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
# Explicitly find the .env file in the same folder as this script
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not DISCORD_TOKEN or not GEMINI_API_KEY:
    raise ValueError(f"Missing API Keys! Looked for .env at: {env_path}")

# Logging Setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize the Google GenAI Client
client = genai.Client(api_key=GEMINI_API_KEY)

# ==========================================
# 2. DATABASE LAYER (SQLite Memory)
# ==========================================
def setup_db():
    conn = sqlite3.connect("chat_memory.db")
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        channel_id TEXT,
        author TEXT,
        content TEXT,
        timestamp TEXT
    )
    """)
    conn.commit()
    conn.close()

def save_message(cid, author, content, ts):
    try:
        conn = sqlite3.connect("chat_memory.db")
        c = conn.cursor()
        c.execute("INSERT INTO messages VALUES (?, ?, ?, ?)", (cid, author, content, ts))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Database write error: {e}")

def get_recent_history(channel_id, limit=6):
    try:
        conn = sqlite3.connect("chat_memory.db")
        c = conn.cursor()
        c.execute("SELECT author, content FROM messages WHERE channel_id=? ORDER BY timestamp DESC LIMIT ?", (str(channel_id), limit))
        rows = c.fetchall()
        conn.close()
        
        rows.reverse()
        history = ""
        for author, content in rows:
            history += f"{author}: {content}\n"
        return history
    except Exception as e:
        logger.error(f"Database read error: {e}")
        return ""

# ==========================================
# 3. AI AGENT LAYER (Text & Intent)
# ==========================================
async def generate_with_gemini(prompt, mode="chat"):
    """Generates text using the google-genai SDK."""
    try:
        if mode == "chat":
            model_name = "gemini-2.5-flash"
            sys_instruct = "You are a friendly AI assistant with a slight Nepali-English tone. Keep responses short (1-2 sentences) and helpful."
            config = types.GenerateContentConfig(system_instruction=sys_instruct)
            
        elif mode == "factual":
            model_name = "gemini-2.5-pro"
            sys_instruct = "You are a factual assistant. Provide highly accurate answers, ending with a short, friendly Nepali remark."
            config = types.GenerateContentConfig(system_instruction=sys_instruct)
            
        elif mode == "professional":
            model_name = "gemini-2.5-pro"
            sys_instruct = "You are a strict, professional AI. No jokes, no slang. Focus strictly on facts and objective summaries."
            config = types.GenerateContentConfig(system_instruction=sys_instruct)
            
        else:
            model_name = "gemini-2.5-flash"
            config = types.GenerateContentConfig()

        response = await client.aio.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini API Error: {e}")
        return "⚠️ I'm having trouble connecting to my neural network right now. Please try again later."

async def detect_intent_llm(user_input):
    """Uses Gemini Flash to quickly classify user intent without regex keywords."""
    prompt = f"""
    Analyze the following user input and determine the primary intent. 
    Output ONLY a raw JSON object with no markdown formatting.
    Valid intents: 'news', 'distance', 'where', 'chat'.
    
    If they ask for locations, it is 'where'.
    If they ask for distance/how far, it is 'distance'.
    If they ask for updates, news, or current events, it is 'news'.
    Otherwise, default to 'chat'.
    
    Input: "{user_input}"
    Output Format: {{"intent": "detected_intent"}}
    """
    try:
        config = types.GenerateContentConfig(response_mime_type="application/json")
        response = await client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=config
        )
        result = json.loads(response.text)
        return result.get("intent", "chat")
    except Exception as e:
        logger.error(f"Intent parsing error: {e}")
        return "chat"

# ==========================================
# 4. SCRAPING & GEO LAYER
# ==========================================
def fetch_rss_news(query=None):
    feeds = ["http://feeds.bbci.co.uk/news/rss.xml", "http://rss.cnn.com/rss/edition.rss", "https://www.reutersagency.com/feed/"]
    articles = []
    for f in feeds:
        feed = feedparser.parse(f)
        for entry in feed.entries[:5]:
            title = entry.title
            link = entry.link
            if query:
                if any(word in title.lower() for word in query.lower().split()):
                    articles.append(f"{title} - {link}")
            else:
                articles.append(f"{title} - {link}")
    return articles[:5]

def get_coords(place):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": place, "format": "json", "limit": 1}
    headers = {"User-Agent": "BideshiNepaliBot/2.0"}
    try:
        res = requests.get(url, params=params, headers=headers).json()
        if res:
            return float(res[0]["lat"]), float(res[0]["lon"]), res[0]["display_name"]
    except Exception as e:
        logger.error(f"Geo API Error: {e}")
    return None

def calculate_distance(c1, c2):
    R = 6371
    lat1, lon1 = c1
    lat2, lon2 = c2
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return R * (2 * atan2(sqrt(a), sqrt(1 - a)))

def extract_entities_regex(text, intent):
    text = text.lower()
    if intent == "distance":
        patterns = [r'between (.+?) and (.+)', r'from (.+?) to (.+)', r'distance (.+?) to (.+)']
        for p in patterns:
            m = re.search(p, text)
            if m: return m.group(1).strip(), m.group(2).strip()
    elif intent == "where":
        m = re.search(r'where is (.+)', text)
        if m: return m.group(1).strip()
    return None

# ==========================================
# 5. DISCORD LAYER
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    setup_db()
    logger.info(f"✅ Logged in securely as {bot.user}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Log to SQLite memory
    save_message(str(message.channel.id), str(message.author), message.content, str(message.created_at))

    if bot.user in message.mentions:
        user_prompt = message.content.replace(f"<@{bot.user.id}>", "").strip()
        
        async with message.channel.typing():
            intent = await detect_intent_llm(user_prompt)
            logger.info(f"Detected intent: {intent}")

            if intent == "news":
                articles = fetch_rss_news(user_prompt)
                if not articles:
                    await message.channel.send("Couldn't find relevant news right now.")
                    return
                combined = "\n".join(articles)
                summary = await generate_with_gemini(f"Summarise this news objectively:\n{combined}", mode="professional")
                link = articles[0].split(" - ")[-1]
                await message.channel.send(f"{summary}\n\n🔗 {link}")
                return

            if intent == "where":
                place = extract_entities_regex(user_prompt, "where") or user_prompt.replace("where is", "").strip()
                data = get_coords(place)
                if not data:
                    await message.channel.send("I couldn't locate that on the map.")
                    return
                lat, lon, name = data
                desc = await generate_with_gemini(f"What is {place}? Short factual answer.", mode="factual")
                await message.channel.send(f"{desc}\n📍 **{name}**\n🗺️ https://www.openstreetmap.org/?mlat={lat}&mlon={lon}")
                return

            if intent == "distance":
                entities = extract_entities_regex(user_prompt, "distance")
                if not entities:
                    await message.channel.send("Please specify the two locations clearly.")
                    return
                p1, p2 = entities
                c1, c2 = get_coords(p1), get_coords(p2)
                if not c1 or not c2:
                    await message.channel.send("Couldn’t resolve one or both locations.")
                    return
                dist = calculate_distance((c1[0], c1[1]), (c2[0], c2[1]))
                await message.channel.send(f"📏 The distance from **{p1}** to **{p2}** is approximately **{round(dist,2)} km**.\n🗺️ https://www.openstreetmap.org/directions?route={c1[0]},{c1[1]};{c2[0]},{c2[1]}")
                return

            # Default Chat (With SQLite Memory Context)
            chat_history = get_recent_history(message.channel.id)
            full_prompt = f"Here is the recent chat history for context:\n{chat_history}\n\nRespond to the latest message from the user."
            
            reply = await generate_with_gemini(full_prompt, mode="chat")
            await message.channel.send(reply)

    await bot.process_commands(message)

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)