# /agents/stt_agent.py
import os
import uuid
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from deepgram import (
    DeepgramClient,
    PrerecordedOptions,
    FileSource
)
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
deepgram_client = None

if not DEEPGRAM_API_KEY:
    print("WARNING: DEEPGRAM_API_KEY not found in environment. STT Agent will not function.")
else:
    try:
        deepgram_client = DeepgramClient(api_key=DEEPGRAM_API_KEY) # Explicitly pass key
        print("Deepgram client initialized successfully for STT Agent.")
    except Exception as e:
        print(f"Error initializing Deepgram client: {e}")
        deepgram_client = None


class TranscriptionResponse(BaseModel):
    transcribed_text: str
    # You can add more fields from Deepgram's response if needed, like confidence etc.

@app.post("/transcribe_audio", response_model=TranscriptionResponse)
async def transcribe_audio_file(audio_file: UploadFile = File(...)):
    if not deepgram_client:
        raise HTTPException(status_code=503, detail="STT service (Deepgram) not available or not initialized.")

    if not audio_file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an audio file.")

    temp_file_path = None
    try:
        audio_bytes = await audio_file.read()
        
        payload: FileSource = {
            "buffer": audio_bytes,
        }

        options = PrerecordedOptions(
            smart_format=True, # Automatically detect audio format
            model="nova-2",    # Or your preferred model, "nova-2" is good
            language="en-US",  # Specify language
        )
        
        print(f"STT Agent: Sending audio (approx {len(audio_bytes)} bytes) to Deepgram for transcription.")
        dg_response = deepgram_client.listen.prerecorded.v("1").transcribe_file(payload, options, timeout=30)
        transcript = ""
        if dg_response and dg_response.results and dg_response.results.channels:
            transcript = dg_response.results.channels[0].alternatives[0].transcript
            print(f"STT Agent: Transcription successful. Transcript: '{transcript}'")
        else:
            print(f"STT Agent: Transcription failed or no transcript found in response. Response: {dg_response.to_json(indent=2) if dg_response else 'No response'}")
            raise HTTPException(status_code=500, detail="Transcription failed or no transcript found.")

        if not transcript.strip(): # If transcript is empty or just whitespace
            print("STT Agent: Received empty transcript from Deepgram.")
            return TranscriptionResponse(transcribed_text="") # Or an error

        return TranscriptionResponse(transcribed_text=transcript)

    except HTTPException as e: # Re-raise HTTPExceptions
        raise e
    except Exception as e:
        error_type = type(e).__name__
        error_details = str(e)
        print(f"STT Agent: Error during transcription process: {error_type} - {error_details}")
        raise HTTPException(status_code=500, detail=f"STT Error ({error_type}): {error_details}")
    finally:
        # Clean up: No temporary file was created if using buffer directly
        pass
