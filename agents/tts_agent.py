# /agents/tts_agent.py
import os
import re
import httpx # Using httpx for async consistency with other agents
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import List, Generator, AsyncGenerator

load_dotenv()

app = FastAPI()

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
DEEPGRAM_TTS_URL = "https://api.deepgram.com/v1/speak?model=aura-hera-en" 

if not DEEPGRAM_API_KEY:
    print("WARNING: DEEPGRAM_API_KEY not found. TTS Agent will not function.")

TTS_HEADERS = {
    "Authorization": f"Token {DEEPGRAM_API_KEY}",
    "Content-Type": "application/json"
}

class TTSRequest(BaseModel):
    text: str

def segment_text_by_sentence(text: str) -> List[str]:
    sentence_boundaries = re.finditer(r'(?<=[.!?])\s+', text)
    boundaries_indices = [boundary.start() for boundary in sentence_boundaries]
    segments = []
    start = 0
    for boundary_index in boundaries_indices:
        segments.append(text[start:boundary_index + 1].strip())
        start = boundary_index + 1
    final_segment = text[start:].strip()
    if final_segment: 
        segments.append(final_segment)
    return [seg for seg in segments if seg]

async def stream_audio_segments(segments: List[str], client: httpx.AsyncClient) -> AsyncGenerator[bytes, None]:
    for segment_text in segments:
        if not segment_text: continue 
        payload = {"text": segment_text}
        try:
            print(f"TTS Agent: Requesting audio for segment: '{segment_text[:50]}...'")
            async with client.stream("POST", DEEPGRAM_TTS_URL, headers=TTS_HEADERS, json=payload, timeout=30.0) as r:
                r.raise_for_status() # Check for HTTP errors
                async for chunk in r.aiter_bytes(chunk_size=1024):
                    if chunk:
                        yield chunk
            print(f"TTS Agent: Streamed audio for segment: '{segment_text[:50]}...'")
        except httpx.HTTPStatusError as e:
            print(f"TTS Agent: HTTP error for segment '{segment_text[:30]}...': {e.response.status_code} - {e.response.text}")
        except Exception as e:
            print(f"TTS Agent: Error processing segment '{segment_text[:30]}...': {str(e)}")


@app.post("/synthesize_speech")
async def synthesize_speech_endpoint(request: TTSRequest):
    if not DEEPGRAM_API_KEY:
        raise HTTPException(status_code=503, detail="TTS service (Deepgram) not configured.")
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="No text provided for speech synthesis.")

    print(f"TTS Agent: Received text for synthesis (first 100 chars): '{request.text[:100]}'")
    segments = segment_text_by_sentence(request.text)
    if not segments:
        print("TTS Agent: Text resulted in no segments.")

        async def empty_generator():
            if False: yield # This makes it an async generator
        return StreamingResponse(empty_generator(), media_type="audio/mpeg")


    client = httpx.AsyncClient()
    async def audio_stream_generator():

        async with httpx.AsyncClient() as stream_client:
            async for chunk in stream_audio_segments(segments, stream_client):
                yield chunk
        print("TTS Agent: Finished streaming all audio segments.")

    return StreamingResponse(audio_stream_generator(), media_type="audio/mpeg")

