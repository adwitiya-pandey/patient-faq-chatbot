"""Streamlit entrypoint for Northfield Hospital FAQ chatbot."""

import streamlit as st

from faq_bot.chat import handle_turn
from faq_bot.config import Config, load_config
from faq_bot.cost import Totals
from faq_bot.messages import DISCLAIMER

# Page configuration
st.set_page_config(
    page_title="Patient FAQ Assistant", page_icon="🏥", layout="centered"
)

# Attempt loading configuration safely
try:
    config: Config = load_config()
except ValueError:
    st.error("Please set GEMINI_API_KEY in your environment or .env file.")
    st.stop()

# Initialize session state for conversation history and usage totals
if "history" not in st.session_state:
    st.session_state.history = []
if "totals" not in st.session_state:
    st.session_state.totals = Totals()

# Sidebar: Token usage, estimated cost, and controls
with st.sidebar:
    st.header("Session Usage (Estimate)")
    st.caption("Pricing is an estimate based on configured token rates.")
    st.text(f"Model: {config.gemini_model}")
    st.metric("LLM Calls", st.session_state.totals.llm_calls)
    st.metric("Input Tokens", f"{st.session_state.totals.input_tokens:,}")
    st.metric("Output Tokens", f"{st.session_state.totals.output_tokens:,}")
    st.metric("Estimated Cost", f"${st.session_state.totals.total_cost_usd:.4f}")

    if st.button("Clear Chat", use_container_width=True):
        st.session_state.history = []
        st.session_state.totals.reset()
        st.rerun()

# Main conversation UI
st.title(f"{config.hospital_name} Patient FAQ")
st.write(
    "Ask questions about appointments, insurance, surgery preparation, and pharmacy logistics."
)
st.caption(DISCLAIMER)

# Render conversation history
for item in st.session_state.history:
    with st.chat_message(item["role"]):
        cat = item.get("category", "")
        if cat == "emergency":
            st.error(item["content"])
        elif cat == "clinical_advice":
            st.info(item["content"])
        else:
            st.write(item["content"])

# Chat input prompt
user_text = st.chat_input("Ask a question about hospital logistics...")
if user_text:
    # Render user message immediately
    with st.chat_message("user"):
        st.write(user_text)

    # Process turn with spinner
    with st.spinner("Processing..."):
        result = handle_turn(
            history=st.session_state.history,
            text=user_text,
            config=config,
        )

        # Update running session totals
        st.session_state.totals.add_call(
            result.usage,
            price_in=config.price_input_per_m,
            price_out=config.price_output_per_m,
        )

        # Append messages to session state
        st.session_state.history.append(
            {
                "role": "user",
                "content": user_text,
                "category": "user",
                "blocked": False,
            }
        )
        st.session_state.history.append(
            {
                "role": "assistant",
                "content": result.text,
                "category": result.category,
                "blocked": result.blocked,
            }
        )

    # Render assistant response and update sidebar
    st.rerun()
