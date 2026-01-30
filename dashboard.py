"""
Dashboard rendering logic. 

Transforming a dashboard plan into tables and visualizations

"""

import streamlit as st
import plotly.express as px

def render_kpis(df, kpis):
    if not kpis:
        return
    cols = st.columns(len(kpis))
    for col, kpi in zip(cols, kpis):
        column = kpi.get("column")
        agg = kpi.get("aggregation")
        unit = kpi.get("unit", "")
        fmt = kpi.get("format")

        if column not in df.columns:
            col.warning(f"{kpi['label']} Column '{column}' not in dataset")
            continue

        try:
            if agg == "count":
                value = df[column].count()
            elif agg == "mean":
                value = df[column].mean()
            elif agg == "sum":
                value = df[column].sum()
            else:
                value = None

            if value is None:
                display = "N/A"
            elif fmt == "percent":
                display = f"{value * 100:.1f}%"
            elif isinstance(value, float):
                display = f"{value:,.2f}{unit}"
            else:
                display = f"{value}{unit}"

            col.metric(kpi["label"], display)
        except Exception as e:
            col.error(f"{kpi['label']} ❌ Error: {str(e)}")


def render_filters(df):
    st.sidebar.header("Filters")
    filters = {}
    for col in df.columns:
        if df[col].nunique() <= 20:
            selected = st.sidebar.multiselect(f"{col}", options=df[col].unique(), default=list(df[col].unique()))
            filters[col] = selected
    return filters


def render_dashboard(df, plan):
    st.header(plan.get("template_name", "AI Dashboard"))

    # KPIs
    render_kpis(df, plan.get("kpis", []))

    # Filters
    filters = render_filters(df)
    for col, selected in filters.items():
        df = df[df[col].isin(selected)]

    # Charts
    visualizations = plan.get("visualizations", [])
    cols_per_row = 2
    for i, viz in enumerate(visualizations):
        col_idx = i % cols_per_row
        if col_idx == 0:
            row = st.columns(cols_per_row)
        chart_col = row[col_idx]

        x = viz.get("x_axis")
        y = viz.get("y_axis")
        chart_type = viz.get("type", "bar")
        title = viz.get("title", "")

        try:
            if chart_type == "bar":
                fig = px.bar(df, x=x, y=y, color=x)
            elif chart_type == "line":
                fig = px.line(df, x=x, y=y, color=x)
            elif chart_type == "scatter":
                fig = px.scatter(df, x=x, y=y, color=x, hover_data=df.columns)
            elif chart_type == "pie":
                fig = px.pie(df, names=x, values=y)
            else:
                fig = px.bar(df, x=x, y=y, color=x)
            chart_col.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            chart_col.error(f"{title} ❌ Error: {str(e)}")
