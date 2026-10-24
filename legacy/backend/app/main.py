"""AquaSense AI FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import forecast, simulate, wells, xai

app = FastAPI(title="AquaSense AI Backend API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(wells.router)
app.include_router(forecast.router)
app.include_router(xai.router)
app.include_router(simulate.router)


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "online", "system": "AquaSense AI API"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
