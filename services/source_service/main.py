from __future__ import annotations

import csv
import io
import os
import re
import zipfile
from datetime import date, datetime, time, timedelta
from email import policy
from email.parser import BytesParser
from pathlib import PurePosixPath
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from services.validation import duplicate_headers, normalize_header

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", "20971520"))
MAX_ROWS = 20_000
MAX_COLUMNS = 300
MAX_ARCHIVE_UNCOMPRESSED = 150 * 1024 * 1024
ALLOWED_EXTENSIONS = {".eml", ".csv", ".tsv", ".xlsx", ".xlsb"}

app = FastAPI(title="AirOps source service", docs_url=None, redoc_url=None)


def _text(value: Any, header: str = "") -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.strftime("%d/%m/%y %H:%M") if isinstance(value, datetime) and value.time() != time(0, 0) else value.strftime("%d/%m/%y")
    if isinstance(value, time):
        return value.strftime("%H:%M")
    if isinstance(value, (int, float)) and re.search(r"date|deadline|bookingdate", header, re.IGNORECASE):
        try:
            serial = float(value)
            date_value = datetime(1899, 12, 30) + timedelta(days=serial)
            return date_value.strftime("%d/%m/%y %H:%M") if date_value.time() != time(0, 0) else date_value.strftime("%d/%m/%y")
        except (OverflowError, ValueError):
            return str(value)
    return str(value).strip()


