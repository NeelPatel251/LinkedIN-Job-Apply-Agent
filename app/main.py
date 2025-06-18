from fastapi import FastAPI
from api.v1 import api_router

app = FastAPI(title="Job Apply Agent API")
app.include_router(api_router)
