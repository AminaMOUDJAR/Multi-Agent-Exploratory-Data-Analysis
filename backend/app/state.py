# shared state for the whole pipeline. each agent gets this dict and returns
# whatever keys it wants to add/update, langgraph merges them for the next one.
# the dataframe only exists in here while the pipeline runs, we never ship it
# to the browser, just the small summary dicts.
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
