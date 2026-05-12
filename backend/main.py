from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.api_routes import router


app = FastAPI(
    title="Digital System for Natural Disaster Risk Estimation",
    description=(
        "Academic prototype for environmental monitoring and disaster risk estimation. "
        "The API does not provide official warnings or exact disaster predictions."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
