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

    # Create a temporary file to store the uploaded audio
    # This is because some SDK methods might prefer file paths,
    # or it's a reliable way to handle the buffer.
    temp_file_path = None
    try:
        # Read the file content (audio_bytes)
        audio_bytes = await audio_file.read()
        
        # Prepare the payload for Deepgram
        payload: FileSource = {
            "buffer": audio_bytes,
            # "mimetype": audio_file.content_type # Optionally provide mimetype
        }

        # Configure Deepgram options
        # The summarize option might not be what we want for a simple query.
        # Let's focus on accurate transcription.
        options = PrerecordedOptions(
            smart_format=True, # Automatically detect audio format
            model="nova-2",    # Or your preferred model, "nova-2" is good
            language="en-US",  # Specify language
            # summarize="v2", # Remove summarize if you only want transcription for the query
            # punctuate=True, # Add punctuation
        )
        
        print(f"STT Agent: Sending audio (approx {len(audio_bytes)} bytes) to Deepgram for transcription.")
        
        # Call Deepgram's transcribe_file method
        # Using listen.rest.v("1").transcribe_file as per your example structure
        # (Adjust if using a different SDK version or method call signature)
        # The Deepgram SDK has evolved. The `deepgram.listen.prerecorded.v("1").transcribe_file` is common.
        # Or if `deepgram.listen.rest` is the new way for your SDK version:
        
        # Assuming `deepgram_client.listen.prerecorded.v("1").transcribe_file`
        # response = deepgram_client.listen.prerecorded.v("1").transcribe_file(payload, options, timeout=30)

        # Using the example structure you provided: deepgram.listen.rest.v("1").transcribe_file
        # This might vary slightly based on the exact version of the `deepgram-sdk` you installed.
        # Let's stick to a common known good one if yours gives trouble:
        # `deepgram_client.listen.prerecorded.v("1")`

        # Using `.transcribe_file(payload, options)` as per SDK examples if payload is FileSource with buffer
        dg_response = deepgram_client.listen.prerecorded.v("1").transcribe_file(payload, options, timeout=30)


        # Extract the transcript
        # The structure of dg_response.to_json() needs to be inspected.
        # Typically, transcript is under results.channels[0].alternatives[0].transcript
        # Let's parse the JSON as per your example usage if `file_response.to_json()` is common for your SDK version.
        # If using `deepgram-sdk>=3.0`, the response object is different.
        
        # For `deepgram-sdk` version around 3.x:
        transcript = ""
        if dg_response and dg_response.results and dg_response.results.channels:
            transcript = dg_response.results.channels[0].alternatives[0].transcript
            print(f"STT Agent: Transcription successful. Transcript: '{transcript}'")
        else:
            print(f"STT Agent: Transcription failed or no transcript found in response. Response: {dg_response.to_json(indent=2) if dg_response else 'No response'}")
            raise HTTPException(status_code=500, detail="Transcription failed or no transcript found.")

        if not transcript.strip(): # If transcript is empty or just whitespace
            print("STT Agent: Received empty transcript from Deepgram.")
            # Consider this an error or handle as "no query recognized"
            # raise HTTPException(status_code=400, detail="No speech detected or transcribed.")
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

# To run this agent:
# cd agents
# uvicorn stt_agent:app --reload --port 8005