def _parse_text_date(text: str) -> date | None:
    for fmt in ("%d/%m/%y %H:%M", "%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d", "%d-%b-%y", "%d-%b-%Y"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _departure_contract_candidates(headers: list[Any], rows: list[list[Any]]) -> tuple[list[dict[str, Any]], int]:
    indexes = {_norm(str(header)): index for index, header in enumerate(headers)}
    def value(row: list[Any], *names: str) -> str:
        for name in names:
            index = indexes.get(_norm(name))
            if index is not None and index < len(row):
                return _text(row[index], str(headers[index]))
        return ""
    def route(text: str) -> list[str]:
        clean = text.strip().upper()
        if re.fullmatch(r"[A-Z]{6}", clean):
            return [clean[:3], clean[3:]]
        return [part.strip().upper() for part in re.split(r"\s*(?:-|→|–|—|\bto\b)\s*", text, flags=re.I) if part.strip()]
    flights: list[dict[str, Any]] = []
    invalid = 0
    for row in rows:
        airline = value(row, "Airline", "Airline Code").upper()
        if not airline:
            match = re.match(r"\s*([A-Z0-9]{2})[ -]?\d", value(row, "Flight", "Flight No").upper())
            airline = match.group(1) if match else ""
        onward = route(value(row, "Sector_Onwards", "Sector", "Sector Onwards"))
        returned = route(value(row, "Sector_Return", "Return Sector"))
        if not airline or len(onward) < 2:
            invalid += 1
            continue
        dep = _parse_text_date(value(row, "Dep_Date", "Departure Date", "Travel Date"))
        if dep is None:
            invalid += 1
            continue
        status = value(row, "Final_Status") or "Unspecified"
        pnr = value(row, "PNR", "PNR_Onwards", "Onward PNR")
        first_to = onward[1] if len(onward) > 2 else onward[-1]
        flights.append({"airline": airline, "pnr": pnr, "status": status,
                        "legs": [{"origin": onward[0], "destination": first_to, "date": dep.strftime("%d/%m/%y")}],
                        "direction": "outbound"})
        reverse = returned if len(returned) >= 2 else (onward[1:] if len(onward) == 3 else [])
        if reverse:
            return_date = _parse_text_date(value(row, "Return_Date", "Return Date"))
            if return_date is None:
                invalid += 1
                continue
            return_pnr = value(row, "PNR2", "PNR_Return", "Return PNR") if returned else pnr
            flights.append({"airline": airline, "pnr": return_pnr, "status": status,
                            "legs": [{"origin": reverse[0], "destination": reverse[-1], "date": return_date.strftime("%d/%m/%y")}],
                            "direction": "return"})
    return _contract_candidates_from_flights(flights), invalid


def _safe_name(name: str) -> str:
    return PurePosixPath(name.replace("\\", "/")).name[:180] or "upload"


def _table(name: str, headers: list[str], rows: list[list[Any]], source_file: str) -> dict[str, Any]:
    clean_headers = [_text(h) for h in headers[:MAX_COLUMNS]]
    clean_rows = [[_text(c, clean_headers[index] if index < len(clean_headers) else "") for index, c in enumerate(row[:MAX_COLUMNS])] for row in rows[:MAX_ROWS]]
    while clean_headers and not clean_headers[-1]:
        clean_headers.pop()
    width = len(clean_headers)
    clean_rows = [row[:width] + [""] * max(0, width - len(row)) for row in clean_rows]
    clean_rows = [row for row in clean_rows if any(value.strip() for value in row)]
    return {
        "name": name[:180],
        "sourceFile": source_file,
        "headers": clean_headers,
        "rows": clean_rows,
        "rowCount": len(clean_rows),
        "truncated": len(rows) > MAX_ROWS,
        "duplicateHeaders": duplicate_headers(clean_headers),
    }


def _guard_archive(data: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            unpacked = sum(entry.file_size for entry in entries)
            if unpacked > MAX_ARCHIVE_UNCOMPRESSED:
                raise ValueError("Workbook expands beyond the 150 MB safety limit.")
            for entry in entries:
                if entry.file_size > 0 and (entry.compress_size == 0 or entry.file_size / entry.compress_size > 1000):
                    raise ValueError("Workbook contains an unusually compressed entry and was rejected.")
    except zipfile.BadZipFile as exc:
        raise ValueError("Workbook is not a valid XLSX/XLSB archive.") from exc


def _parse_csv(data: bytes, filename: str) -> list[dict[str, Any]]:
    try:
        content = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = data.decode("cp1252", errors="replace")
    delimiter = "\t" if PurePosixPath(filename).suffix.lower() == ".tsv" else ","
    try:
        sample = content[:8192]
        if delimiter == "," and sample:
            delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
        parsed = []
        for row in csv.reader(io.StringIO(content), delimiter=delimiter):
            if len(parsed) >= MAX_ROWS + 2:
                break
            parsed.append(row)
    except csv.Error as exc:
        raise ValueError(f"Could not read CSV structure: {exc}") from exc
    if not parsed:
        raise ValueError("The CSV is empty.")
    return [_table(filename, parsed[0], parsed[1:], filename)]


def _parse_xlsx(data: bytes, filename: str) -> list[dict[str, Any]]:
    _guard_archive(data)
    try:
        from openpyxl import load_workbook

        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:
        raise ValueError(f"Could not read XLSX workbook: {type(exc).__name__}") from exc
    tables: list[dict[str, Any]] = []
    try:
        for sheet in workbook.worksheets:
            iterator = sheet.iter_rows(values_only=True)
            header_row: tuple[Any, ...] | None = None
            data_rows: list[list[Any]] = []
            truncated = False
            for row in iterator:
                if header_row is None:
                    if any(value is not None and str(value).strip() for value in row):
                        header_row = row[:MAX_COLUMNS]
                    continue
                if len(data_rows) >= MAX_ROWS + 1:
                    truncated = True
                    break
                data_rows.append(list(row[:MAX_COLUMNS]))
            if header_row is not None:
                table = _table(sheet.title, list(header_row), data_rows, filename)
                table["truncated"] = table["truncated"] or truncated
                tables.append(table)
    finally:
        workbook.close()
    if not tables:
        raise ValueError("No readable worksheets were found.")
    return tables


def _parse_xlsb(data: bytes, filename: str) -> list[dict[str, Any]]:
    _guard_archive(data)
    try:
        from python_calamine import CalamineWorkbook

        workbook = CalamineWorkbook.from_filelike(io.BytesIO(data))
    except Exception as exc:
        raise ValueError(f"Could not read XLSB workbook: {type(exc).__name__}") from exc
    tables: list[dict[str, Any]] = []
    try:
        skip_sheets = {"naming", "issued-naminglist", "ofline issuance"}
        available = {name.casefold() for name in workbook.sheet_names if name}
        # Preserve the existing Summary + Terms inputs for block preparation while
        # independently aggregating Departures for the contract-preparation workflow.
        preferred = ({"summary", "terms", "departures"} if "summary" in available
                     else ({"departures"} if "departures" in available else None))
        paired_summary = False
        # Inspect Summary first. Its separate PNR/PNR2 columns are the authoritative
        # leg linkage for this workbook format; older Departures tabs can coexist.
        ordered_sheets = sorted(enumerate(workbook.sheet_names), key=lambda entry: 0 if entry[1].casefold() == "summary" else 1)
        for index, sheet_name in ordered_sheets:
            if not sheet_name:
                continue
            if preferred and sheet_name.casefold() not in preferred:
                continue
            if paired_summary and sheet_name.casefold() == "departures":
                continue
            if sheet_name.casefold() in skip_sheets:
                continue
            try:
                sheet = workbook.get_sheet_by_index(index)
                iterator = iter(sheet.iter_rows())
                header: list[Any] | None = None
                data_rows: list[list[Any]] = []
                total_data_rows = 0
                departure_rows: list[list[Any]] = []
                departure_columns: list[int | None] = []
                departure_fields = ["Airline", "Airline Code", "Flight", "Flight No", "Sector_Onwards", "Sector", "Sector_Return", "Return Sector", "Dep_Date", "Departure Date", "Return_Date", "PNR", "PNR2", "PNR_Return", "Final_Status"]
                truncated = False
                is_departures = sheet_name.casefold() == "departures"
                for row in iterator:
                    values = list(row[:MAX_COLUMNS])
                    if header is None:
                        if any(value is not None and str(value).strip() for value in values):
                            header = values[:MAX_COLUMNS]
                            if is_departures:
                                departure_columns = [_column([str(cell) for cell in header], {name}) for name in departure_fields]
                        continue
                    if not any(value is not None for value in values):
                        continue
                    if not is_departures and total_data_rows >= MAX_ROWS:
                        truncated = True
                        break
                    total_data_rows += 1
                    if is_departures:
                        if len(departure_rows) >= 250_000:
                            raise ValueError("Departures contains more than 250,000 rows. Split the source file before preparing contracts.")
                        # Keep only route, date, PNR and status cells for pairing. Never
                        # retain or return passenger-level worksheet rows.
                        departure_rows.append([values[column] if column is not None and column < len(values) else None for column in departure_columns])
                    if not is_departures and len(data_rows) < MAX_ROWS:
                        data_rows.append(values[:MAX_COLUMNS])
                if header is not None:
                    table = _table(sheet_name, header, data_rows, filename)
                    table["truncated"] = table["truncated"] or truncated
                    if sheet_name.casefold() == "summary":
                        paired_summary = _is_paired_summary_headers(table["headers"])
                    if is_departures:
                        candidates, departure_invalid = _departure_contract_candidates(departure_fields, departure_rows)
                        if len(candidates) > 5_000:
                            raise ValueError("Departures data contains more than 5,000 distinct airline/route groups. Split the source file before processing.")
                        table["rowCount"] = total_data_rows
                        # Departure rows contain passenger names, DOB, passport and PNRs.
                        # Only grouped route/date counts leave the parser for this workflow.
                        table["rows"] = []
                        table["rowsOmittedForPrivacy"] = True
                        table["truncated"] = truncated
                        table["contractCandidates"] = candidates
                        table["invalidContractRows"] = departure_invalid
                    tables.append(table)
            except ValueError:
                raise
            except Exception as exc:
                raise ValueError(f"Could not fully read XLSB worksheet '{_safe_name(sheet_name)}': {type(exc).__name__}.") from exc
    finally:
        workbook.close()
    if not tables:
        raise ValueError("No readable XLSB worksheets were found.")
    return tables


def _parse_attachment(data: bytes, filename: str) -> list[dict[str, Any]]:
    suffix = PurePosixPath(filename).suffix.lower()
    if suffix in {".xlsx", ".xlsm"}:
        return _parse_xlsx(data, filename)
    if suffix == ".xlsb":
        return _parse_xlsb(data, filename)
    if suffix in {".csv", ".tsv"}:
        return _parse_csv(data, filename)
    return []


def _parse_eml(data: bytes, filename: str) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    try:
        message = BytesParser(policy=policy.default).parsebytes(data)
    except Exception as exc:
        raise ValueError("Could not parse the email file.") from exc
    body_parts: list[str] = []
    attachments: list[str] = []
    tables: list[dict[str, Any]] = []
    for part in message.walk():
        if part.is_multipart():
            continue
        payload = part.get_payload(decode=True) or b""
        attached_name = part.get_filename()
        if attached_name:
            safe = _safe_name(attached_name)
            attachments.append(safe)
            if len(payload) > MAX_UPLOAD_BYTES:
                continue
            try:
                tables.extend(_parse_attachment(payload, safe))
            except ValueError:
                continue
        elif part.get_content_type() == "text/plain":
            try:
                text = part.get_content()
                if isinstance(text, str):
                    body_parts.append(text[:40_000])
            except Exception:
                continue
    return tables, attachments, body_parts


_norm = normalize_header


def _column(headers: list[str], aliases: set[str]) -> int | None:
    # Prefer the earliest matching physical column. This matters for Thailand
    # sheets that contain both source PNRs and later-derived PNR columns.
    normalized_aliases = {_norm(alias) for alias in aliases}
    for index, header in enumerate(headers):
        if _norm(header) in normalized_aliases:
            return index
    return None


def _is_paired_summary_headers(headers: list[str]) -> bool:
    names = {_norm(str(value)) for value in headers}
    return {"airline", "sector", "returnsector", "pnr", "pnr2", "depdate", "returndate"}.issubset(names)


def _flight_groups(table: dict[str, Any]) -> list[dict[str, Any]]:
    headers = table["headers"]
    # Thailand-style operational summaries keep outbound and return inventory in the same row.
    paired = {
        "out_pnr": _column(headers, {"PNR", "Onward PNR"}),
        "out_date": _column(headers, {"Dep Date", "Departure Date"}),
        "out_sector": _column(headers, {"Sector", "Sector_Onwards"}),
        "out_flight": _column(headers, {"Flight No", "FlightNo_Onwards"}),
        "out_timing": _column(headers, {"TIMINGS", "Departure time"}),
        "out_seats": _column(headers, {"Total Onwrd Seats", "Seats"}),
        "out_fare": _column(headers, {"Fares", "Fare"}),
        "out_deadline": _column(headers, {"Ticketing Deadline", "TIME LIMIT", "Deadline D-7"}),
        "return_pnr": _column(headers, {"PNR2", "Return PNR"}),
        "return_date": _column(headers, {"Return Date"}),
        "return_sector": _column(headers, {"Return Sector"}),
        "return_flight": _column(headers, {"Flight No2", "FlightNo_Return"}),
        "return_timing": _column(headers, {"TIMINGS3", "Return timing"}),
        "return_seats": _column(headers, {"TOTAL Return seats", "Return seats"}),
        "return_fare": _column(headers, {"Fares4", "Return fare"}),
        "return_deadline": _column(headers, {"Return Ticketing Deadline", "Deadline 7"}),
    }
    paired_headers = {
        key: (str(headers[index]).strip() if index is not None and index < len(headers) else "")
        for key, index in paired.items()
    }
    if all(paired[key] is not None for key in ("out_pnr", "out_date", "out_sector", "out_flight", "return_pnr", "return_date", "return_sector", "return_flight")):
        result: list[dict[str, Any]] = []
        airline_i = _column(headers, {"Airline", "Airline Code", "Marketing Airline"})
        def cell(row: list[str], key: str) -> str:
            index = paired[key]
            return row[index].strip() if index is not None and index < len(row) else ""
        for row_number, row in enumerate(table["rows"], start=2):
            for prefix, direction in (("out", "outbound"), ("return", "return")):
                pnr = cell(row, f"{prefix}_pnr")
                if not pnr:
                    continue
                sector = cell(row, f"{prefix}_sector").split("-")
                timing = cell(row, f"{prefix}_timing").split("-")
                flight = cell(row, f"{prefix}_flight")
                result.append({
                    "sourceSheet": table["name"], "sourceFile": table["sourceFile"], "pnr": pnr,
                    "direction": direction, "sourceRow": row_number,
                    "airline": row[airline_i].strip() if airline_i is not None and airline_i < len(row) else "",
                    "seats": cell(row, f"{prefix}_seats"), "fare": cell(row, f"{prefix}_fare"),
                    "timeLimit": cell(row, f"{prefix}_deadline"),
                    "timeLimitHeader": paired_headers.get(f"{prefix}_deadline", ""), "legs": [{
                        "date": cell(row, f"{prefix}_date"),
                        "origin": sector[0].strip() if sector else "",
                        "destination": sector[1].strip() if len(sector) > 1 else "",
                        "flight": flight, "departure": timing[0].strip() if timing else "",
                        "arrival": timing[1].strip() if len(timing) > 1 else "", "sourceRow": row_number,
                    }],
                })
        if result:
            return result
    pnr_i = _column(headers, {"PNR", "PNRNo", "PNR No", "airlinePnr", "PNR2"})
    if pnr_i is None:
        return []
    origin_i = _column(headers, {"O/B", "Origin", "from", "depArpCd", "Sector origin"})
    dest_i = _column(headers, {"I/B", "Destination", "to", "arrArpCd", "Sector destination"})
    date_i = _column(headers, {"FlightDate", "Dep Date", "Return Date", "depDate", "Date"})
    flight_i = _column(headers, {"FC", "Flight No", "Flight No2", "FlightNo_Onwards", "fltNo"})
    dep_i = _column(headers, {"DEP", "TIMINGS", "Departure time", "depTime"})
    arr_i = _column(headers, {"ARR", "Arrival time", "arrTime"})
    seats_i = _column(headers, {"Seats", "Total Onwrd Seats", "TOTAL Return seats", "totSeats"})
    fare_i = _column(headers, {"Fare", "Fares", "Fares4", "adultFare"})
    limit_i = _column(headers, {"TIME LIMIT", "Ticketing Deadline", "timeLimit", "Deadline D-7", "Deadline 7"})
    airline_i = _column(headers, {"Airline", "Airline Code", "Marketing Airline"})
    groups: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def flush() -> None:
        nonlocal current
        if current and current["legs"]:
            groups.append(current)
        current = None

    def get(row: list[str], idx: int | None) -> str:
        return row[idx].strip() if idx is not None and idx < len(row) else ""

    for row_number, row in enumerate(table["rows"], start=2):
        row_pnr = get(row, pnr_i)
        if not any(cell.strip() for cell in row):
            flush()
            continue
        if row_pnr:
            flush()
            current = {"sourceSheet": table["name"], "sourceFile": table["sourceFile"], "pnr": row_pnr, "sourceRow": row_number, "airline": get(row, airline_i), "seats": get(row, seats_i), "fare": get(row, fare_i), "timeLimit": get(row, limit_i), "legs": []}
        if current is None:
            continue
        leg = {
            "date": get(row, date_i), "origin": get(row, origin_i), "destination": get(row, dest_i),
            "flight": get(row, flight_i), "departure": get(row, dep_i), "arrival": get(row, arr_i), "sourceRow": row_number,
        }
        if any(leg[key] for key in ("date", "origin", "destination", "flight", "departure", "arrival")):
            current["legs"].append(leg)
    flush()
    return groups


def _contract_candidates_from_flights(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pair reciprocal legs only when their airline PNR is the same."""
    by_pnr: dict[tuple[str, str], list[dict[str, Any]]] = {}
    unlinked: list[dict[str, Any]] = []
    for group in groups:
        legs = group.get("legs") or []
        airline = str(group.get("airline") or "").strip().upper()
        if not airline:
            continue
        pnr = str(group.get("pnr") or "").strip().upper()
        for leg in legs:
            origin = str(leg.get("origin") or "").strip().upper()
            destination = str(leg.get("destination") or "").strip().upper()
            departure = _parse_text_date(str(leg.get("date") or ""))
            if not origin or not destination or departure is None:
                continue
            record = {"airline": airline, "origin": origin, "destination": destination,
                      "date": departure, "direction": group.get("direction") or "", "status": group.get("status") or ""}
            if pnr:
                by_pnr.setdefault((airline, pnr), []).append(record)
            else:
                unlinked.append(record)

    candidates: dict[tuple[str, ...], dict[str, Any]] = {}

    def add(airline: str, first: tuple[str, str], second: tuple[str, str] | None, records: list[dict[str, Any]]) -> None:
        journey_type = "RT" if second else "OW"
        from2, to2 = second or ("", "")
        key = (airline, journey_type, *first, from2, to2)
        start = min(record["date"] for record in records)
        end = max(record["date"] for record in records)
        statuses: dict[str, int] = {}
        for record in records:
            if record["status"]:
                statuses[record["status"]] = statuses.get(record["status"], 0) + 1
        existing = candidates.get(key)
        if existing:
            existing["startDate"] = min(_parse_text_date(existing["startDate"]), start).strftime("%d/%m/%y")
            existing["endDate"] = max(_parse_text_date(existing["endDate"]), end).strftime("%d/%m/%y")
            existing["sourceRows"] += len(records)
            for status, count in statuses.items():
                existing["statusCounts"][status] = existing["statusCounts"].get(status, 0) + count
        else:
            candidates[key] = {
                "airline": airline, "journeyType": journey_type,
                "journey1From": first[0], "journey1To": first[1],
                "journey2From": from2, "journey2To": to2,
                "startDate": start.strftime("%d/%m/%y"), "endDate": end.strftime("%d/%m/%y"),
                "sourceRows": len(records), "statusCounts": statuses,
            }

    for (airline, _pnr), records in by_pnr.items():
        routes = {(record["origin"], record["destination"]) for record in records}
        if len(routes) == 2 and all((destination, origin) in routes for origin, destination in routes):
            outward = next((record for record in records if record["direction"] == "outbound"), records[0])
            first = (outward["origin"], outward["destination"])
            add(airline, first, (first[1], first[0]), records)
        else:
            for record in records:
                add(airline, (record["origin"], record["destination"]), None, [record])
    for record in unlinked:
        add(record["airline"], (record["origin"], record["destination"]), None, [record])
    return sorted(candidates.values(), key=lambda item: (item["airline"], item["journey1From"], item["journey1To"], item["journey2To"]))


def _classify(tables: list[dict[str, Any]]) -> None:
    for table in tables:
        headers = {_norm(header) for header in table["headers"]}
        if "blockid" in headers:
            table["detectedRole"] = "AIS block export"
        elif "contractid" in headers and any("itineraries" in header.casefold() for header in table["headers"]):
            table["detectedRole"] = "AIS block upload or result"
        elif "contractname" in headers and any(_norm(header) == "journey1from" for header in table["headers"]):
            table["detectedRole"] = "AIS contract template or result"
        elif "contractid" in headers and any(_norm(header) == "journeytype" for header in table["headers"]):
            table["detectedRole"] = "Contract terms source"
        elif {"bookingid", "sectoronwards", "airline"}.issubset(headers):
            table["detectedRole"] = "Airline departures source"
        elif any(_norm(header) in {"flightdate", "flightno", "flightno2", "sector"} for header in table["headers"]):
            table["detectedRole"] = "Procurement or flight source"
        else:
            table["detectedRole"] = "Unclassified source"


@app.middleware("http")
async def no_store(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "source"}


@app.post("/inspect")
async def inspect_source(file: UploadFile = File(...)) -> JSONResponse:
    filename = _safe_name(file.filename or "upload")
    suffix = PurePosixPath(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        await file.close()
        raise HTTPException(415, "Supported types: EML, CSV, TSV, XLSX, XLSB.")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()
    if len(data) > MAX_UPLOAD_BYTES:
        max_mib = MAX_UPLOAD_BYTES / (1024 * 1024)
        raise HTTPException(413, f"File exceeds the {max_mib:g} MiB upload limit.")
    try:
        if suffix == ".eml":
            tables, attachments, body = _parse_eml(data, filename)
            email_meta = {"subject": str(BytesParser(policy=policy.default).parsebytes(data).get("subject", ""))[:200], "attachments": attachments, "bodyExcerpt": "\n".join(body)[:2000]}
        elif suffix in {".csv", ".tsv"}:
            tables, email_meta = _parse_csv(data, filename), None
        elif suffix == ".xlsb":
            tables, email_meta = _parse_xlsb(data, filename), None
        else:
            tables, email_meta = _parse_xlsx(data, filename), None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    _classify(tables)
    paired_summary = next((table for table in tables if table["name"].casefold() == "summary" and _is_paired_summary_headers(table["headers"])), None)
    group_tables = [paired_summary] if paired_summary else tables
    groups = [group for table in group_tables for group in _flight_groups(table)]
    # Thailand workbooks often repeat the same inventory in Pivot and Summary.
    # De-duplicate identical PNR/flight/date groups while keeping first-sheet provenance.
    unique_groups: list[dict[str, Any]] = []
    seen_groups: set[tuple[str, ...]] = set()
    for group in groups:
        legs = group.get("legs", [])
        signature = (
            _norm(group.get("pnr", "")), _norm(group.get("direction", "")),
            *(_norm(leg.get(key, "")) for leg in legs for key in ("date", "origin", "destination", "flight")),
        )
        if signature in seen_groups:
            continue
        seen_groups.add(signature)
        unique_groups.append(group)
    groups = unique_groups
    contract_candidates = _contract_candidates_from_flights(groups)
    if paired_summary:
        paired_summary["contractCandidates"] = contract_candidates
    notices = ["AIS field requirements and business defaults are not inferred from sample rows.", "Uploaded content is processed in memory and is not retained by this service."]
    if paired_summary:
        notices.append("Contract routes use the paired Summary sheet; reciprocal sectors require the same PNR to form one return contract.")
    return JSONResponse({"fileName": filename, "tables": tables, "groups": groups, "contractCandidates": contract_candidates, "email": email_meta, "notices": notices})
