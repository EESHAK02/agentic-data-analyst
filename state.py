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

# keep track of the agent's state 
@dataclass
class AnalystState:
    # user intent
    user_goal: Optional[str] = None

    # understanding the data
    dataset_summary: Dict[str, Any] = field(default_factory=dict)

    # handling uncertainty
    assumptions: List[str] = field(default_factory=list)
    unanswered_questions: List[str] = field(default_factory=list)

    # dashboard design
    dashboard_plan: Optional[Dict[str, Any]] = None

    # output 
    last_rendered_dashboard: Optional[Any] = None

    # condition to end
    goal_completed: bool = False