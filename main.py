import feedparser
import os
import time
import requests
import smtplib
import urllib.parse
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dateutil import parser
from difflib import SequenceMatcher

# --- CONFIGURATION ---

# 1. GENERAL SECTOR KEYWORDS
GENERAL_KEYWORDS = [
    "NBFC", "Non-Banking Financial Company", "Shadow Bank", "Fintech Lender", 
    "Microfinance", "Housing Finance", "Gold Loan"
]

# 2. WATCHLIST (User List + Extracted from BCG Report)
WATCHLIST_COMPANIES = [
    "SBFC Finance", "Kogta Financial", "Bajaj Finance", "HDB Financial", "Tata Capital", 
    "Shriram Finance", "Sundaram Finance", "Poonawalla Fincorp", "Godrej Capital", 
    "Hero FinCorp", "Anand Rathi", "Piramal Capital", "Aditya Birla Capital", 
    "Cholamandalam Investment", "Mahindra Finance", "L&T Finance", "IIFL Finance", 
    "Capri Global", "Ugro Capital", "Clix Capital", "APC", 
    "LIC Housing Finance", "Repco Home Finance", "Can Fin Homes", "PNB Housing", 
    "GIC Housing", "IndoStar Capital", "Bajaj Housing Finance", "Samman Capital",
    "CreditAccess Grameen", "Satin Creditcare", "Asirvad Microfinance", 
    "Muthoot Finance", "Manappuram Finance", "SBI Card", "Spandana Sphoorty"
]

# 3. ACTION KEYWORDS
ACTIONS = [
    "investment", "deal", "funding", "stake", "partnership", "tie-up", 
    "launch", "product", "appoint", "CEO", "MD", "resign", 
    "report", "outlook", "earnings", "profit", "quarter", "result", "Q3", "Q4"
]

# 4. CREDIBLE SOURCES WHITELIST
# Only news from these domains/names will be processed.
CREDIBLE_SOURCES = [
    "Economic Times", "The Economic Times", "Livemint", "Mint", 
    "Business Standard", "Moneycontrol", "Financial Express", 
    "CNBC-TV18", "CNBC", "The Hindu Business Line", "Bloomberg", 
    "Reuters", "NDTV Profit", "Business Today", "Inc42", 
    "Entrackr", "VCCircle", "Fortune India", "Forbes India"
]

# 5. STOCK NOISE FILTER (Extended for Trading Outlooks)
STOCK_NOISE_KEYWORDS = [
    # Price Movements
    "share price", "stock price", "shares", "stocks", "closing", "trading", 
    "intraday", "market cap", "m-cap", "valuation", "sensex", "nifty", "bse", "nse",
    "bull", "bear", "rally", "plunge", "surges", "jumps", "falls", "soars", "hits", 
    "52-week", "upper circuit", "lower circuit", "investors lose", "wealth erodes", 
    "top loser", "top gainer", "flat", "volatile", "gains", "losses", "green", "red",
    
    # Technical Analysis
    "technical analysis", "chart", "candlestick", "moving average", "rsi", "macd",
    "support level", "resistance level", "breakout", "breakdown", "pivot", "volume",
    "momentum", "trendline", "crossover", "technicals", "chart check",
    
    # Brokerage/Analyst Ratings
    "buy rating", "sell rating", "accumulate", "hold rating", "target price", 
    "target of", "upside", "downside", "stop loss", "brokerage view", "recommends",
    
    # Trading Outlooks & Day Trading (NEW EXTENSION)
    "stocks to watch", "stocks to buy", "market live", "live updates", "stock picks",
    "trading ideas", "morning trade", "opening bell", "closing bell", "market wrap",
    "pre-market", "after-market", "ahead of market", "market prediction", "trade setup",
    "hot stocks", "buzzing stocks", "options", "futures", "f&o", "derivative", 
    "call option", "put option", "bank nifty", "nifty prediction",
    
    # Corporate Actions (often considered noise for strategic updates)
    "dividend", "bonus issue", "stock split", "record date", "ex-dividend", "demat"
]

# Priority Models
MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite", 
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-1.5-pro"
]

# API Keys & Secrets
API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASS")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER") # Can be "a@b.com,c@d.com"

def generate_rss_links():
    """Generates multiple RSS links to ensure we cover ALL companies."""
    links = []
    
    # Batch 1: General Sector News (Last 48h)
    gen_keys_str = ' OR '.join(GENERAL_KEYWORDS)
    act_keys_str = ' OR '.join(ACTIONS)
    general_query = f"({gen_keys_str}) AND ({act_keys_str}) AND India when:2d"
    
    encoded_gen = urllib.parse.quote(general_query)
    links.append(f"https://news.google.com/rss/search?q={encoded_gen}&hl=en-IN&gl=IN&ceid=IN:en")

    # Batch 2 & 3: Specific Company News
    chunk_size = 10
    for i in range(0, len(WATCHLIST_COMPANIES), chunk_size):
        chunk = WATCHLIST_COMPANIES[i:i + chunk_size]
        chunk_str = ' OR '.join(f'"{c}"' for c in chunk)
        company_query = f"({chunk_str}) AND India when:2d"
        
        encoded_co = urllib.parse.quote(company_query)
        links.append(f"https://news.google.com/rss/search?q={encoded_co}&hl=en-IN&gl=IN&ceid=IN:en")
        
    return links

