import streamlit as st
import requests
from streamlit_mic_recorder import mic_recorder
import base64

ORCHESTRATOR_VOICE_URL = "http://127.0.0.1:8000/process_voice_query/"
ORCHESTRATOR_TEXT_URL = "http://127.0.0.1:8000/process_full_brief_query/"

st.title("Multi-Agent Finance Assistant - Chat Interface")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "pending_audio" not in st.session_state:
    st.session_state.pending_audio = None

if "message_id" not in st.session_state:
    st.session_state.message_id = 0

def add_message(role, content, audio_b64=None):
    message_data = {
        "role": role, 
        "content": content,
        "id": st.session_state.message_id,
        "audio": audio_b64
    }
    st.session_state.chat_history.append(message_data)
    st.session_state.message_id += 1

def display_chat_history():
    for message in st.session_state.chat_history:
        if message["role"] == "user":
            with st.chat_message("user"):
                st.write(message["content"])
        else:
            with st.chat_message("assistant"):
                st.write(message["content"])
                
                # Display audio player if available
                if message.get("audio"):
                    try:
                        audio_bytes = base64.b64decode(message["audio"])
                        b64_encoded = base64.b64encode(audio_bytes).decode()
                        
                        # Create persistent audio player
                        st.markdown("🔊 **Audio Response:**")
                        audio_html = f"""
                            <audio controls style="width: 100%;">
                                <source src="data:audio/mpeg;base64,{b64_encoded}" type="audio/mpeg">
                                Your browser does not support the audio element.
                            </audio>
                        """
                        st.markdown(audio_html, unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"Error loading audio: {str(e)}")

def process_query(query_text):
    chat_history_for_api = []
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            chat_history_for_api.append({"role": "user", "content": msg["content"]})
        else:
            chat_history_for_api.append({"role": "assistant", "content": msg["content"]})
    
    payload = {
        "user_query": query_text,
        "chat_history": chat_history_for_api
    }
    
    try:
        with st.spinner("Processing query and generating response..."):
            response = requests.post(ORCHESTRATOR_TEXT_URL, json=payload, timeout=180)
            response.raise_for_status()
            response_data = response.json()
            
            narrative = response_data.get("narrative_text", "No response generated.")
            audio_b64 = response_data.get("audio_base64")
            
            # Add message with audio data
            add_message("assistant", narrative, audio_b64)
                    
    except Exception as e:
        st.error(f"Error processing query: {str(e)}")

# Display chat history
display_chat_history()

# Input section
col1, col2 = st.columns([3, 1])

with col1:
    user_input = st.chat_input("Type your message here...")

with col2:
    audio_data = mic_recorder(
        start_prompt="🎤", 
        stop_prompt="⏹️", 
        just_once=True, 
        key=f'mic_recorder_{len(st.session_state.chat_history)}'
    )

# Handle text input
if user_input:
    add_message("user", user_input)
    with st.spinner("Generating response..."):
        process_query(user_input)
    st.rerun()

# Handle voice input
if audio_data and audio_data.get("bytes"):
    st.audio(audio_data["bytes"], format="audio/wav")
    
    files_for_stt = {'audio_file': ('recorded_query.wav', audio_data["bytes"], 'audio/wav')}
    try:
        with st.spinner("Transcribing audio..."):
            stt_response = requests.post("http://127.0.0.1:8005/transcribe_audio", files=files_for_stt, timeout=45)
            stt_response.raise_for_status()
            stt_data = stt_response.json()
            transcribed_query = stt_data.get("transcribed_text", "Could not transcribe.")
            
            if transcribed_query and transcribed_query.strip():
                add_message("user", transcribed_query)
                with st.spinner("Generating response..."):
                    process_query(transcribed_query)
                st.rerun()
            else:
                st.error("Could not transcribe the audio. Please try again.")
                
    except Exception as e:
        st.error(f"Error processing voice query: {str(e)}")

# Sidebar controls
if st.sidebar.button("Clear Chat History"):
    st.session_state.chat_history = []
    st.session_state.message_id = 0
    st.rerun()

# Show current status
st.sidebar.markdown(f"**Messages:** {len(st.session_state.chat_history)}")
if st.session_state.chat_history:
    audio_count = sum(1 for msg in st.session_state.chat_history if msg.get("audio"))
    st.sidebar.markdown(f"**Audio responses:** {audio_count}")