import feedparser
import os
import time
import requests
import smtplib
import urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dateutil import parser # Requires: pip install python-dateutil

# --- CONFIGURATION ---

# 1. GENERAL SECTOR KEYWORDS
GENERAL_KEYWORDS = [
    "NBFC", "Non-Banking Financial Company", "Shadow Bank", "Fintech Lender", 
    "Microfinance", "Housing Finance", "Gold Loan"
]

# 2. WATCHLIST (User List + Extracted from BCG Report)
WATCHLIST_COMPANIES = [
    # User Specific
    "SBFC Finance", "Kogta Financial", "Bajaj Finance", "HDB Financial", "Tata Capital", 
    "Shriram Finance", "Sundaram Finance", "Poonawalla Fincorp", "Godrej Capital", 
    "Hero FinCorp", "Anand Rathi", "Piramal Capital", "Aditya Birla Capital", 
    "Cholamandalam Investment", "Mahindra Finance", "L&T Finance", "IIFL Finance", 
    "Capri Global", "Ugro Capital", "Clix Capital", "APC", 
    # From BCG Report
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

# Priority Models
MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite", 
    "gemini-2.0-flash",
    "gemini-1.5-flash"
]

# API Keys & Secrets
API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASS")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER")

def generate_rss_links():
    """Generates multiple RSS links to ensure we cover ALL companies."""
    links = []
    
    # Batch 1: General Sector News (Last 48h)
    # FIX: Join strings outside of f-string to prevent SyntaxError
    gen_keys_str = ' OR '.join(GENERAL_KEYWORDS)
    act_keys_str = ' OR '.join(ACTIONS)
    general_query = f"({gen_keys_str}) AND ({act_keys_str}) AND India when:2d"
    
    encoded_gen = urllib.parse.quote(general_query)
    links.append(f"https://news.google.com/rss/search?q={encoded_gen}&hl=en-IN&gl=IN&ceid=IN:en")

    # Batch 2 & 3: Specific Company News
    chunk_size = 10
    for i in range(0, len(WATCHLIST_COMPANIES), chunk_size):
        chunk = WATCHLIST_COMPANIES[i:i + chunk_size]
        
        # FIX: Join strings outside of f-string to prevent SyntaxError
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
        
        # Check against UTC now
        delta = datetime.utcnow() - pub_date
        return delta.days <= 2
    except:
        return True # Keep if parsing fails to be safe

def send_email(html_body):
    if not EMAIL_USER or not EMAIL_PASS or not EMAIL_RECEIVER:
        print("Skipping email: Missing secrets.")
        return

    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = EMAIL_RECEIVER
        msg['Subject'] = f"🚀 MD's Briefing: NBFC & Banking Pulse - {datetime.now().strftime('%d %b %Y')}"

        # --- PROFESSIONAL CSS STYLING ---
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
        server.send_message(msg)
        server.quit()
        print(f"✅ Executive Briefing sent to {EMAIL_RECEIVER}!")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

def analyze_market_news():
    print(f"Scanning news (Past 48H) for {len(WATCHLIST_COMPANIES)} NBFCs...")
    
    rss_links = generate_rss_links()
    all_headlines = []
    seen_titles = set()

    # Fetch from all generated RSS links
    for link in rss_links:
        try:
            feed = feedparser.parse(link)
            if not feed.entries:
                continue
            for entry in feed.entries:
                if entry.title not in seen_titles:
                    # STRICT DATE CHECK
                    if hasattr(entry, 'published'):
                        if not is_within_last_48_hours(entry.published):
                            continue # Skip old news
                            
                    # We send Title + Link to AI so it can format the HTML link
                    all_headlines.append(f"Title: {entry.title} | Link: {entry.link}")
                    seen_titles.add(entry.title)
        except Exception as e:
            print(f"Error fetching batch: {e}")
    
    # Limit to top 60 to allow enough room for analysis
    final_headlines = all_headlines[:60]

    if not final_headlines:
        print("No news found in the last 48 hours for the watchlist.")
        return

    print(f"Found {len(final_headlines)} unique headlines (Last 48h). Generating Report...")

    if not API_KEY:
        print("Error: API Key is missing.")
        return

    # --- THE PROMPT ---
    prompt_text = (
        "You are a Market Intelligence Analyst. Review these news headlines (from the last 48 hours) "
        "and create a beautiful, professional HTML daily briefing for the MD. "
        "Focus strictly on the Indian NBFC/Banking sector.\n\n"
        
        "**Output Guidelines (STRICT HTML):**\n"
        "1. Return **ONLY valid HTML** content (start with `<h3>`). Do not use <html> or <body> tags (I have a wrapper).\n"
        "2. **Headers:** Use `<h3>` tags with Emojis for sections.\n"
        "3. **Lists:** Use `<ul>` lists. Each item should be `<li>`.\n"
        "4. **Links:** The headline MUST be a clickable link: `<a href='URL'>Headline Text</a>`.\n"
        "5. **Summary:** Add a `<span class='summary'>👉 Summary: [One sentence impact analysis]</span>` inside the `<li>`.\n"
        "6. **No News:** If a category is empty, write `<i>No significant updates in the last 48h.</i>`.\n\n"

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

    # --- THE DIRECT API LOOP ---
    success = False
    
    for model in MODELS:
        print(f"Attempting direct connection to: {model}...")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={API_KEY}"
        headers = {'Content-Type': 'application/json'}
        data = {"contents": [{"parts": [{"text": prompt_text}]}]}

        try:
            response = requests.post(url, headers=headers, json=data, timeout=120)
            
            if response.status_code == 200:
                result = response.json()
                try:
                    text_output = result['candidates'][0]['content']['parts'][0]['text']
                    text_output = text_output.replace("```html", "").replace("```", "")
                    
                    print("\n" + "="*30)
                    print(f"SUCCESS with {model}")
                    print("="*30)
                    
                    send_email(text_output)
                    success = True
                    break 
                except (KeyError, IndexError):
                    print(f"Model {model} returned 200 OK but unreadable format.")
                    continue
            elif response.status_code == 429:
                print(f"Model {model} is busy (Quota Exceeded). Trying next...")
                time.sleep(1)
            elif response.status_code == 404:
                print(f"Model {model} not found. Trying next...")
            else:
                print(f"Model {model} failed with Status {response.status_code}")

        except Exception as e:
            print(f"Connection error with {model}: {e}")

    if not success:
        print("CRITICAL: All models failed. No email sent.")

if __name__ == "__main__":
    analyze_market_news()
