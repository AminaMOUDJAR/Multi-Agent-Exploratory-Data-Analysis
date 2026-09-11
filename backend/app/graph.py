# langgraph wiring: a straight line, one node per agent.
# every agent is a function over the shared EDAState, so adding a step later
# (loops, conditional edges, a human sign-off node) is just another add_node.
from langgraph.graph import END, START, StateGraph

from .agents import (
    cleaner_agent,
    insights_agent,
    loader_agent,
    modeler_agent,
    profiler_agent,
    visualizer_agent,
)
from .state import EDAState

PIPELINE = ["loader", "cleaner", "profiler", "modeler", "visualizer", "insights"]

_AGENTS = {
    "loader": loader_agent,
    "cleaner": cleaner_agent,
    "profiler": profiler_agent,
    "modeler": modeler_agent,
    "visualizer": visualizer_agent,
    "insights": insights_agent,
}


def build_pipeline():
    graph = StateGraph(EDAState)
    for name in PIPELINE:
        graph.add_node(name, _AGENTS[name])
    graph.add_edge(START, "loader")
    for a, b in zip(PIPELINE, PIPELINE[1:]):
        graph.add_edge(a, b)
    graph.add_edge("insights", END)
    return graph.compile()


eda_graph = build_pipeline()
