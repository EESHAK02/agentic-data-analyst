import pandas as pd
from ai_analysis import create_dashboard_plan
from dashboard import render_dashboard
from state import AnalystState
from data_loader import summarize_dataset

def sample_df():
    data = {
        "Age": [22, 38, 26, 35],
        "Fare": [7.25, 71.83, 7.92, 53.1],
        "Survived": [0, 1, 1, 1],
        "PassengerId": [1, 2, 3, 4],
        "Sex": ["male", "female", "female", "male"]
    }
    return pd.DataFrame(data)

def test_create_dashboard_plan():
    df = sample_df()
    state = AnalystState(user_goal="Show survival stats")
    plan = create_dashboard_plan(df, state)
    assert "visualizations" in plan
    assert "kpis" in plan
    assert isinstance(plan["visualizations"], list)
    assert isinstance(plan["kpis"], list)
