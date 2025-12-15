import feedparser
import os
from google import genai
import google.generativeai as legacy_genai # We use the legacy lib just to list models easily

# --- CONFIGURATION ---
RSS_FEED_URL = "https://news.google.com/rss/search?q=(NBFC+OR+Banking)+AND+(investment+OR+deal+OR+funding+OR+acquisition+OR+merger+OR+stake)&hl=en-IN&gl=IN&ceid=IN:en"

# Get API Key
API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

def get_dynamic_model(api_key):
    """
    Automatically finds the best available 'Gemini' model that supports content generation.
    It prioritizes 'Flash' models for speed, then 'Pro', then whatever is left.
    """
    legacy_genai.configure(api_key=api_key)
    
    available_models = []
    try:
        # List all models available to your specific API Key
        for m in legacy_genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                # We only want "Gemini" models, not "PaLM" or others
                if "gemini" in m.name.lower():
                    available_models.append(m.name)
    except Exception as e:
        print(f"Warning: Could not list models ({e}). Defaulting to 'gemini-2.0-flash'")
        return "gemini-2.0-flash"

    # Sort/Filter logic to pick the best one automatically
    # Priority 1: 2.0 Flash (New standard)
    # Priority 2: 1.5 Flash (Old standard)
    # Priority 3: Any Flash (Speed)
    # Priority 4: Any Pro (Power)
    
    # Clean up model names (remove 'models/' prefix if present for matching)
    clean_names = [m.replace("models/", "") for m in available_models]

    if "gemini-2.0-flash" in clean_names:
        return "gemini-2.0-flash"
    if "gemini-1.5-flash" in clean_names:
        return "gemini-1.5-flash"
    
    # If specific versions aren't found, grab the first "flash" model
    for m in clean_names:
        if "flash" in m:
            return m
            
    # If no flash, grab the first "gemini" model found
    if clean_names:
        return clean_names[0]
        
    # Fallback if list is empty
    return "gemini-2.0-flash"

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
        print("Error: API Key (GEMINI_API_KEY or GOOGLE_API_KEY) is missing.")
        return

    # --- AUTO-SELECT MODEL ---
    selected_model = get_dynamic_model(API_KEY)
    print(f"Using Model: {selected_model}") 
    # -------------------------

    try:
        client = genai.Client(api_key=API_KEY)

        prompt = (
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

        response = client.models.generate_content(
            model=selected_model, 
            contents=prompt
        )

        print("\n" + "="*30)
        print("NBFC & BANKING INTELLIGENCE")
        print("="*30)
        print(response.text)
        print("="*30)

    except Exception as e:
        print(f"Error during analysis: {e}")

if __name__ == "__main__":
    analyze_market_news()