def is_within_last_48_hours(published_string):
    """Checks if the news article is actually from the last 2 days."""
    try:
        pub_date = parser.parse(published_string)
        if pub_date.tzinfo is not None:
            pub_date = pub_date.replace(tzinfo=None)
        
        delta = datetime.utcnow() - pub_date
        return delta.days <= 2
    except:
        return True 

def clean_text(text):
    """
    1. Removes source suffix (e.g. ' - Times of India').
    2. Removes special chars.
    3. Lowers case.
    """
    # Remove RSS Source suffix (anything after ' - ')
    text = re.split(r'\s-\s', text)[0]
    return re.sub(r'[^a-zA-Z0-9\s]', '', text).lower().strip()

def is_stock_noise(title):
    """Returns True if the title sounds like generic stock market noise."""
    clean_title = clean_text(title)
    
    for word in STOCK_NOISE_KEYWORDS:
        if word in clean_title:
            # Exception: Allow 'profit/result' news even if it mentions 'jumps' (e.g., "Profit jumps")
            # But strictly block technical terms like 'target price' or 'share price'
            if "profit" in clean_title or "result" in clean_title or "earnings" in clean_title or "revenue" in clean_title:
                # STRICT BLOCK for share/stock specific keywords even inside earnings news
                bad_context = ["share", "stock", "target", "buy", "sell", "dividend", "split"]
                if any(b in clean_title for b in bad_context):
                    return True 
                return False 
            return True
    return False

def is_credible_source(entry):
    """Checks if the news source is in our credible list."""
    if not hasattr(entry, 'source'):
        return False
        
    source_title = entry.source.get('title', '').strip()
    
    # Check exact match or substring (e.g. "Mint" in "Livemint")
    for credible in CREDIBLE_SOURCES:
        if credible.lower() in source_title.lower():
            return True
            
    return False

def get_word_set(text):
    """Extracts significant words (len > 3) to form a fingerprint."""
    cleaned = clean_text(text)
    return set(w for w in cleaned.split() if len(w) > 3)

def is_duplicate(new_title, existing_titles):
    """
    Uses Jaccard Similarity (Set Overlap).
    If >45% of the words in the new title exist in an old title, it's a duplicate.
    """
    new_words = get_word_set(new_title)
    if not new_words: return False 
    
    for existing in existing_titles:
        existing_words = get_word_set(existing)
        
        # Calculate Jaccard Similarity: Intersection / Union
        intersection = new_words.intersection(existing_words)
        union = new_words.union(existing_words)
        
        if len(union) == 0: continue
        
        jaccard_score = len(intersection) / len(union)
        
        # Threshold 0.45: slightly more aggressive deduping
        if jaccard_score > 0.45:
            return True
                
    return False

