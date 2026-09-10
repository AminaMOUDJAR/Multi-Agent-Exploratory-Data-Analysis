"""In-memory LRU store for generated reports (report_id -> {report, context}).

Keeps the last 20 reports; good enough for a local dev tool. Swap for Redis
or a DB if you need persistence across restarts.
"""
import uuid
from collections import OrderedDict
from threading import Lock

_MAX_REPORTS = 20
_REPORTS: "OrderedDict[str, dict]" = OrderedDict()
_LOCK = Lock()


def save_report(report: dict, context: str = "") -> str:
    report_id = uuid.uuid4().hex[:12]
    with _LOCK:
        _REPORTS[report_id] = {"report": report, "context": context}
        _REPORTS.move_to_end(report_id)
        while len(_REPORTS) > _MAX_REPORTS:
            _REPORTS.popitem(last=False)
    return report_id


def get_report(report_id: str):
    with _LOCK:
        entry = _REPORTS.get(report_id)
        if entry is not None:
            _REPORTS.move_to_end(report_id)
        return entry
