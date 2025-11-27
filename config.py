"""
Simple configuration file
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Your credentials
YOUR_EMAIL = os.getenv("YOUR_EMAIL", "24f1001647@ds.study.iitm.ac.in")
YOUR_SECRET = os.getenv("YOUR_SECRET", "jfhd8f79093ujfkjdf03ur73skgh")

# API keys
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# Settings
SERVER_PORT = 7860
QUIZ_DEADLINE = 180  # 3 minutes
HEADLESS_BROWSER = True
