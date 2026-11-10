from __future__ import annotations

import base64
import csv
import io
import math
import re
import zipfile
from datetime import datetime
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from services.file_output import xlsx_base64
from services.request_models import TableHeaders, TableRows
from services.validation import duplicate_headers, formula_like, normalize_header
from .profiles import (BLOCK_CONFIG_FIELDS, config_field_metadata, get_profile, import_preview,
                       list_profiles, save_profile, save_template)
from .schema import KNOWN_OPTIONAL_FIELDS, derived_field, optional_field, source_owned

app = FastAPI(title="AirOps block service", docs_url=None, redoc_url=None)
norm = normalize_header


class BlockRequest(BaseModel):
    headers: TableHeaders
    rows: TableRows
    format: Literal["csv", "xlsx"] = "csv"
    profileCode: str = Field(min_length=3, max_length=16)
    profileVersion: int = Field(ge=1)
    contractReferences: list[dict[str, Any]] = Field(default_factory=list, max_length=500)


class BlockProfileRequest(BaseModel):
    fields: dict[str, str] = Field(max_length=300)


class BlockTemplateRequest(BaseModel):
    headers: TableHeaders
    fileName: str = Field(min_length=1, max_length=255)


class BlockProfileImportRequest(BaseModel):
    profileCode: str = Field(min_length=3, max_length=16)
    headers: TableHeaders
    rows: TableRows


@app.middleware("http")
async def no_store(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "blocks"}


@app.get("/profiles")
def block_profiles() -> dict[str, Any]:
    try:
        return {"profiles": list_profiles(), "configFields": BLOCK_CONFIG_FIELDS,
                "fieldMetadata": config_field_metadata(), "optionalFields": KNOWN_OPTIONAL_FIELDS,
                "schemaVersion": 2}
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.get("/profiles/{code}")
def block_profile(code: str) -> dict[str, Any]:
    try:
        profile = get_profile(code)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    if profile is None:
        raise HTTPException(404, f"Block configuration {code.upper()} was not found.")
    return profile


@app.put("/profiles/{code}")
def put_block_profile(code: str, request: BlockProfileRequest) -> dict[str, Any]:
    try:
        return save_profile(code, request.fields, "local user")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.put("/profiles/{code}/template")
def put_block_template(code: str, request: BlockTemplateRequest) -> dict[str, Any]:
    try:
        return save_template(code, request.headers, request.fileName, "local user")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.post("/profiles/import-preview")
def block_profile_import_preview(request: BlockProfileImportRequest) -> dict[str, Any]:
    try:
        profile = get_profile(request.profileCode)
        if profile is None:
            raise HTTPException(404, f"Block configuration {request.profileCode.upper()} was not found.")
        return import_preview(request.headers, request.rows, profile["configFields"])
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


