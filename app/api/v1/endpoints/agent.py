from fastapi import APIRouter
from models.profile import UserProfile
from core.config import User_Profile_path, GEMINI_API_KEY, LINKEDIN_EMAIL, LINKEDIN_PASSWORD
from services.Entrypoints.navigator import LinkedInJobsNavigator
from sse_starlette.sse import EventSourceResponse
import asyncio
import json
import sys

router = APIRouter()
print_buffer = []

# ──────────────── 🔁 Save Profile ────────────────
@router.post("/set-profile")
async def set_profile(profile: UserProfile):
    with open(User_Profile_path, "w") as f:
        json.dump(profile.dict(), f, indent=2)
    return {"status": "success", "msg": "Profile saved"}

# ──────────────── 📤 Print Interceptor ────────────────
class PrintInterceptor:
    def write(self, message):
        if message.strip():
            print_buffer.append(message.strip())
    def flush(self):
        pass

# sys.stdout = PrintInterceptor()

# ──────────────── ▶️ Run Agent ────────────────
@router.get("/start-agent")
async def start_agent():
    async def run():
        print("=== CONFIGURATION CHECK ===")
        print(f"Gemini API Key set: {'Yes' if GEMINI_API_KEY else 'No'}")
        print(f"LinkedIn Email set: {'Yes' if LINKEDIN_EMAIL else 'No'}")
        print(f"LinkedIn Password set: {'Yes' if LINKEDIN_PASSWORD else 'No'}")
        print("===========================\n")

        if not GEMINI_API_KEY:
            print("WARNING: GEMINI_API_KEY not set!")
        if not LINKEDIN_EMAIL or not LINKEDIN_PASSWORD:
            print("Missing LinkedIn credentials! Aborting.")
            return

        try:
            navigator = LinkedInJobsNavigator()
            await navigator.navigate_to_jobs()
            print("✅ Agent finished execution.")
        except Exception as e:
            print(f"❌ Exception: {e}")

    asyncio.create_task(run())

    async def stream_logs():
        while True:
            if print_buffer:
                yield f"data: {print_buffer.pop(0)}\n\n"
            await asyncio.sleep(0.5)

    return EventSourceResponse(stream_logs())