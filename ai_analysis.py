"""
LLM-powered logic

This file contains the instructions for the LLM including:
- generating clarification questions
- parsing the intent
- planning dashboard components
- revising the dashboard as per requirement

"""
from typing import List, Dict, Any
from state import AnalystState

def parse_intent(user_msg: str, state: AnalystState) -> str:
    """
    Determine the user's intent based on their message and current state.

    Expected intents:
    - "clarify"
    - "analyze"
    - "revise"
    - "render"
    """
    pass


def ask_clarification(state: AnalystState) -> str:
    """
    Generate a clarification question to resolve the most important
    uncertainty blocking progress.
    """
    pass


def create_dashboard_plan(state: AnalystState) -> Dict[str, Any]:
    """
    Create a structured dashboard plan based on the dataset summary,
    user goal, and current assumptions.
    """
    pass


def revise_dashboard_plan(
    state: AnalystState, user_msg: str
) -> Dict[str, Any]:
    """
    Modify an existing dashboard plan based on user feedback.
    """
    pass