import re
from pathlib import Path

from gvs_pipeline.packets import COLUMNS

CAPTURE = Path(__file__).resolve().parents[2] / "uno_q" / "linux" / "capture.sh"


def test_capture_fields_match_parser_columns():
    # Reason: the parser reads columns by position; any drift silently mislabels every packet.
    fields = tuple(re.findall(r"-e ([a-z0-9_.]+)", CAPTURE.read_text()))
    assert fields == COLUMNS
