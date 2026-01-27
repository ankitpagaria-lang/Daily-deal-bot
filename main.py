import feedparser
import os
import time
import requests
import smtplib
import urllib.parse
import re
import hashlib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from dateutil import parser
from difflib import SequenceMatcher

# --- CONFIGURATION ---

# 1. GENERAL SECTOR KEYWORDS
GENERAL_KEYWORDS = [
    "NBFC", "Non-Banking Financial Company", "Shadow Bank", "Fintech Lender", 
    "Microfinance", "Housing Finance", "Gold Loan", "SME Lending", "Vehicle Finance"
]

# 2. EXTENDED WATCHLIST (Major Indian NBFCs & Relevant Banks)
WATCHLIST_COMPANIES = [
    # Large Cap / Diversified
    "Bajaj Finance", "Shriram Finance", "Cholamandalam Investment", "Muthoot Finance",
    "Mahindra Finance", "L&T Finance", "Sundaram Finance", "Aditya Birla Capital",
    "Piramal Capital", "Tata Capital", "HDB Financial", "Bajaj Housing Finance",
    
    # Mid-Market / Specialized
    "Poonawalla Fincorp", "Manappuram Finance", "IIFL Finance", "Five Star Business Finance",
    "CreditAccess Grameen", "Fusion Micro Finance", "Spandana Sphoorty",
    "Aavas Financiers", "Home First Finance", "Aptus Value Housing", "IndoStar Capital",
    
    # Emerging / Niche / Fintech
    "SBFC Finance", "Ugro Capital", "Capri Global", "Kogta Financial", "Varthana",
    "Lendingkart", "InCred Finance", "Clix Capital", "Hero FinCorp", "Godrej Capital",
    "Anand Rathi Global Finance", "Centrum Capital", "Mas Financial",
    
    # Housing Specific
    "LIC Housing Finance", "PNB Housing", "Can Fin Homes", "GIC Housing", "Repco Home Finance",
    
    # Cards / Other
    "SBI Card", "Samman Capital"
]

# 3. ACTION KEYWORDS
ACTIONS = [
    "investment", "deal", "funding", "stake", "partnership", "tie-up", "acquisition", "merger",
    "launch", "product", "appoint", "CEO", "MD", "resign", "regulatory", "RBI",
    "report", "outlook", "earnings", "profit", "quarter", "result", "Q3", "Q4", "NPA", "AUM"
]

# 4. CREDIBLE SOURCES WHITELIST
CREDIBLE_SOURCES = [
    "Economic Times", "The Economic Times", "Livemint", "Mint", 
    "Business Standard", "Moneycontrol", "Financial Express", 
    "CNBC-TV18", "CNBC", "The Hindu Business Line", "Bloomberg", 
    "Reuters", "NDTV Profit", "Business Today", "Inc42", 
    "Entrackr", "VCCircle", "Fortune India", "Forbes India", "VCCEdge"
]

# 5. STOCK NOISE FILTER (Aggressive Anti-Spam)
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
    "momentum", "trendline", "crossover", "technicals", "chart check", "golden cross",
    
    # Brokerage/Analyst Ratings (Purely transactional)
    "buy rating", "sell rating", "accumulate", "hold rating", "target price", 
    "target of", "upside", "downside", "stop loss", "brokerage view", "recommends",
    "brokerage radar", "analyst calls", "market voice",
    
    # Day Trading & Spam
    "stocks to watch", "stocks to buy", "market live", "live updates", "stock picks",
    "trading ideas", "morning trade", "opening bell", "closing bell", "market wrap",
    "pre-market", "after-market", "ahead of market", "market prediction", "trade setup",
    "hot stocks", "buzzing stocks", "options", "futures", "f&o", "derivative", 
    "call option", "put option", "bank nifty", "nifty prediction", "multibagger",
    
    # Corporate Actions (Noise)
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

# History File to prevent repeating news across days
HISTORY_FILE = "sent_news_history.txt"

def load_history():
    """Loads the set of previously sent URL hashes."""
    if not os.path.exists(HISTORY_FILE):
        return set()
    try:
        with open(HISTORY_FILE, "r") as f:
            return set(line.strip() for line in f.readlines())
    except:
        return set()