def _date(value: Any) -> datetime | None:
    text = str(value or "").strip()
    for pattern in ("%d/%m/%y %H:%M", "%d/%m/%Y %H:%M", "%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue
    return None


def _contract_link_ok(row: list[str], indexes: dict[str, int], references: dict[str, dict[str, Any]], row_number: int, issues: list[str]) -> bool:
    def value(field: str) -> str:
        index = indexes.get(norm(field))
        return row[index].strip() if index is not None and index < len(row) else ""

    contract_id = value("contractId")
    reference = references.get(contract_id)
    if reference is None:
        issues.append(f"Block row {row_number}: contract ID is not present in the uploaded AIS contract result.")
        return False
    origin, destination = value("itineraries.1.from").casefold(), value("itineraries.1.to").casefold()
    routes = reference.get("routes", [])
    if routes and not any(str(route.get("from", "")).strip().casefold() == origin and
                          str(route.get("to", "")).strip().casefold() == destination for route in routes):
        issues.append(f"Block row {row_number}: selected contract {contract_id} does not include route {origin.upper()}–{destination.upper()}.")
        return False
    airline = value("itineraries.1.itineraryFlights.1.mrkAl").casefold()
    if airline and reference.get("airline") and str(reference["airline"]).strip().casefold() != airline:
        issues.append(f"Block row {row_number}: selected contract {contract_id} airline does not match the block.")
        return False
    departure = _date(value("itineraries.1.depDate"))
    start, end = _date(reference.get("startDate")), _date(reference.get("endDate"))
    if departure and start and departure.date() < start.date():
        issues.append(f"Block row {row_number}: departure is before contract {contract_id} start date.")
        return False
    if departure and end and departure.date() > end.date():
        issues.append(f"Block row {row_number}: departure is after contract {contract_id} end date.")
        return False
    return True


def _itinerary_city_count(headers: list[str], row: list[str]) -> int:
    cities: set[str] = set()
    route_field = re.compile(r"itineraries\d+(?:from|to)$")
    flight_airport_field = re.compile(r"itineraries\d+itineraryflights\d+(?:deparpcd|arrarpcd)$")
    for header, raw_value in zip(headers, row):
        key = norm(header)
        if route_field.fullmatch(key) or flight_airport_field.fullmatch(key):
            city = str(raw_value or "").strip().upper()
            if city:
                cities.add(city)
    return len(cities)


@app.post("/generate")
def generate_blocks(request: BlockRequest) -> dict[str, Any]:
    if not request.headers:
        return {"files": [], "issues": ["The AIS block template has no header row."], "rowCount": 0, "canDownload": False}
    try:
        profile = get_profile(request.profileCode)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    if profile is None:
        raise HTTPException(422, f"No approved Block Config profile exists for {request.profileCode.upper()}.")
    if profile.get("version") != request.profileVersion:
        raise HTTPException(409, "The selected Block Config changed after this draft was prepared. Reload the profile and rebuild the block rows.")
    # Ignore legacy profile values for fields now derived from procurement/contract data.
    profile_field_keys = set(profile.get("configFields", BLOCK_CONFIG_FIELDS))
    profile_fields = {key: value for key, value in profile.get("fields", {}).items() if key in profile_field_keys}
    saved_template_headers = (profile.get("template") or {}).get("headers")
    if saved_template_headers and request.headers != saved_template_headers:
        raise HTTPException(409, "The selected Block Config uses a different AIS template. Reload that profile's template and regenerate.")
    normalized = [norm(header) for header in request.headers]
    indexes = {key: index for index, key in enumerate(normalized)}
    issues: list[str] = []
    can_download = True
    duplicates = duplicate_headers(request.headers)
    if duplicates:
        issues.append("Duplicate headers detected: " + ", ".join(duplicates) + ". Confirm the exact upload template before continuing.")
        can_download = False
    if any(formula_like(header) for header in request.headers):
        issues.append("A template header contains formula-like text and is blocked for CSV safety.")
        can_download = False
    if "blockid" in normalized:
        issues.append("This is a downloaded AIS block export with blockId, not a pre-submit upload template.")
        can_download = False
    core = {"contractid", "airlinepnr", "itineraries1from", "itineraries1to", "itineraries1depdate",
            "itineraries1itineraryflights1mrkal", "itineraries1itineraryflights1fltno",
            "itineraries1itineraryflights1deparpcd", "itineraries1itineraryflights1arrarpcd",
            "pnrfareinfos1totseats", "pnrfareinfos1paxfaresadultbs"}
    if not core.issubset(normalized):
        issues.append("The block template is missing required contract, PNR, route, date, flight, airport, or seat columns.")
        can_download = False

    profile_by_key = {norm(key): str(value).strip() for key, value in profile_fields.items()}
    unknown = [header for header, key in zip(request.headers, normalized)
               if key not in profile_by_key and not source_owned(header) and not optional_field(header) and not derived_field(header)]
    if unknown:
        issues.append("Template fields need a source mapping or approved block configuration before export: " + ", ".join(unknown[:20]))
        can_download = False

    references: dict[str, dict[str, Any]] = {}
    for item in request.contractReferences:
        contract_id = str(item.get("id", "")).strip()
        if not contract_id:
            continue
        if contract_id in references:
            issues.append(f"Duplicate contract ID {contract_id} in the AIS contract result.")
            can_download = False
        references[contract_id] = item
    if not references:
        issues.append("AIS contract references are missing. Upload the post-submission contract result and rebuild.")
        can_download = False

    output_rows: list[list[str]] = []
    seen_blocks: set[tuple[str, str, str]] = set()
    for row_number, source_row in enumerate(request.rows, start=1):
        if len(source_row) != len(request.headers):
            issues.append(f"Block row {row_number} has {len(source_row)} values for {len(request.headers)} template columns.")
            can_download = False
            continue
        prepared = list(source_row)
        for column, key in enumerate(normalized):
            if key in profile_by_key and (not source_owned(request.headers[column]) or not str(prepared[column]).strip()):
                prepared[column] = profile_by_key[key]
            if formula_like(str(prepared[column])):
                issues.append(f"Block row {row_number}, {request.headers[column]}: formula-like cell content is blocked for CSV safety.")
                can_download = False
        output_rows.append(prepared)
        by_name = {key: prepared[index] for index, key in enumerate(normalized)}
        for field in ("contractid", "airlinepnr", "itineraries1from", "itineraries1to", "itineraries1depdate",
                      "itineraries1itineraryflights1mrkal", "itineraries1itineraryflights1fltno",
                      "itineraries1itineraryflights1deparpcd", "itineraries1itineraryflights1arrarpcd",
                      "pnrfareinfos1totseats", "pnrfareinfos1paxfaresadultbs"):
            if field in normalized and not by_name.get(field, "").strip():
                issues.append(f"Block row {row_number}: {request.headers[normalized.index(field)]} is blank.")
                can_download = False
        for column, (header, key) in enumerate(zip(request.headers, normalized)):
            if derived_field(header) and not optional_field(header) and not str(prepared[column]).strip():
                issues.append(f"Block row {row_number}: {header} could not be derived from the linked contract and itinerary.")
                can_download = False
        if references and not _contract_link_ok(prepared, indexes, references, row_number, issues):
            can_download = False
        linked_contract = references.get(by_name.get("contractid", "").strip(), {})
        for column, (header, key) in enumerate(zip(request.headers, normalized)):
            value = str(prepared[column]).strip()
            if key == "bookingstartdate":
                approved_start = str(linked_contract.get("startDate", "")).strip()
                if not approved_start or value != approved_start:
                    issues.append(f"Block row {row_number}: bookingStartDate must match the selected AIS contract start date.")
                    can_download = False
            elif key == "mmtproductclass" and value:
                city_count = _itinerary_city_count(request.headers, prepared)
                expected_product_class = f"Holiday#{city_count}" if city_count else ""
                if not re.fullmatch(r"Holiday#\d+", value, re.I) or (expected_product_class and value != expected_product_class):
                    issues.append(f"Block row {row_number}: mmtProductClass must be Holiday#{city_count}, based on the {city_count} distinct itinerary cities.")
                    can_download = False
            elif key.endswith("farefamily"):
                dummy = str(linked_contract.get("dummyContract", "")).strip().casefold()
                expected_family = "Tentative" if dummy in {"yes", "true", "1"} else "Smart Saver Fare" if dummy in {"no", "false", "0"} else ""
                if not expected_family or value != expected_family:
                    issues.append(f"Block row {row_number}: {header} must follow the Dummy setting on the selected AIS contract.")
                    can_download = False
        seats = by_name.get("pnrfareinfos1totseats", "").strip()
        if seats:
            try:
                count = float(seats)
                if not math.isfinite(count) or count <= 0 or not count.is_integer():
                    raise ValueError
            except ValueError:
                issues.append(f"Block row {row_number}: seat quantity must be a positive whole number.")
                can_download = False
        departure = by_name.get("itineraries1depdate", "").strip()
        if departure and _date(departure) is None:
            issues.append(f"Block row {row_number}: departure date is invalid; use DD/MM/YY or YYYY-MM-DD.")
            can_download = False
        for key, value in by_name.items():
            if key.endswith((".bs", ".tx", ".amnt")) or key.endswith("bs") or key.endswith("tx") or key.endswith("amnt"):
                if value.strip():
                    try:
                        amount = float(value)
                        if not math.isfinite(amount) or amount < 0:
                            raise ValueError
                    except ValueError:
                        issues.append(f"Block row {row_number}: {request.headers[normalized.index(key)]} must be a finite non-negative amount.")
                        can_download = False
        block_key = (by_name.get("contractid", "").strip(), by_name.get("airlinepnr", "").strip().upper(), departure)
        if block_key[1] and block_key in seen_blocks:
            issues.append(f"Block row {row_number}: duplicate contract, PNR, and departure-date combination.")
            can_download = False
        seen_blocks.add(block_key)

    if not request.rows:
        issues.append("No block rows were provided.")
        can_download = False
    result = {"files": [], "format": request.format, "issues": issues, "rowCount": len(request.rows),
              "profileCode": profile["code"], "profileVersion": profile["version"],
              "isDraft": True, "canDownload": can_download}
    if can_download:
        contract_index = normalized.index("contractid")
        grouped: dict[str, list[list[str]]] = {}
        for row in output_rows:
            grouped.setdefault(row[contract_index].strip(), []).append(row)
        expected_ids = {str(item.get("id", "")).strip() for item in request.contractReferences if str(item.get("id", "")).strip()}
        missing_ids = sorted(expected_ids - set(grouped))
        if missing_ids:
            issues.append("No procurement block rows matched these AIS contract IDs: " + ", ".join(missing_ids[:30]) + ". Check that the source contains departures for every contract.")
            can_download = False
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for file_number, (contract_id, rows) in enumerate(sorted(grouped.items()), start=1):
                if request.format == "xlsx":
                    content = base64.b64decode(xlsx_base64(request.headers, rows))
                else:
                    stream = io.StringIO(newline="")
                    writer = csv.writer(stream, lineterminator="\r\n")
                    writer.writerow(request.headers)
                    writer.writerows(rows)
                    content = ("\ufeff" + stream.getvalue()).encode("utf-8")
                safe_id = re.sub(r"[^A-Za-z0-9_-]+", "_", contract_id)[:70].strip("_") or "contract"
                file_name = f"airops-block-{safe_id}-{file_number}.{request.format}"
                result["files"].append({"contractId": contract_id, "fileName": file_name, "rowCount": len(rows)})
                bundle.writestr(file_name, content)
        if can_download:
            result["archiveFileName"] = "airops-block-files.zip"
            result["archiveBase64"] = base64.b64encode(archive.getvalue()).decode("ascii")
            result["contractCount"] = len(result["files"])
        else:
            result["files"] = []
        if can_download and len(result["files"]) > 1:
            result["issues"].append(f"Generated {len(result['files'])} separate files, one per contract ID, in a ZIP download.")
        result["canDownload"] = can_download
    return result
