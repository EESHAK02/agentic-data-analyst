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


# def ask_clarification(state: AnalystState) -> str:
#     """
#     Generate a clarification question to resolve the most important
#     uncertainty blocking progress.
#     """

#     if state.unanswered_questions:
#         return state.unanswered_questions.pop(0)
#     return "Could you please provide more details about your exact needs?"
def ask_clarification(state: AnalystState, user_msg: str, df: pd.DataFrame) -> str:
    """
    Generate a targeted clarification question based on:
    - the user's query
    - dataset summary
    - current state (assumptions, unanswered questions)
    """

    # 1. If there are existing unanswered questions, return the first
    if state.unanswered_questions:
        return state.unanswered_questions.pop(0)

    # 2. Summarize dataset if not already done
    summary = state.dataset_summary
    if not summary:
        summary = summarize_dataset(df)
        state.dataset_summary = summary

    # 3. Prompt LLM to suggest a specific clarification
    prompt = f"""
    You are a helpful data analyst assistant.

    The user asked: "{user_msg}"
    Dataset summary: {summary}

    Identify the **most important missing detail** that prevents you from fully answering the user's request.
    Ask a single, clear, specific question in plain English.
    """

    try:
        response = ollama.chat(
            model="llama3.1:latest",
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response["message"]["content"]

        # Extract first sentence as clarification
        question = raw.strip().split("\n")[0]

        # Save it to unanswered questions for tracking
        state.unanswered_questions.append(question)

        return question

    except Exception as e:
        print("⚠️ Clarification generation failed:", e)
        return "Could you clarify exactly what you want to know about the dataset?"


def needs_clarification(user_msg: str) -> bool:
    """
    Return True if the message is vague and we need clarification.
    For now, we assume questions with words like 'first', 'best', 'important' are vague.
    """
    vague_keywords = ["first", "important", "best", "interesting", "what to look at", "help me understand"]
    return any(k in user_msg.lower() for k in vague_keywords)

def wants_new_dashboard(msg: str) -> bool:
    triggers = [
        "start over",
        "new dashboard",
        "different dataset",
        "scratch",
        "completely new",
    ]
    return any(t in msg.lower() for t in triggers)

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
            col = kpi.get("column")
            agg = kpi.get("aggregation")

            if col not in df.columns:
                continue

            # KPI must be numeric unless aggregation is count
            if agg != "count" and not pd.api.types.is_numeric_dtype(df[col]):
                continue

            kpi.setdefault("unit", "")
            filtered_kpis.append(kpi)
        ai_output["kpis"] = filtered_kpis

        # Ensure we have at least one chart and one KPI
        if not ai_output["visualizations"] or not ai_output["kpis"]:
            raise ValueError("AI returned empty charts/KPIs, using dynamic fallback.")

    except Exception as e:
        print("AI model failed or returned invalid output:", str(e))
        # Dynamic fallback: generate charts/KPIs based on dataset automatically
        ai_output = dynamic_fallback(df)
    
    analysis_summary = {
        "user_question": state.user_goal,
        "approach": (
            "The dataset was summarized to understand available columns and data types. "
            "KPIs were selected to capture key aggregates, while charts were chosen to "
            "highlight trends and relationships relevant to the user's goal."
        ),
        "reasoning": []
    }
    # Explain charts
    for chart in ai_output.get("visualizations", []):
        purpose = chart.get("purpose") or chart.get("title", "")
        analysis_summary["reasoning"].append(
            f"Chart '{chart.get('title')}' was included to {purpose.lower()}."
        )

    # Explain KPIs
    for kpi in ai_output.get("kpis", []):
        analysis_summary["reasoning"].append(
            f"KPI '{kpi.get('label')}' summarizes the {kpi.get('aggregation')} of "
            f"'{kpi.get('column')}', providing a high-level indicator."
        )

    ai_output["analysis_summary"] = analysis_summary
    return ai_output


def revise_dashboard_plan(
    state: AnalystState,
    user_msg: str
) -> Dict[str, Any]:


    df = state.df
    existing_plan = state.dashboard_plan

    # Safety check
    if df is None or existing_plan is None:
        return existing_plan

    summary = summarize_dataset(df)

    prompt = f"""
You are an AI data analyst revising an EXISTING dashboard.

Dataset summary:
{summary}

Current dashboard plan (JSON):
{json.dumps(existing_plan, indent=2)}

User request:
"{user_msg}"

Your task:
- Modify the dashboard ONLY where needed to address the user's request
- Preserve charts and KPIs that are still relevant
- Use ONLY columns that exist in the dataset
- If the request is ambiguous or does not require a dashboard change,
  return the original dashboard unchanged
- Update or add an `analysis_summary` explaining:
    - what the user asked
    - what (if anything) changed
    - why the dashboard still answers the question

Output ONLY valid JSON in the SAME structure as the input dashboard.
Do NOT include explanations outside JSON.
"""

    try:
        response = ollama.chat(
            model="llama3.1:latest",
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response["message"]["content"]

        # Extract JSON safely
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError("No JSON found in LLM response")

        revised_plan = json.loads(match.group())

        # -------- Validation layer --------

        # Validate visualizations
        valid_visuals = []
        for chart in revised_plan.get("visualizations", []):
            x = chart.get("x_axis")
            y = chart.get("y_axis")
            if x in df.columns and y in df.columns:
                valid_visuals.append(chart)
        revised_plan["visualizations"] = valid_visuals

        # Validate KPIs
        valid_kpis = []
        for kpi in revised_plan.get("kpis", []):
            col = kpi.get("column")
            agg = kpi.get("aggregation")

            if col not in df.columns:
                continue

            # Non-count aggregations must be numeric
            if agg != "count" and not pd.api.types.is_numeric_dtype(df[col]):
                continue

            kpi.setdefault("unit", "")
            valid_kpis.append(kpi)

        revised_plan["kpis"] = valid_kpis

        # If revision removed everything, keep old plan
        if not revised_plan["visualizations"] and not revised_plan["kpis"]:
            return existing_plan

        return revised_plan

    except Exception as e:
        print("⚠️ Revision failed, keeping existing dashboard:", str(e))
        return existing_plan



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