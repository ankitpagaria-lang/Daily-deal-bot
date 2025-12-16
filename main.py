import feedparser
import os
import time
import requests
import smtplib
import urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
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
    # From BCG Report (Housing, Gold, MFI, Cards)
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
