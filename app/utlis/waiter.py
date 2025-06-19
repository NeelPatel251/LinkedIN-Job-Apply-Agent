import asyncio
import os
from core.config import Temp_Path

RESUME_SIGNAL_FILE = Temp_Path

async def wait_for_user_resume(reason: str = "manual input required"):
    """
    Waits until user clicks 'Continue Agent' in the Chrome extension.
    A universal pause method for any step that requires user input.
    """
    print(f"\n⏸️ Waiting for user to continue: {reason}")
    print("Please complete the required action in your browser and click 'Continue Agent'.")

    while not os.path.exists(RESUME_SIGNAL_FILE):
        await asyncio.sleep(1)

    os.remove(RESUME_SIGNAL_FILE)
    print("✅ Resumed by user. Continuing automation...\n")