def send_email(html_body):
    if not EMAIL_USER or not EMAIL_PASS or not EMAIL_RECEIVER:
        print("Skipping email: Missing secrets.")
        return

    # HANDLE MULTIPLE RECIPIENTS
    recipients = [email.strip() for email in EMAIL_RECEIVER.split(',')]

    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = ", ".join(recipients) # Display list in "To" header
        msg['Subject'] = f"🚀 MD's Briefing: NBFC & Banking Pulse - {datetime.now().strftime('%d %b %Y')}"

        final_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #f4f6f8; margin: 0; padding: 0; color: #333; }}
                .container {{ max-width: 750px; margin: 30px auto; background-color: #ffffff; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); overflow: hidden; border: 1px solid #e1e4e8; }}
                .header {{ background: linear-gradient(135deg, #003366 0%, #004080 100%); color: #ffffff; padding: 30px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 24px; font-weight: 600; letter-spacing: 0.5px; }}
                .header p {{ margin: 10px 0 0 0; font-size: 14px; opacity: 0.9; }}
                .content {{ padding: 30px; line-height: 1.6; }}
                h3 {{ color: #004080; border-bottom: 2px solid #f0f2f5; padding-bottom: 8px; margin-top: 25px; font-size: 18px; }}
                ul {{ padding-left: 20px; }}
                li {{ margin-bottom: 15px; list-style-type: none; }}
                a {{ color: #0066cc; text-decoration: none; font-weight: 500; }}
                a:hover {{ text-decoration: underline; }}
                .summary {{ display: block; margin-top: 4px; color: #555; font-size: 13px; font-style: italic; }}
                .footer {{ background-color: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; color: #888; border-top: 1px solid #eee; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🇮🇳 NBFC & Banking Intelligence</h1>
                    <p>{datetime.now().strftime('%A, %d %B %Y')} | Last 48 Hours Update</p>
                </div>
                <div class="content">
                    {html_body}
                </div>
                <div class="footer">
                    <p>Generated by <strong>Gemini 2.5 AI Bot</strong> | Market Intelligence Unit</p>
                    <p>Tracking {len(WATCHLIST_COMPANIES)} Companies • Daily 9:30 AM IST Update</p>
                </div>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(final_html, 'html'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        
        # SEND TO LIST OF RECIPIENTS
        server.sendmail(EMAIL_USER, recipients, msg.as_string())
        
        server.quit()
        print(f"✅ Executive Briefing sent to {len(recipients)} recipients!")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

def call_gemini_with_retry(model, prompt, retries=3):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}

    for attempt in range(retries):
        try:
            response = requests.post(url, headers=headers, json=data, timeout=120)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 503:
                time.sleep(5)
                continue 
            elif response.status_code == 429:
                return None 
            elif response.status_code == 404:
                return None
            else:
                return None
        except Exception:
            return None
    return None

def analyze_market_news():
    print(f"Scanning news (Past 48H) for {len(WATCHLIST_COMPANIES)} NBFCs...")
    
    rss_links = generate_rss_links()
    all_headlines = []
    seen_titles = [] 
    seen_links = set() 

    for link in rss_links:
        try:
            feed = feedparser.parse(link)
            if not feed.entries:
                continue
            for entry in feed.entries:
                title = entry.title
                url = entry.link
                
                # 1. EXACT URL CHECK
                if url in seen_links: continue
                
                # 2. STRICT DATE CHECK
                if hasattr(entry, 'published') and not is_within_last_48_hours(entry.published):
                    continue 

                # 3. CREDIBLE SOURCE CHECK
                if not is_credible_source(entry):
                    continue

                # 4. STOCK NOISE CHECK
                if is_stock_noise(title):
                    continue

                # 5. SMART DEDUPLICATION (Jaccard)
                if is_duplicate(title, seen_titles):
                    continue
                
                # If valid unique business news, add it
                # We append source title to the output for the AI to see context
                source_name = entry.source.get('title', 'News')
                all_headlines.append(f"Title: {title} | Source: {source_name} | Link: {url}")
                seen_titles.append(title)
                seen_links.add(url)
                
        except Exception as e:
            print(f"Error fetching batch: {e}")
    
    final_headlines = all_headlines[:60]

    if not final_headlines:
        print("No news found in the last 48 hours for the watchlist.")
        return

    print(f"Found {len(final_headlines)} unique, credible headlines. Generating Report...")

    if not API_KEY:
        print("Error: API Key is missing.")
        return

    # --- THE PROMPT ---
    prompt_text = (
        "You are a Market Intelligence Analyst. Review these news headlines (from the last 48 hours) "
        "and create a beautiful, professional HTML daily briefing for the MD. "
        "Focus strictly on the Indian NBFC/Banking sector.\n\n"
        
        "**Output Guidelines (STRICT HTML):**\n"
        "1. Return **ONLY valid HTML** content (start with `<h3>`). Do not use <html> or <body> tags.\n"
        "2. **Headers:** Use `<h3>` tags with Emojis for sections.\n"
        "3. **Lists:** Use `<ul>` lists. Each item should be `<li>`.\n"
        "4. **Links:** The headline MUST be a clickable link: `<a href='URL'>Headline Text</a>`.\n"
        "5. **Summary:** Add a `<span class='summary'>👉 Summary: [One sentence impact analysis]</span>` inside the `<li>`.\n"
        "6. **No News:** If a category is empty, write `<i>No significant updates in the last 48h.</i>`.\n"
        "7. **Cleanliness:** Do NOT include repetitive news. If two headlines are about the same event, combine them or pick the best one.\n\n"

        "**Required Categories:**\n"
        "1. 📊 Earnings & Financial Performance\n"
        "2. 💰 Deals, M&A & Fundraising\n"
        "3. 📑 Reports, Ratings & Brokerage Outlook\n"
        "4. 🤝 Strategic Partnerships & Tie-ups\n"
        "5. 🚀 Product Launches & Business Expansion\n"
        "6. 👔 Leadership Moves & Regulatory Circulars\n\n"

        "**Input Headlines:**\n"
        + "\n".join(final_headlines)
    )

    # --- THE MAIN LOOP ---
    success = False
    
    for model in MODELS:
        print(f"Attempting direct connection to: {model}...")
        result = call_gemini_with_retry(model, prompt_text)
        if result:
            try:
                text_output = result['candidates'][0]['content']['parts'][0]['text']
                text_output = text_output.replace("```html", "").replace("```", "")
                print("\n" + "="*30 + f"\nSUCCESS with {model}\n" + "="*30)
                send_email(text_output)
                success = True
                break 
            except (KeyError, IndexError):
                continue

    if not success:
        print("CRITICAL: All models failed. No email sent.")

if __name__ == "__main__":
    analyze_market_news()