def save_history(new_hashes):
    """Appends new hashes to history file."""
    try:
        with open(HISTORY_FILE, "a") as f:
            for h in new_hashes:
                f.write(f"{h}\n")
    except:
        pass

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
    chunk_size = 8 # Reduced chunk size slightly to prevent query overflow
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
    text = re.split(r'\s-\s', text)[0]
    return re.sub(r'[^a-zA-Z0-9\s]', '', text).lower().strip()

def is_stock_noise(title):
    """Returns True if the title sounds like generic stock market noise."""
    clean_title = clean_text(title)
    
    for word in STOCK_NOISE_KEYWORDS:
        if word in clean_title:
            # Exception: Allow 'profit/result' news ONLY if it's purely fundamental
            # But strictly block if it mentions price action alongside earnings
            if any(x in clean_title for x in ["profit", "result", "earnings", "revenue", "quarter"]):
                bad_context = ["share", "stock", "target", "buy", "sell", "dividend", "split", "surges", "falls", "jumps"]
                if any(b in clean_title for b in bad_context):
                    return True 
                return False 
            return True
    return False

def is_credible_source(entry):
    if not hasattr(entry, 'source'): return False
    source_title = entry.source.get('title', '').strip()
    for credible in CREDIBLE_SOURCES:
        if credible.lower() in source_title.lower():
            return True
    return False

def get_word_set(text):
    cleaned = clean_text(text)
    return set(w for w in cleaned.split() if len(w) > 3)

def is_duplicate(new_title, existing_titles):
    """Jaccard Similarity Check (Set Overlap > 45%)."""
    new_words = get_word_set(new_title)
    if not new_words: return False 
    
    for existing in existing_titles:
        existing_words = get_word_set(existing)
        intersection = new_words.intersection(existing_words)
        union = new_words.union(existing_words)
        if len(union) == 0: continue
        if (len(intersection) / len(union)) > 0.45:
            return True
    return False

