import os

from dotenv import load_dotenv
from fastapi import Header, HTTPException

# find_dotenv() (load_dotenv() ke andar) parent directories mein upar
# tak dhoondta hai .env -- isi wajah se ye chalega chahe uvicorn
# service ke apne APP/ folder se start ho ya repo root se.
load_dotenv()

API_KEY = os.environ.get("API_KEY", "")


async def require_api_key(x_api_key: str = Header(default="")):
    if not API_KEY or API_KEY == "changeme_generate_a_real_key":
        raise HTTPException(
            status_code=500,
            detail="API_KEY is not configured on the server -- set a real value in .env before exposing this endpoint.",
        )
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key header.")
