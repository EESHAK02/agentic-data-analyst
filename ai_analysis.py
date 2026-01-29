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
import pandas as pd
import json
import re
import ollama
from data_loader import summarize_dataset

def parse_intent(user_msg: str, state: AnalystState) -> str:
    """
    Determine the user's intent based on their message and current state.

    Expected intents:
    - "clarify" - agent to ask a clarification question
    - "analyze" - agent to create a new dashboard plan
    - "revise" - agent to revise existing plan
    - "render" - agent to render the dashboard
    """
    
    if "clarify" in user_msg.lower():
        return "clarify"
    elif "revise" in user_msg.lower():
        return "revise"
    elif "render" in user_msg.lower():
        return "render"
    else:
        return "analyze"


def ask_clarification(state: AnalystState) -> str:
    """
    Generate a clarification question to resolve the most important
    uncertainty blocking progress.
    """

    if state.unanswered_questions:
        return state.unanswered_questions.pop(0)
    return "Could you please provide more details about your exact needs?"


def create_dashboard_plan(df: pd.DataFrame,state: AnalystState) -> Dict[str, Any]:
    """
    Create a structured dashboard plan based on the dataset summary,
    user goal, and current assumptions.
    """
    
    summary = summarize_dataset(df)
    prompt = f"""
    I have this dataset summary:
    {summary}
    The user wants to: {state.user_goal}
    Suggest up to 5 charts and 5 KPIs that would be most useful.
    For each chart:
      - type (bar, line, scatter, pie)
      - x_axis
      - y_axis
      - title
      - purpose
    For each KPI:
      - label
      - column (must exist in dataset)
      - aggregation (count, sum, mean)
      - unit (if applicable)
      - format (optional: percent)
    
    Output ONLY valid JSON in this structure:
    {{
      "template_name": "AI Dashboard",
      "domain": "Generic",
      "confidence": 0.95,
      "visualizations": [...],
      "kpis": [...]
    }}
    """

    try:
        # Call local Ollama model
        response = ollama.chat(
            model="llama3.1:latest",
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response["message"]["content"]

        # Attempt to extract JSON object from model output
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                ai_output = json.loads(match.group())
            except json.JSONDecodeError:
                ai_output = None
        else:
            ai_output = None

        # Use fallback only if AI output is missing or invalid
        if not ai_output or "visualizations" not in ai_output:
            ai_output = {
                "template_name": "Fallback Dashboard",
                "domain": "Dataset",
                "confidence": 0.9,
                "visualizations": [],
                "kpis": []
            }

        # Filter charts & KPIs to only existing columns
        filtered_charts = []
        for chart in ai_output.get("visualizations", []):
            if chart.get("x_axis") in df.columns and chart.get("y_axis") in df.columns:
                filtered_charts.append(chart)
        ai_output["visualizations"] = filtered_charts

        filtered_kpis = []
        for kpi in ai_output.get("kpis", []):
            if kpi.get("column") in df.columns:
                # Default unit to empty string if missing
                if "unit" not in kpi:
                    kpi["unit"] = ""
                filtered_kpis.append(kpi)
        ai_output["kpis"] = filtered_kpis

        # Ensure we have at least one chart and one KPI
        if not ai_output["visualizations"] or not ai_output["kpis"]:
            raise ValueError("AI returned empty charts/KPIs, using dynamic fallback.")

    except Exception as e:
        print("AI model failed or returned invalid output:", str(e))
        # Dynamic fallback: generate charts/KPIs based on dataset automatically
        ai_output = dynamic_fallback(df)
    
    return ai_output


def revise_dashboard_plan(state: AnalystState, user_msg: str) -> Dict[str, Any]:
    """
    Modify an existing dashboard plan based on simple user instructions.
    """
    plan = state.dashboard_plan
    if not plan:
        return plan  # nothing to revise yet

    msg_lower = user_msg.lower()

    # Change x-axis of first chart
    if "change x-axis" in msg_lower and plan.get("visualizations"):
        new_x = msg_lower.split()[-1]  # naive: last word is column name
        plan["visualizations"][0]["x_axis"] = new_x

    # Add simple KPI if requested
    if "add kpi" in msg_lower:
        numeric_cols = state.df.select_dtypes(include="number").columns.tolist()
        if numeric_cols:
            plan["kpis"].append({
                "label": f"Total {numeric_cols[0]}",
                "column": numeric_cols[0],
                "aggregation": "sum",
                "unit": "",
                "format": None
            })

    return plan



def dynamic_fallback(df: pd.DataFrame) -> Dict:
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    categorical_cols = df.select_dtypes(exclude="number").columns.tolist()

    # Create up to 3 simple charts
    visualizations = []
    if categorical_cols and numeric_cols:
        for i, cat_col in enumerate(categorical_cols[:3]):
            visualizations.append({
                "type": "bar",
                "x_axis": cat_col,
                "y_axis": numeric_cols[0],
                "title": f"{numeric_cols[0]} by {cat_col}",
                "purpose": f"Shows {numeric_cols[0]} distribution by {cat_col}"
            })
    elif numeric_cols:
        for i, num_col in enumerate(numeric_cols[:3]):
            visualizations.append({
                "type": "histogram",
                "x_axis": num_col,
                "y_axis": num_col,
                "title": f"Distribution of {num_col}",
                "purpose": f"Histogram of {num_col}"
            })

    # Create up to 3 KPIs
    kpis = []
    for col in numeric_cols[:3]:
        kpis.append({
            "label": f"Total {col}",
            "column": col,
            "aggregation": "sum",
            "unit": "",
            "format": None
        })

    return {
        "template_name": "Dynamic Fallback Dashboard",
        "domain": "Generic",
        "confidence": 0.0,
        "visualizations": visualizations,
        "kpis": kpis
    }