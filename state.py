"""
Docstring for state

Here we define the shared mutable state

This state is basically the agent's memory across turns which tracks - 
- user goals
- agent actions
- assumptions
- open questions
- dashboard idea

"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import pandas as pd

@dataclass
class AnalystState:
    # dataset
    df: Optional[pd.DataFrame] = None
    dataset_summary: Dict[str, Any] = field(default_factory=dict)

    # user intent
    user_goal: Optional[str] = None

    # uncertainty handling
    assumptions: List[str] = field(default_factory=list)
    unanswered_questions: List[str] = field(default_factory=list)
    awaiting_clarification: bool = False

    # dashboard design
    dashboard_plan: Optional[Dict[str, Any]] = None
    last_rendered_dashboard: Optional[Any] = None

    # lifecycle
    goal_completed: bool = False
