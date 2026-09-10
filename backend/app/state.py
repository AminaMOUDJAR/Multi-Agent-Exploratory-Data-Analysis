"""Shared LangGraph state for the EDA pipeline.

Every agent is a pure function `agent(state) -> partial state update`.
The DataFrame lives only inside the pipeline (never serialized to the client);
the final report is assembled from the smaller dict fields below.
"""
from typing import Any, Dict, List, Optional

import pandas as pd
from typing_extensions import TypedDict


class EDAState(TypedDict, total=False):
    # inputs
    file_path: str
    file_name: str

    # loader
    df: Optional[pd.DataFrame]
    error: Optional[str]
    load_info: Dict[str, Any]

    # cleaner
    cleaning: Dict[str, Any]

    # profiler
    profile: Dict[str, Any]

    # modeler
    modeling: Dict[str, Any]

    # visualizer
    charts: List[Dict[str, Any]]

    # insights
    insights: Dict[str, Any]
    context: str
