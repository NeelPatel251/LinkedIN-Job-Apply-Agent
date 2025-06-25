from fastapi import APIRouter
from models.profile import UserProfile
from core.config import User_Profile_path, GEMINI_API_KEY, LINKEDIN_EMAIL, LINKEDIN_PASSWORD
from services.Entrypoints.navigator import LinkedInJobsNavigator
from sse_starlette.sse import EventSourceResponse
import asyncio
import json
import sys
from core.config import Temp_Path

router = APIRouter()
print_queue = asyncio.Queue()


# ──────────────── 🔁 Save Profile ────────────────
@router.post("/set-profile")
async def set_profile(profile: UserProfile):
    print("Set Profile Called =====================")
    with open(User_Profile_path, "w") as f:
        json.dump(profile.dict(), f, indent=2)
    return {"status": "success", "msg": "Profile saved"}

# ──────────────── 📤 Print Interceptor ────────────────
class PrintInterceptor:
    def write(self, message):
        message = message.strip()
        if message:
            asyncio.create_task(print_queue.put(message))
    def flush(self):
        pass

sys.stdout = PrintInterceptor()
sys.stderr = PrintInterceptor()

@router.post("/continue-agent")
async def continue_agent():
    # Create the signal file
    with open(Temp_Path, "w") as f:
        f.write("RESUME")
    return {"status": "ok", "message": "Resume signal received"}

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
            try:
                try:
                    message = await asyncio.wait_for(print_queue.get(), timeout=10.0)
                    yield f"data: {message}\n\n"
                except asyncio.TimeoutError:
                    # Send keep-alive comment to prevent SSE timeout
                    yield ": keep-alive\n\n"
            except asyncio.CancelledError:
                break
            
    return EventSourceResponse(stream_logs())