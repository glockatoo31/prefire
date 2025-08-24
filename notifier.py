import httpx, os
from dotenv import load_dotenv

load_dotenv()                       # pulls secrets from .env in same folder

def push(message: str):
    httpx.post(
        "https://api.pushover.net/1/messages.json",
        data={
            "token":  os.getenv("PUSHOVER_APP_TOKEN"),
            "user":   os.getenv("PUSHOVER_USER_KEY"),
            "message": message
        },
        timeout=10
    ).raise_for_status()
