from fastapi import FastAPI
from api.v1 import api_router
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title="Job Apply Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or restrict to extension origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(api_router)
