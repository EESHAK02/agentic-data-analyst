import pandas as pd
import pytest
from state import AnalystState
from ai_analysis import decide_response_mode, get_clarification_question, analyst_explain, create_dashboard_plan

def sample_df():
    data = {
        "Age": [22, 38, 26, 35],
        "Fare": [7.25, 71.83, 7.92, 53.1],
        "Survived": [0, 1, 1, 1],
        "PassengerId": [1, 2, 3, 4],
        "Sex": ["male", "female", "female", "male"]
    }
    return pd.DataFrame(data)

def test_decide_response_when_awaiting_clarification():
    state = AnalystState()
    state.awaiting_clarification = True

    mode = decide_response_mode("Here is more detail", state)
    assert mode == "explain"

def test_decide_response_mode_with_existing_dashboard():
    state = AnalystState()
    state.dashboard_plan = {"visualizations": [], "kpis": []}
    mode = decide_response_mode("Can you update the dashboard?", state)
    assert mode == "revise_dashboard"

def test_decide_response_mode_visualization_trigger():
    state = AnalystState()
    mode = decide_response_mode("Can you plot Age vs Fare?", state)
    assert mode == "create dashboard"

def test_decide_response_mode_generic_text():
    state = AnalystState()
    mode = decide_response_mode("Just explain this dataset", state)
    assert mode == "explain"

def test_get_clarification_question_returns_string():
    state = AnalystState()
    df = sample_df()
    question = get_clarification_question(state, "What should I look at?", df)
    assert isinstance(question, str)
    assert len(question) > 0

def test_get_clarification_sets_awaiting_flag():
    state = AnalystState()
    df = sample_df()
    question = get_clarification_question(state, "What should I look at?", df)
    assert state.awaiting_clarification is True


def test_analyst_explain_returns_string():
    state = AnalystState()
    df = sample_df()
    explanation = analyst_explain(user_msg="Explain this data", state=state, df=df)
    assert isinstance(explanation, dict)
    assert "content" in explanation
    assert len(explanation["content"]) > 0

def test_analyst_explain_with_no_df():
    state = AnalystState()
    explanation = analyst_explain(user_msg="Explain this data", state=state, df=None)
    assert isinstance(explanation, dict)
    assert "content" in explanation
    assert len(explanation["content"]) > 0
    assert explanation["next_steps"]
    assert state.awaiting_clarification is False
