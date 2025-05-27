# /streamlit_app/app.py
import streamlit as st
import requests
from streamlit_mic_recorder import mic_recorder # Import the component

# Orchestrator URL needs an endpoint that can handle audio eventually
# For now, let's assume we will create a new endpoint or adapt one.
# Let's target a new endpoint in orchestrator: /process_voice_query/
ORCHESTRATOR_VOICE_URL = "http://127.0.0.1:8000/process_voice_query/"
ORCHESTRATOR_TEXT_URL = "http://127.0.0.1:8000/process_full_brief_query/" # Existing text endpoint

st.title("Multi-Agent Finance Assistant v3 (Voice Enabled)")

# --- Option for Text Input (Keep for debugging/fallback) ---
st.subheader("Option 1: Text Input")
user_text_query = st.text_input(
    "Type your query (e.g., 'What's the latest on Apple?'):",
    key="text_query_input"
)

if st.button("Get Brief from Text", key="text_submit"):
    if user_text_query:
        payload = {"user_query": user_text_query}
        try:
            st.markdown("---")
            with st.spinner("Processing text query..."):
                response = requests.post(ORCHESTRATOR_TEXT_URL, json=payload, timeout=120)
                response.raise_for_status()
                response_data = response.json()
                narrative = response_data.get("narrative")
                st.subheader("Market Brief:")
                if narrative:
                    st.write(narrative) # Later this will be TTS
                else:
                    st.json(response_data)
        except Exception as e:
            st.error(f"Error processing text query: {str(e)}")
    else:
        st.warning("Please enter a text query.")

st.divider()

# --- Option for Voice Input ---
st.subheader("Option 2: Voice Input")
st.write("Click the 'Start Recording' button and speak your query.")

# Use the mic_recorder component
# It returns audio bytes when recording is stopped or a specific format.
# We need to check its output format; `output_format="wav"` is good.
# `key` is important for Streamlit to manage widget state.
audio_data = mic_recorder(
    start_prompt="Start Recording 🎤",
    stop_prompt="Stop Recording ⏹️",
    just_once=True, # Record once per button interaction cycle
    use_container_width=False,
    # format="wav", # Let's try default first, usually gives wav bytes
    # callback=None, # No callback needed if we process after it returns
    key='mic_recorder'
)

if audio_data and audio_data.get("bytes"):
    st.audio(audio_data["bytes"], format="audio/wav") # Playback the recorded audio for user confirmation
    st.write("Processing your voice query...")

    # Send the audio bytes to the Orchestrator
    # The orchestrator will then forward to STT Agent
    files = {'audio_file': ('recorded_query.wav', audio_data["bytes"], 'audio/wav')}
    
    try:
        with st.spinner("Transcribing and fetching brief... This may take a moment."):
            # Assuming orchestrator will have an endpoint like /process_voice_query/
            # This endpoint will handle the audio file and then proceed like process_full_brief_query
            response = requests.post(ORCHESTRATOR_VOICE_URL, files=files, timeout=150) # Increased timeout
            response.raise_for_status()
            response_data = response.json()
            narrative = response_data.get("narrative") # Orchestrator should return the final narrative

            st.subheader("Market Brief (from voice):")
            if narrative:
                st.write(narrative) # Later, this will be TTS output
                # TODO: Add TTS playback here
            else:
                st.warning("Received no narrative from voice query. Full response:")
                st.json(response_data)
    
    except requests.exceptions.Timeout:
        st.error("The request timed out. Voice processing might be taking too long.")
    except requests.exceptions.ConnectionError:
        st.error("Failed to connect to the Orchestrator for voice processing.")
    except requests.exceptions.HTTPError as e:
        error_message = f"Error from Orchestrator (voice query): {e.response.status_code}"
        try:
            error_detail = e.response.json().get("detail", e.response.text)
            error_message += f" - {error_detail}"
        except ValueError:
            error_message += f" - {e.response.text}"
        st.error(error_message)
    except Exception as e:
        st.error(f"An unexpected error occurred during voice query processing: {str(e)}")