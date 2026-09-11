# reports are small (the df stays in the pipeline) so a dict + an LRU cap of
# 20 is plenty for a local tool. if you want them to survive a restart, swap
# this for sqlite or redis, the rest of the code only calls save/get.
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
