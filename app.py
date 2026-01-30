# """
# Streamlit application entry point.

# This web app file handles:
# - user interaction
# - maintaining session state
# - running the agent loop

# """

import streamlit as st
import pandas as pd
from data_loader import load_dataset, summarize_dataset
from ai_analysis import (
    parse_intent,
    ask_clarification,
    create_dashboard_plan,
    revise_dashboard_plan,
    needs_clarification,
    wants_new_dashboard
)
from dashboard import render_dashboard
from state import AnalystState

st.set_page_config(layout="wide")
st.title("🤖 AI Dashboard Analyst")

# Initialize state
if "state" not in st.session_state:
    st.session_state.state = AnalystState()
if "ai_output" not in st.session_state:
    st.session_state.ai_output = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "df" not in st.session_state:
    st.session_state.df = None


state = st.session_state.state

if not hasattr(state, "awaiting_clarification"):
    state.awaiting_clarification = False

st.sidebar.header("📂 Upload Dataset")
file = st.sidebar.file_uploader("Upload CSV or Excel", type=["csv", "xlsx"])

if file:
    df = load_dataset(file)
    st.session_state.df = df
    state.df = df
    st.sidebar.success(f"Successfully loaded dataset!")
else:
    st.info("Please upload a dataset to begin!")
    st.stop()

tabs = st.tabs(["Data", "Dashboard", "Insights"])

with tabs[0]: # Data Tab
    st.subheader("Dataset Preview")
    st.dataframe(df)

with tabs[1]:  # Dashboard tab

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Scrollable chat container 
    chat_height = 200
    with st.container():
        st.markdown("### Chat History")
        with st.container(height=chat_height):
            for msg in st.session_state.messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

    #  Chat input
    user_msg = st.chat_input("Ask me about your data...")
    if user_msg:
        st.session_state.messages.append({"role": "user", "content": user_msg})
        with st.chat_message("user"):
            st.markdown(user_msg)

        intent = parse_intent(user_msg, state)

        with st.chat_message("assistant"):

            # Case 1: awaiting clarification
            if state.awaiting_clarification:
                state.user_goal = user_msg
                state.awaiting_clarification = False
                st.markdown("✅ Got it! Let me design the dashboard.")
                state.dashboard_plan = create_dashboard_plan(state.df, state)
                st.session_state.ai_output = state.dashboard_plan

            # Case 2: first analysis or new request
            elif intent == "analyze":
                if state.awaiting_clarification:
                    state.user_goal = user_msg
                    state.awaiting_clarification = False
                    st.markdown("✅ Got it! Generating dashboard / insights...")
                    state.dashboard_plan = create_dashboard_plan(state.df, state)
                    st.session_state.ai_output = state.dashboard_plan

                elif needs_clarification(user_msg):
                    question = ask_clarification(state, user_msg, state.df)
                    state.awaiting_clarification = True
                    st.markdown(f"❓ {question}")

                else:
                    # question is specific - create or revise
                    if state.dashboard_plan and not wants_new_dashboard(user_msg):
                        st.markdown("🔁 Updating the existing dashboard...")
                        state.dashboard_plan = revise_dashboard_plan(state, user_msg)
                    else:
                        st.markdown("📊 Designing dashboard based on your request...")
                        state.dashboard_plan = create_dashboard_plan(state.df, state)

                    st.session_state.ai_output = state.dashboard_plan

            # Case 4: render
            elif intent == "render" and state.dashboard_plan:
                st.markdown("Here’s the current dashboard.")

            else:
                st.markdown("🤔 I’m not sure what to do yet. Can you clarify?")

        # Save assistant response to session state
        st.session_state.messages.append(
            {"role": "assistant", "content": st.session_state.messages[-1]["content"]}
        )

    # Render dashboard if available 
    if state.dashboard_plan:
        st.divider()
        render_dashboard(state.df, state.dashboard_plan)


with tabs[2]: # Insights tab
    if state.dashboard_plan and "analysis_summary" in state.dashboard_plan:
        summary = state.dashboard_plan["analysis_summary"]

        st.subheader("🧠 Analyst Reasoning")

        #st.markdown(f"**Your question:** {summary['user_question']}")
        st.markdown(f"**Approach:** {summary['approach']}")

        st.markdown("**Why this dashboard works:**")
        for point in summary["reasoning"]:
            st.markdown(f"- {point}")
    else:
        st.info("Insights will appear after analysis.")


