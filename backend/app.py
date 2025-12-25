from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from service import run

app = FastAPI()

# allow Next.js dev server (localhost:3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Req(BaseModel):
    location: str
    item: str

@app.post("/api/analyze")
def analyze(req: Req):
    return run(req.location, req.item)

@app.get("/health")
def health():
    return {"ok": True}