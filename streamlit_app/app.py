# /streamlit_app/app.py
import streamlit as st
import requests

# Updated Orchestrator URL and endpoint
ORCHESTRATOR_URL = "http://127.0.0.1:8000/process_market_brief_query/" 

st.title("Multi-Agent Finance Assistant")

# Input for a general user query
user_query = st.text_input("Ask about Asia tech stocks (e.g., 'What are TSMC's latest results?', 'How is Samsung doing?', 'What is the market sentiment in Asia tech?'):", 
                           "What are TSMC's latest results?")

if st.button("Get Market Brief"):
    if user_query:
        payload = {"user_query": user_query} 
        try:
            st.markdown("---")
            with st.spinner("Fetching your market brief... This may take a moment."):
                response = requests.post(ORCHESTRATOR_URL, json=payload, timeout=60) # Increased timeout
                response.raise_for_status() 

                response_data = response.json()
                narrative = response_data.get("narrative")

                st.subheader("Market Brief:")
                if narrative:
                    st.write(narrative)
                else:
                    st.warning("Received no narrative. Full response:")
                    st.json(response_data)
        
        except requests.exceptions.Timeout:
            st.error("The request to the orchestrator timed out. The agents might be taking too long to respond.")
        except requests.exceptions.ConnectionError:
            st.error("Failed to connect to the Orchestrator. Is it running and accessible at port 8000?")
        except requests.exceptions.HTTPError as e:
            st.error(f"Error from Orchestrator: {e.response.status_code}")
            try:
                error_detail = e.response.json()
                st.json(error_detail) 
            except ValueError:
                st.text(e.response.text) 
        except Exception as e:
            st.error(f"An unexpected error occurred: {str(e)}")
    else:
        st.warning("Please enter your query.")