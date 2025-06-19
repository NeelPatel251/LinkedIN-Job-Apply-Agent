import os
from dotenv import load_dotenv

load_dotenv()  # Load .env values

# --- API Keys ---
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")

# --- LinkedIn Credentials ---
LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASS")

# --- Job Search Preferences ---
JOB_TITLE = "Data Scientist"
JOB_LOCATION = "Bangalore, India"

# --- Misc Settings ---
PHONE_NUMNER = "7046281329"
RESUME_PATH = "/home/neel/Desktop/Job Apply Agent/resume college 1.pdf"

# --- Base URLs ---
TARGET_URL = "https://www.linkedin.com"
User_Profile_path = "/home/neel/Desktop/Job Apply Agent/user_profile.json"
Temp_Path = "/home/neel/Desktop/Job Apply Agent/app/continue_signal.txt"