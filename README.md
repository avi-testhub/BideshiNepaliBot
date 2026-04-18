# BideshiNepaliBot: Technical Overview & Development Journey

This repository documents the development of a Discord-based AI operations assistant. The project transitioned from an experimental bilingual script to a hybrid cloud-local AI agent designed for specialized tasks: market auditing, geographical resolution, and automated information retrieval.

## Developer Profile & Methodology
**Developer:** Avi

**Methodology: Vibe Coding** This project was built with a very limited foundational background in Python. The development process relied almost entirely on "vibe coding"—an iterative, prompt-heavy approach to building software.
* **Phase 1:** Initial logic and structure were drafted using the paid version of **ChatGPT**.
* **Phase 2:** The project transitioned to **Gemini Pro** for more complex refactoring and the implementation of the hybrid architecture.
* **Process:** The development involved extensive trial and error, identifying system failures through continuous manual auditing rather than formal software testing suites.

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
| **Phase 1: Pure LLM** | Internal knowledge only | ![Pure LLM Output](image_fc32a8.png) |
| **Phase 2: Validated Logic** | Python Math + OpenStreetMap | ![Validated OSM Output](1%20-%20Map%20distance%20calculator.jpg) |

*The system provides precise calculations and forces a plotted OpenStreetMap route link for verification.*

### 📈 Financial Market Auditing
Integrated with `yfinance` to monitor trading movements. This feature allows for the correlation of media sentiment with actual market volatility.

![Stock Performance Comparison](2%20-%20Market%20research.jpg)
![Business Model Analysis](2%20-%20Market%20research%20contd.jpg)
*Fig: Comparative stock performance snapshots and business model metrics.*

The bot also handles broad market analysis for regulatory briefings:
![Market Trend Summary](2%20-%20Market%20analysis.jpg)
*Fig: Automated 5-point market trend summary.*

### 📄 Automated Briefing
The system processes broad informational queries into constrained, scannable summaries (e.g., under 200 words).

![Summarization Example](3%20-%20Information%20request.jpg)
*Fig: Fact-based summarization of historical data.*

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

* **Conversation Memory (SQLite3):** Currently in the pipeline. An asynchronous SQLite layer is being refactored to allow the bot to summarize past channel history or specific user statements.
* **Multimodal Auditing:** Future support for ingesting screenshots of financial reports for automated table extraction and sentiment analysis.
* **Regional Sentry v2:** Refining the hybrid parser to eliminate "Global Leakage" and ensure source integrity for specific international markets.

## Setup
1. Define `DISCORD_TOKEN` and `GEMINI_API_KEY` in `.env`.
2. Install dependencies: `pip install discord.py google-genai requests yfinance feedparser python-dotenv`.
3. Ensure Ollama is running LLaMA 3 for local fallback support.