def send_email(html_body):
    if not EMAIL_USER or not EMAIL_PASS or not EMAIL_RECEIVER:
        print("Skipping email: Missing secrets.")
        return

    recipients = [email.strip() for email in EMAIL_RECEIVER.split(',')]

    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = ", ".join(recipients)
        msg['Subject'] = f"🚀 NBFC Sector Intel: Daily Briefing - {datetime.now().strftime('%d %b %Y')}"

        final_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Helvetica, Arial, sans-serif; background-color: #f4f6f8; margin: 0; padding: 0; color: #333; }}
                .container {{ max-width: 800px; margin: 30px auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); overflow: hidden; border: 1px solid #e1e4e8; }}
                .header {{ background: linear-gradient(135deg, #1a237e 0%, #283593 100%); color: #ffffff; padding: 25px; text-align: left; }}
                .header h1 {{ margin: 0; font-size: 22px; font-weight: 600; letter-spacing: 0.5px; }}
                .header p {{ margin: 5px 0 0 0; font-size: 13px; opacity: 0.8; }}
                .content {{ padding: 30px; line-height: 1.6; font-size: 14px; }}
                h3 {{ color: #1a237e; border-bottom: 2px solid #eaeff5; padding-bottom: 8px; margin-top: 25px; font-size: 16px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }}
                ul {{ padding-left: 15px; }}
                li {{ margin-bottom: 12px; list-style-type: none; border-left: 3px solid #e0e0e0; padding-left: 10px; }}
                li:hover {{ border-left-color: #1a237e; }}
                a {{ color: #2962ff; text-decoration: none; font-weight: 600; font-size: 15px; display: block; margin-bottom: 4px; }}
                a:hover {{ text-decoration: underline; }}
                .source-tag {{ font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: 0.5px; margin-right: 5px; }}
                .summary {{ display: block; color: #555; font-size: 13px; margin-top: 2px; line-height: 1.5; }}
                .footer {{ background-color: #f8f9fa; padding: 15px; text-align: center; font-size: 11px; color: #888; border-top: 1px solid #eee; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🇮🇳 NBFC Sector Intelligence</h1>
                    <p>{datetime.now().strftime('%A, %d %B %Y')} | Daily Executive Briefing</p>
                </div>
                <div class="content">
                    {html_body}
                </div>
                <div class="footer">
                    <p>Generated by <strong>Gemini 2.5 AI Bot</strong> | Automated Market Intelligence</p>
                    <p>Tracking {len(WATCHLIST_COMPANIES)} Key Entities</p>
                </div>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(final_html, 'html'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
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
    
    # Load history of already sent news
    sent_hashes = load_history()
    new_hashes_to_save = []
    
    rss_links = generate_rss_links()
    all_headlines = []
    seen_titles = [] 
    
    for link in rss_links:
        try:
            feed = feedparser.parse(link)
            if not feed.entries: continue
            
            for entry in feed.entries:
                title = entry.title
                url = entry.link
                
                # Create a unique hash for the URL to track history
                url_hash = hashlib.md5(url.encode()).hexdigest()
                
                # 1. HISTORY CHECK (Prevents Repeating News across days)
                if url_hash in sent_hashes: continue
                
                # 2. STRICT DATE CHECK
                if hasattr(entry, 'published') and not is_within_last_48_hours(entry.published):
                    continue 

                # 3. CREDIBLE SOURCE CHECK
                if not is_credible_source(entry): continue

                # 4. STOCK NOISE CHECK
                if is_stock_noise(title): continue

                # 5. DEDUPLICATION (Current Batch)
                if is_duplicate(title, seen_titles): continue
                
                source_name = entry.source.get('title', 'News')
                all_headlines.append(f"Title: {title} | Source: {source_name} | Link: {url}")
                seen_titles.append(title)
                new_hashes_to_save.append(url_hash)
                
        except Exception as e:
            print(f"Error fetching batch: {e}")
    
    final_headlines = all_headlines[:50] # Limit to top 50 relevant items

    if not final_headlines:
        print("No new significant updates found.")
        return

    print(f"Found {len(final_headlines)} relevant, unique headlines. Generating Report...")

    if not API_KEY:
        print("Error: API Key is missing.")
        return

    # --- THE REFINED PROMPT ---
    prompt_text = (
        "Role: You are a Senior NBFC Sector Analyst in India. You are briefing the Managing Director.\n"
        "Task: Review these headlines and synthesize a high-quality HTML Executive Briefing.\n\n"
        
        "**Strict Editorial Guidelines:**\n"
        "1. **Eliminate Noise:** Ignore minor updates. Only include strategic shifts, major deals (>50 Cr), RBI actions, or C-suite changes.\n"
        "2. **No Stock Talk:** Do NOT mention share prices, 'bull runs', or 'buy ratings'. Focus on BUSINESS FUNDAMENTALS.\n"
        "3. **Tone:** Professional, concise, analytical. Not journalistic.\n\n"
        
        "**HTML Formatting Rules:**\n"
        "1. Use `<h3>` with relevant emojis for Section Headers.\n"
        "2. Use `<ul>` and `<li>` for items.\n"
        "3. Format Item: `<span class='source-tag'>SOURCE</span> <a href='URL'>HEADLINE</a> <br><span class='summary'>👉 <b>Impact:</b> One sentence analysis of why this matters to the sector.</span>`\n"
        "4. If a category has no news, omit the section.\n\n"

        "**Categories to Cover:**\n"
        "1. 🏛 Regulatory & Compliance (RBI Circulars/Penalties)\n"
        "2. 💰 Fund Raising, M&A & Strategic Deals\n"
        "3. 📊 Quarterly Results & Asset Quality (NPA/AUM trends only)\n"
        "4. 👔 Leadership Changes (C-Suite only)\n"
        "5. 🚀 New Product Launches & Digital Initiatives\n\n"

        "**Input Headlines:**\n"
        + "\n".join(final_headlines)
    )

    success = False
    for model in MODELS:
        print(f"Synthesizing with: {model}...")
        result = call_gemini_with_retry(model, prompt_text)
        if result:
            try:
                text_output = result['candidates'][0]['content']['parts'][0]['text']
                text_output = text_output.replace("```html", "").replace("```", "")
                
                send_email(text_output)
                save_history(new_hashes_to_save) # Save successful items to history
                success = True
                break 
            except (KeyError, IndexError):
                continue

    if not success:
        print("CRITICAL: AI Model generation failed.")

if __name__ == "__main__":
    analyze_market_news()
