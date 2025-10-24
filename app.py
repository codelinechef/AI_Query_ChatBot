from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import asyncio
import assistant

app = FastAPI(title="RAG Gemini Chatbot")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Init Chroma on boot
@app.on_event("startup")
def startup_event():
    # your assistant module should expose init_chroma(rebuild=False)
    if hasattr(assistant, "init_chroma"):
        assistant.init_chroma(rebuild=False)

# POST /api/query — uses assistant.query_api(question)
@app.post("/api/query")
async def api_query(req: Request):
    try:
        payload = await req.json()
        question = (payload.get("question") or "").strip()
        if not question:
            return JSONResponse({"error": "Question is required."}, status_code=400)

        result = assistant.query_api(question)
        return JSONResponse({
            "answer": result.get("gemini_answer"),
            "matches": result.get("matches", [])
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# Alias for frontend
@app.post("/api/chat")
async def api_chat(req: Request):
    return await api_query(req)

# Streaming endpoint (SSE). If assistant has stream_query, use it; else simulate.
@app.post("/api/chat/stream")
async def api_chat_stream(req: Request):
    payload = await req.json()
    question = (payload.get("question") or "").strip()
    if not question:
        return JSONResponse({"error": "Question is required."}, status_code=400)

    async def gen():
        # If you implement assistant.stream_query(question) yielding tokens/chunks, plug in here.
        if hasattr(assistant, "stream_query"):
            async for chunk in assistant.stream_query(question):
                yield f"data:{chunk}\n\n"
            yield "data:[DONE]\n\n"
            return

        # Fallback: non-streaming result split into chunks.
        try:
            result = assistant.query_api(question)
            text = result.get("gemini_answer") or ""
            # naive chunking
            CHUNK = 140
            for i in range(0, len(text), CHUNK):
                await asyncio.sleep(0.02)  # tiny pacing
                yield f"data:{text[i:i+CHUNK]}\n\n"
            yield "data:[DONE]\n\n"
        except Exception as e:
            yield f"data:⚠️ {str(e)}\n\n"
            yield "data:[DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")

# Static frontend
app.mount("/images", StaticFiles(directory="images"), name="images")
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
