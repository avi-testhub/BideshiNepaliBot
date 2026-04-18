import os
import re
import json
import logging
import sqlite3
import requests
import feedparser
import yfinance as yf
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
# Look for .env in the same folder as this script
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# Correct way to load keys: Do NOT paste actual keys here!
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not DISCORD_TOKEN or not GEMINI_API_KEY:
    print(f"CRITICAL ERROR: Keys not found at {env_path}")
    # This prevents the bot from even trying to start if keys are missing
    exit()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Gemini Client
client = genai.Client(api_key=GEMINI_API_KEY)

# ==========================================
# 2. MARKET DATA LAYER (Weekend Proof)
# ==========================================
def get_market_comparison(ticker, period="5d"):
    """Fetches market data. 5d period ensures we find Friday prices on weekends."""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        
        if hist.empty or len(hist) < 1: 
            return None
        
        # Get the very last available closing price
        current_p = hist['Close'].iloc[-1]
        
        # Get the previous day's price for comparison
        if len(hist) >= 2:
            prev_p = hist['Close'].iloc[-2]
            change = ((current_p - prev_p) / prev_p) * 100
        else:
            prev_p = current_p
            change = 0.0

        return {
            "ticker": ticker.upper(), 
            "price": round(current_p, 2), 
            "change": round(change, 2), 
            "currency": stock.info.get('currency', 'USD')
        }
    except:
        return None

# ==========================================
# 3. HYBRID AI LAYER (Intent + Fallback)
# ==========================================
async def analyze_query_entities(user_input):
    """Uses Gemini Flash to extract what the user wants."""
    prompt = f"""
    Analyze the user input. Return ONLY a JSON object.
    Intents: 'distance' (loc1, loc2), 'market' (ticker), 'top_stocks', 'where' (loc), 'chat'.
    Input: "{user_input}"
    """
    try:
        res = await client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(res.text)
    except:
        t = user_input.lower()
        if "top" in t and "stock" in t: return {"intent": "top_stocks"}
        if "distance" in t or "between" in t: return {"intent": "distance"}
        return {"intent": "chat"}

async def generate_hybrid_text(prompt):
    """Cloud-to-Local Fallback (Gemini -> LLaMA 3)."""
    try:
        res = await client.aio.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return res.text.strip()
    except:
        logger.warning("Gemini limit reached. Using Local LLaMA 3...")
        try:
            res = requests.post("http://localhost:11434/api/generate", 
                                json={"model": "llama3", "prompt": prompt, "stream": False}, timeout=15)
            return res.json().get("response", "").strip()
        except:
            return "⚠️ I'm currently disconnected from my AI brains. Please check back later."

# ==========================================
# 4. GEO & UTILITY LAYER
# ==========================================
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
    logger.info(f"✅ Bot is Live: {bot.user}")

@bot.event
async def on_message(message):
    if message.author == bot.user: return

    if bot.user in message.mentions:
        user_prompt = re.sub(r'<@!?\d+>', '', message.content).strip()
        
        async with message.channel.typing():
            analysis = await analyze_query_entities(user_prompt)
            intent = analysis.get("intent")

            # 1. TOP 5 STOCKS (Weekend Proof)
            if intent == "top_stocks":
                tickers = ["NVDA", "AAPL", "MSFT", "GOOGL", "AMZN"]
                res_list = []
                for t in tickers:
                    d = get_market_comparison(t)
                    if d: res_list.append(f"**{t}**: {d['price']} USD ({d['change']}%)")
                
                await message.channel.send("📈 **Top 5 S&P 500 Stocks (Latest Trading Data)**\n" + "\n".join(res_list))

            # 2. INDIVIDUAL MARKET LOOKUP
            elif intent == "market":
                ticker = analysis.get("ticker", "SPY").upper()
                d = get_market_comparison(ticker)
                if d:
                    await message.channel.send(f"📊 **{d['ticker']} Snapshot**\nPrice: {d['price']} {d['currency']}\n24h Change: {d['change']}%")
                else:
                    await message.channel.send(f"Could not find data for {ticker}.")

            # 3. DISTANCE (FORCED MAP FIX)
            elif intent == "distance":
                loc1, loc2 = analysis.get("loc1"), analysis.get("loc2")
                # Backup regex if AI parsing locs fails
                if not loc1 or not loc2:
                    parts = re.split(r' to | and | between ', user_prompt.lower())
                    loc1, loc2 = parts[-2].strip(), parts[-1].strip()

                c1, c2 = get_coords(loc1), get_coords(loc2)
                if c1 and c2:
                    dist_km = round(calculate_distance(c1, c2), 2)
                    ai_text = await generate_hybrid_text(f"Friendly answer: distance between {loc1} and {loc2} is {dist_km}km.")
                    
                    # Manual Append: The Map Link is NEVER missing now
                    map_url = f"https://www.openstreetmap.org/directions?route={c1[0]},{c1[1]};{c2[0]},{c2[1]}"
                    await message.channel.send(f"📏 {ai_text}\n🗺️ **View Plotted Route:** {map_url}")
                else:
                    await message.channel.send("I couldn't resolve those locations on the map.")

            # 4. DEFAULT CHAT
            else:
                reply = await generate_hybrid_text(user_prompt)
                await message.channel.send(reply)

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)