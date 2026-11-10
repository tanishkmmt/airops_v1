"""Small serializers shared by the independent CSV/XLSX generation services."""
from __future__ import annotations

import base64
import io
from typing import Sequence


def xlsx_base64(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    from openpyxl import Workbook

    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("AIS Upload")
    sheet.append([str(value) for value in headers])
    for row in rows:
        sheet.append([str(value) if value is not None else "" for value in row])
    stream = io.BytesIO()
    workbook.save(stream)
    return base64.b64encode(stream.getvalue()).decode("ascii")
