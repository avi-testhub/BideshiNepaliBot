# BideshiNepaliBot: Hybrid AI Intelligence & Operations Assistant

This repository documents the development of a Discord bot designed for both specialized operational tasks like market auditing and geographical resolution and standard general-purpose chatting. 

In Nepali, "Bideshi" means "Foreign." The term BideshiNepali refers to the global Nepalese diaspora, those living and working outside of Nepal. The bot is named to reflect this identity: a technical tool for navigating international life (markets, geography, news) while staying connected to Nepali roots.

## Developer Profile & Methodology
**Developer:** Avi

**Methodology: Vibe Coding** This project was built with a very limited foundational background in Python, which proved insufficient for complex architecture. Consequently, the development process relied almost entirely on **"vibe coding"** - an iterative, prompt-heavy approach to building software through high-level intent rather than manual syntax writing.
* **Phase 1:** Initial logic and structure were drafted using the paid version of **ChatGPT**.
* **Phase 2:** The project transitioned to **Gemini Pro** for more complex refactoring and the implementation of the hybrid architecture.
* **Process:** The development involved extensive trial and error. Systems were "audited" through continuous manual interaction to identify edge cases and logic failures.

---

## 🛠️ Prompting & Iteration Metrics

Because the development followed a **"Vibe Coding"** methodology, the project represents approximately **70–90 high-level prompts** across both ChatGPT and Gemini Pro.

### Process Breakdown:
**Total Estimated Prompts: ~100**
1. **System Refinement (~35 prompts):** Repeated requests for "Full Code" to ensure that various disparate modules (Geo-spatial math, Market APIs, and RSS parsers) were integrated without breaking the asynchronous Discord event loop.
2. **Feature Deep-Dives (~25 prompts):** Specifically tuning the "Regional Sentry" to prevent global news leakage and implementing weekend-proof logic for stock market data.
3. **Audit-Driven Debugging (~30 prompts):** Identifying and resolving failures in the intent router, such as the bot's stubbornness in defaulting to BBC links for UAE-based news queries.
4. **Environment & Documentation (~10 prompts):** Handling .env setup, dependency troubleshooting, and README asset mapping.
   
---

## Technical Architecture: Hybrid AI Orchestration

To ensure 100% operational uptime, the bot utilizes a "Cloud-First, Local-Second" failsafe:
* **Primary Engine:** Google Gemini 2.5 Flash (Cloud).
* **Fallback Engine:** LLaMA 3 (Local via Ollama).

If the system detects an API quota limit (HTTP 429) or connection failure, it automatically reroutes the prompt to the local hardware.

---

## Core Feature Breakdown

### 🌍 Geographical Resolution & OSM Integration
The bot resolves coordinates via the Nominatim API and calculates the great-circle distance using the **Haversine formula**. This avoids the hallucinations common in pure LLM distance estimations.

| Iteration Phase | Logic | Result |
| :--- | :--- | :--- |
| **Validated Logic** | Python Math + OpenStreetMap | ![Validated OSM Output](1%20-%20Map%20distance%20calculator.jpg) |

*The system provides precise calculations and forces a plotted OpenStreetMap route link for verification. You can see that initially, the BOT failed to generate the answer - this was due to the constraints in the token limitaions - after adding a failsafe mechanism to use LLAMA3 locally if the token ran out - the prompt was executed.*

### 📈 Financial Market Auditing
Integrated with `yfinance` to monitor trading movements. This feature allows for the correlation of media sentiment with actual market volatility.

![Stock Performance Comparison](2%20-%20Market%20research.jpg)
![Business Model Analysis](2%20-%20Market%20research%20contd.jpg)
*Fig: Comparative stock performance snapshots and business model metrics.*

The bot also handles broad market analysis:
![Market Trend Summary](2%20-%20Market%20analysis.jpg)
*Fig: Automated 5-point market trend summary.*

### 📄 Automated Briefing
The system processes broad informational queries into constrained, scannable summaries (e.g., under 200 words).

![Summarization Example](3%20-%20Information%20request.jpg)
*Fig: Fact-based summarization of historical data.*

### 🇳🇵 Translation & Linguistic Analysis
The bot can translate sentences from various languages into English. It attempts to explain grammatical components like verbs and conjunctions to provide better context for code-switching.

![Translation Breakdown Example](5%20-%20translation.jpg)
*Fig: Etymological breakdown of a Nepali sentence.*

_Note: This feature is highly dependent on the cloud model (Gemini). When the system falls back to **LLaMA 3**, translation results are often "not so great", failing to capture the nuances of grammar or cultural context._

---

## Operational Challenges: The "BBC Leak"

A persistent technical hurdle identified during the auditing phase is **strict regional news adherence**. Despite a whitelist of regional RSS feeds (NZ, AUS, Nepal, UAE, SEA), the intent classifier occasionally fails to distinguish between "Regional" and "Global" contexts.

**Technical Deficit:** The system sometimes defaults to its primary global source (BBC) even when specific regional updates are requested.

| Regional Target | Logic Outcome | Evidence |
| :--- | :--- | :--- |
| **Australia (AUS)** | Successful Routing | ![Successful AUS Routing](4%20-%20news.jpg) |
| **UAE** | Intent Mismatch (None) | ![UAE Intent Failure](4%20-%20news2%20error%20UAE.jpg) |
| **UAE** | Global Leakage (BBC) | ![UAE Global Default](4%20-%20news3%20error%20UAE.jpg) |

*The UAE module is currently inconsistent, frequently defaulting to UK-centric data from the BBC feed despite hard-coded overrides.*

---

## Development Roadmap & Pipeline

* **Conversation Memory (SQLite3):** **[IN PIPELINE]** An asynchronous SQLite layer is being refactored to allow the bot to summarize past channel history or specific user statements. Previous iterations were deprecated due to retrieval errors.
* **Multimodal Auditing:** Future support for ingesting screenshots of financial reports for automated table extraction and sentiment analysis.
* **Regional Sentry v2:** Refining the hybrid parser to eliminate "Global Leakage" and ensure source integrity for specific international markets.
* **Bilingual Capability:** Implementing native support for switching between English and Nepali.
* **Cultural Nuance:** Tuning the bot to understand Nepalese social hierarchies (respectful address), kinship terms, and idioms.

## Setup
1. Define `DISCORD_TOKEN` and `GEMINI_API_KEY` in `.env`.
2. Install dependencies: `pip install discord.py google-genai requests yfinance feedparser python-dotenv`.
3. Ensure Ollama is running LLaMA 3 for local fallback support.

