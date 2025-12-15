import feedparser
import os
import time
import requests
import json

# --- CONFIGURATION ---
RSS_FEED_URL = "https://news.google.com/rss/search?q=(NBFC+OR+Banking)+AND+(investment+OR+deal+OR+funding+OR+acquisition+OR+merger+OR+stake)&hl=en-IN&gl=IN&ceid=IN:en"

# UPDATED MODEL LIST (DECEMBER 2025 STANDARDS)
# We try the newest available models first.
MODELS = [
    "gemini-2.5-flash",          # Current standard (Fast & Stable)
    "gemini-2.5-flash-lite",     # High-availability / Backup
    "gemini-3.0-pro-preview",    # Newest Engine (Try this!)
    "gemini-2.0-flash"           # Fallback
]

API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

def analyze_market_news():
    print("Fetching NBFC & Banking Deal news...")
    
    feed = feedparser.parse(RSS_FEED_URL)
    headlines = []
    for entry in feed.entries[:10]:
        headlines.append(f"- {entry.title}")

    if not headlines:
        print("No specific deal news found today.")
        return

    print(f"Found {len(headlines)} headlines. Sending to AI for analysis...")

    if not API_KEY:
        print("Error: API Key is missing.")
        return

    prompt_text = (
        "You are a financial analyst. Review these news headlines about NBFCs and Banking.\n"
        "Identify and summarize ONLY:\n"
        "1. New Investments (Who invested in whom?)\n"
        "2. Mergers & Acquisitions (Deals)\n"
        "3. Major Regulatory Updates affecting the sector\n\n"
        "Headlines:\n"
        + "\n".join(headlines) + "\n\n"
        "Output Format:\n"
        "- **Deals & Investments:** [List details]\n"
        "- **Top Sector News:** [Major non-deal updates]\n"
        "If nothing relevant is found in a category, write 'None'."
    )

    # --- THE DIRECT API LOOP ---
    success = False

    for model in MODELS:
        print(f"Attempting direct connection to: {model}...")
        
        # Note: We use the 'v1beta' endpoint which supports the new models
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={API_KEY}"
        
        headers = {'Content-Type': 'application/json'}
        data = {
            "contents": [{
                "parts": [{"text": prompt_text}]
            }]
        }

        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                try:
                    text_output = result['candidates'][0]['content']['parts'][0]['text']
                    print("\n" + "="*30)
                    print(f"SUCCESS with {model}")
                    print("="*30)
                    print(text_output)
                    print("="*30)
                    success = True
                    break 
                except (KeyError, IndexError):
                    print(f"Model {model} returned 200 OK but unreadable format.")
                    continue

            elif response.status_code == 429:
                print(f"Model {model} is busy (Quota Exceeded). Trying next...")
                time.sleep(1)
            
            elif response.status_code == 404:
                print(f"Model {model} not found (may not be released to your key yet). Trying next...")
            
            else:
                print(f"Model {model} failed with Status {response.status_code}: {response.text}")

        except Exception as e:
            print(f"Connection error with {model}: {e}")

    if not success:
        print("CRITICAL: All models failed. Your API key may have no access to 2.5/3.0 models yet.")

if __name__ == "__main__":
    analyze_market_news()
