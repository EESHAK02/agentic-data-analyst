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


def decide_response_mode(user_msg: str, state: AnalystState) -> str:
    if not user_msg:
        return "explain"

    dashboard_exists = state.dashboard_plan is not None

    prompt = f"""
You are an AI data analyst agent.

You must choose the BEST next action based on:
1. The user's message
2. Whether a dashboard already exists

Current state:
- Dashboard exists: {dashboard_exists}

Available actions:
- explain: give a text-only analytical answer
- create_dashboard: create a new dashboard or charts
- revise_dashboard: modify or show the existing dashboard
- clarify: ask a clarifying question if the request is ambiguous

Guidelines:
- If the user asks to *see*, *show*, or *view* charts AND a dashboard exists → revise_dashboard
- If the user asks to *create* charts or dashboards AND none exists → create_dashboard
- If the question is conceptual or analytical → explain
- If intent is unclear → clarify

User message:
"{user_msg}"

Respond with ONLY one word:
explain | create_dashboard | revise_dashboard | clarify
"""

    try:
        response = ollama.chat(
            model="llama3.1:latest",
            messages=[{"role": "user", "content": prompt}],
        )

        # print(response)

        intent = response["message"]["content"].strip().lower().split()[0]

    except Exception as e:
        print("⚠️ Intent classification failed:", e)
        return "explain"

    if intent == "revise_dashboard" and state.dashboard_plan is None:
            return "create_dashboard"
    elif intent not in ["explain", "create_dashboard", "revise_dashboard", "clarify"]:
        return "explain"
    else:
        return intent
            

def get_clarification_question(state: AnalystState, user_msg:str, df:pd.DataFrame) -> str:
    state.awaiting_clarification = True
    # ques = "Could you please provide more details about your request to help me assist you better?"
    # return ques
    summary = state.dataset_summary
    if not summary:
        summary = summarize_dataset(df)
        state.dataset_summary = summary

    prompt = f"""
    You are a helpful data analyst assistant.

    The user asked: "{user_msg}"
    Dataset summary: {summary}

    Generate **one specific, concise question** in plain English to clarify the user's intent.
    Focus on missing details that prevent you from answering or creating a dashboard.

    Do NOT answer the user's question yet. 
    Only ask a single question that will help you proceed.
    """

    try:
        response = ollama.chat(
            model="llama3.1:latest",
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response["message"]["content"].strip()

        # Use the first sentence as the clarification question
        question = raw.split("\n")[0]

        # Save to unanswered questions for tracking
        state.unanswered_questions.append(question)

        return question

    except Exception as e:
        print("⚠️ LLM clarification failed:", e)
        # fallback hardcoded question
        return "Could you clarify your request so I can assist you better?"



def analyst_explain(user_msg: str, state: AnalystState, df: pd.DataFrame | None = None) -> Dict[str, Any]:
    """
    Provide a text-only explanation or insight based on the user's question.
    Uses LLM to generate a response.
    """
    # Summarize dataset if available
    summary = summarize_dataset(df) if df is not None else "No dataset provided."

    prompt = f"""
    You are a helpful data analyst assistant.

    Dataset summary:
    {summary}

    User asked:
    "{user_msg}"

    Provide a clear, concise, text-only explanation answering the user's question.
    Include any high-level insights, observations, or next steps.
    Respond in plain English. Do NOT output JSON.
    """

    try:
        response = ollama.chat(
            model="llama3.1:latest",
            messages=[{"role": "user", "content": prompt}]
        )
        text = response["message"]["content"]

        explanation = {
            "type": "explanation",
            "content": text,
            # "next_steps": [
            #     "Identify key variables from the question",
            #     "Check distributions and trends",
            #     "Decide if visualization or dashboard is needed"
            # ]
        }
        state.awaiting_clarification = False
        return explanation

    except Exception as e:
        print("⚠️ LLM explanation failed:", e)
        # fallback hardcoded explanation
        explanation = {
            "type": "explanation",
            "content": "Here's how I would approach this question, ...",
            "next_steps": [
                "Identify key variables from the question",
                "Check distributions and trends",
                "Decide if visualization or dashboard is needed"
            ]
        }
        state.awaiting_clarification = False
        return explanation




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
