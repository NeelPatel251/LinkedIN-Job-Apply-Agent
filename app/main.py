import asyncio
from core.config import GEMINI_API_KEY, LINKEDIN_EMAIL, LINKEDIN_PASSWORD
from services.Entrypoints.navigator import LinkedInJobsNavigator

async def main():
    navigator = LinkedInJobsNavigator()
    await navigator.navigate_to_jobs()

if __name__ == "__main__":
    print("=== CONFIGURATION CHECK ===")
    print(f"Gemini API Key set: {'Yes' if GEMINI_API_KEY else 'No'}")
    print(f"LinkedIn Email set: {'Yes' if LINKEDIN_EMAIL else 'No'}")
    print(f"LinkedIn Password set: {'Yes' if LINKEDIN_PASSWORD else 'No'}")
    print("===========================\n")
    if not GEMINI_API_KEY:
        print("WARNING: GEMINI_API_KEY not set - will use fallback logic only!")
        print("The script will still work using rule-based navigation.\n")
    if not LINKEDIN_EMAIL or not LINKEDIN_PASSWORD:
        print("Please set your LINKEDIN_EMAIL and LINKEDIN_PASSWORD in the .env file!")
        exit(1)
    asyncio.run(main())
