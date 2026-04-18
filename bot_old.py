import discord
from discord.ext import commands
import requests
import sqlite3
from datetime import datetime
import feedparser
import re
import time
from math import radians, sin, cos, sqrt, atan2

# ===== CONFIG =====
HF_API_KEY = "<INSERT KEY HERE>"

# ===== LLaMA 3 =====
def generate_with_llama3(prompt):
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "llama3", "prompt": prompt, "stream": False},
            timeout=60
        )
        return response.json().get("response", "").strip()
    except:
        return "⚠️ AI not responding."

# ===== IMAGE GENERATION =====
def generate_image(prompt):
    API_URL = "https://api-inference.huggingface.co/models/stabilityai/sdxl-turbo"

    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }

    session = requests.Session()
    session.trust_env = False  
    try:
        response = session.post(
            API_URL,
            headers=headers,
            json={"inputs": prompt},
            timeout=60
        )

        print("FINAL URL:", response.url)
        print("STATUS:", response.status_code)

        if response.status_code == 200 and "image" in response.headers.get("content-type", ""):
            file = "generated.png"
            with open(file, "wb") as f:
                f.write(response.content)
            return file

        print("HF ERROR:", response.text)

    except Exception as e:
        print("IMAGE ERROR:", e)

    return None

# ===== DATABASE =====
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

def save_message(cid, author, content, ts):
    c.execute("INSERT INTO messages VALUES (?, ?, ?, ?)",
              (cid, author, content, ts))
    conn.commit()

# ===== RSS NEWS =====
def fetch_rss_news(query=None):
    feeds = [
        "http://feeds.bbci.co.uk/news/rss.xml",
        "http://rss.cnn.com/rss/edition.rss",
        "https://www.reutersagency.com/feed/"
    ]

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

# ===== GEO =====
def get_coords(place):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": place, "format": "json", "limit": 1}
    headers = {"User-Agent": "BideshiNepaliBot"}

    res = requests.get(url, params=params, headers=headers).json()

    if res:
        return float(res[0]["lat"]), float(res[0]["lon"]), res[0]["display_name"]

    return None

def calculate_distance(c1, c2):
    R = 6371
    lat1, lon1 = c1
    lat2, lon2 = c2

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return R * (2 * atan2(sqrt(a), sqrt(1 - a)))

# ===== INTENT =====
def detect_intent(text):
    t = text.lower()

    if any(x in t for x in ["news", "latest", "update", "happening", "today", "current"]):
        return "news"

    if any(x in t for x in ["distance", "how far", "km"]):
        return "distance"

    if any(x in t for x in ["where is", "location", "located"]):
        return "where"

    if any(x in t for x in ["image", "draw", "generate", "picture"]):
        return "image"

    return "chat"

def extract_distance(text):
    text = text.lower()

    patterns = [
        r'between (.+?) and (.+)',
        r'from (.+?) to (.+)',
        r'(.+?) to (.+)'
    ]

    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1).strip(), m.group(2).strip()

    return None, None

def extract_where(text):
    m = re.search(r'where is (.+)', text.lower())
    if m:
        return m.group(1).strip()
    return None

# ===== DISCORD =====
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

# ===== COMMANDS =====
@bot.command()
async def news(ctx, *, query=None):
    await ctx.typing()

    articles = fetch_rss_news(query)
    if not articles:
        await ctx.send("No relevant news found.")
        return

    combined = "\n".join(articles)

    summary = generate_with_llama3(f"Summarise clearly:\n{combined}")
    link = articles[0].split(" - ")[-1]

    await ctx.send(f"{summary}\n\n🔗 {link}")

@bot.command()
async def distance(ctx, *, query):
    await ctx.typing()

    p1, p2 = extract_distance(query)

    if not p1 or not p2:
        await ctx.send("Use: !distance A to B")
        return

    c1 = get_coords(p1)
    c2 = get_coords(p2)

    print("DEBUG:", p1, p2, c1, c2)

    if not c1 or not c2:
        await ctx.send("Couldn’t find locations.")
        return

    dist = calculate_distance((c1[0], c1[1]), (c2[0], c2[1]))

    map_link = f"https://www.openstreetmap.org/directions?route={c1[0]},{c1[1]};{c2[0]},{c2[1]}"

    await ctx.send(f"{p1} → {p2} ≈ {round(dist,2)} km\n🗺️ {map_link}")

@bot.command()
async def where(ctx, *, place):
    await ctx.typing()

    data = get_coords(place)
    if not data:
        await ctx.send("Location not found.")
        return

    lat, lon, name = data
    map_link = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}"

    desc = generate_with_llama3(f"What is {place}? Short answer.")

    await ctx.send(f"{desc}\n📍 {name}\n🗺️ {map_link}")

@bot.command()
async def image(ctx, *, prompt):
    await ctx.typing()

    file = generate_image(prompt)

    if not file:
        await ctx.send("Couldn’t generate image.")
        return

    await ctx.send(file=discord.File(file))

# ===== NATURAL LANGUAGE =====
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    save_message(str(message.channel.id), str(message.author),
                 message.content, str(message.created_at))

    if bot.user in message.mentions:
        user_prompt = message.content.replace(f"<@{bot.user.id}>", "").strip()
        intent = detect_intent(user_prompt)

        # NEWS
        if intent == "news":
            articles = fetch_rss_news(user_prompt)
            if not articles:
                await message.channel.send("No relevant news found.")
                return

            combined = "\n".join(articles)
            summary = generate_with_llama3(f"Summarise:\n{combined}")
            link = articles[0].split(" - ")[-1]

            await message.channel.send(f"{summary}\n\n🔗 {link}")
            return

        # IMAGE
        if intent == "image":
            file = generate_image(user_prompt)
            if not file:
                await message.channel.send("Couldn’t generate image.")
                return
            await message.channel.send(file=discord.File(file))
            return

        # WHERE
        if intent == "where":
            place = extract_where(user_prompt)
            data = get_coords(place)

            if not data:
                await message.channel.send("Location not found.")
                return

            lat, lon, name = data
            map_link = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}"

            desc = generate_with_llama3(f"What is {place}?")
            await message.channel.send(f"{desc}\n📍 {name}\n🗺️ {map_link}")
            return

        # DISTANCE
        if intent == "distance":
            p1, p2 = extract_distance(user_prompt)
            c1 = get_coords(p1)
            c2 = get_coords(p2)

            if not c1 or not c2:
                await message.channel.send("Couldn’t find locations.")
                return

            dist = calculate_distance((c1[0], c1[1]), (c2[0], c2[1]))
            map_link = f"https://www.openstreetmap.org/directions?route={c1[0]},{c1[1]};{c2[0]},{c2[1]}"

            await message.channel.send(f"{p1} → {p2} ≈ {round(dist,2)} km\n🗺️ {map_link}")
            return

        # DEFAULT CHAT
        reply = generate_with_llama3(
            f"Answer clearly, friendly, short: {user_prompt}"
        )
        await message.channel.send(reply)

    await bot.process_commands(message)

bot.run("<INSERT KEY HERE>")