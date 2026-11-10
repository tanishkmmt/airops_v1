from __future__ import annotations

import csv
import io
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from services.file_output import xlsx_base64
from services.request_models import ProfileValues, TableHeaders, TableRows
from services.validation import duplicate_headers, formula_like, normalize_header

from .departures_mapper import prepare_candidate_groups
from .profiles import PROFILE_FIELDS, TNC_FIELDS, get_profile, list_profiles, required_profile_fields, save_profile

app = FastAPI(title="AirOps contract service", docs_url=None, redoc_url=None)


class ContractRequest(BaseModel):
    headers: TableHeaders
    rows: TableRows
    airline: str = Field(min_length=1, max_length=8)
    format: Literal["csv", "xlsx"] = "csv"


class DepartureRequest(BaseModel):
    candidates: list[dict[str, Any]] = Field(max_length=5_000)
    airline: str = Field(min_length=1, max_length=8)


class ProfileRequest(BaseModel):
    fields: ProfileValues


class ProfileImportRequest(BaseModel):
    headers: TableHeaders
    rows: TableRows


normalize = normalize_header


@app.middleware("http")
async def no_store(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "contracts"}


@app.get("/profiles")
def profiles() -> dict[str, Any]:
    try:
        return {"profiles": list_profiles(), "fields": PROFILE_FIELDS, "tncFields": TNC_FIELDS}
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.get("/profiles/{airline}")
def airline_profile(airline: str) -> dict[str, Any]:
    try:
        profile = get_profile(airline)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    if profile is None:
        raise HTTPException(404, f"No approved profile exists for airline {airline.upper()}.")
    return profile


@app.put("/profiles/{airline}")
def put_airline_profile(airline: str, request: ProfileRequest) -> dict[str, Any]:
    try:
        return save_profile(airline, request.fields, "local user")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.post("/profiles/import-preview")
def profile_import_preview(request: ProfileImportRequest) -> dict[str, Any]:
    columns: dict[str, int] = {}
    for index, header in enumerate(request.headers):
        columns.setdefault(normalize(header), index)
    airline_i = columns.get("airline")
    airlines = sorted({row[airline_i].strip().upper() for row in request.rows if airline_i is not None and airline_i < len(row) and row[airline_i].strip()})
    if len(airlines) != 1:
        raise HTTPException(422, "The uploaded contract result must contain exactly one airline code.")
    fields: dict[str, str] = {}
    conflicts: list[str] = []
    for field in PROFILE_FIELDS:
        index = columns.get(normalize(field))
        values = sorted({row[index].strip() for row in request.rows if index is not None and index < len(row) and row[index].strip()})
        if len(values) > 1:
            conflicts.append(field)
        elif values:
            fields[field] = values[0]
    missing = [field for field in required_profile_fields(fields) if not fields.get(field)]
    return {"airline": airlines[0], "fields": fields, "conflicts": conflicts, "missing": missing, "canSave": not conflicts and not missing}


@app.post("/prepare")
def prepare_contract(request: DepartureRequest) -> dict[str, Any]:
    try:
        profile = get_profile(request.airline)
        if profile is None:
            raise HTTPException(404, f"No approved T&C profile exists for {request.airline.upper()}.")
        result = prepare_candidate_groups(request.candidates, profile, request.airline)
        result["isDraft"] = True
        return result
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.post("/generate")
def generate_contracts(request: ContractRequest) -> dict[str, Any]:
    try:
        profile = get_profile(request.airline)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    if profile is None:
        raise HTTPException(422, f"No approved Airline T&C profile exists for {request.airline.upper()}. Complete it in Configuration → Airline T&Cs before preparing contracts.")
    fields = profile.get("fields", {})
    missing_profile = [key for key in required_profile_fields(fields) if not str(fields.get(key, "")).strip()]
    if missing_profile:
        raise HTTPException(422, "The approved Airline T&C profile is incomplete: " + ", ".join(missing_profile))
    if not request.headers:
        return {"csv": "", "issues": ["The AIS contract template has no header row."], "rowCount": 0, "canDownload": False}
    duplicates = duplicate_headers(request.headers)
    issues: list[str] = []
    can_download = True
    if duplicates:
        issues.append("Duplicate template headers detected: " + ", ".join(duplicates) + ". Confirm the exact AIS template version before upload.")
        can_download = False
    if any(normalize(header) == "contractid" for header in request.headers):
        issues.append("Contract Id is generated by AIS after upload and must not be present in this contract upload file.")
        can_download = False
    if any(formula_like(header) for header in request.headers):
        issues.append("A template header contains formula-like text and is blocked for CSV safety.")
        can_download = False
    width = len(request.headers)
    normalized_headers = [normalize(h) for h in request.headers]
    profile_columns = {normalize(key): str(value).strip() for key, value in fields.items()}
    required_template = {"contractname", "journey1from", "journey1to", "journeytype", "airline"}
    if not required_template.issubset(normalized_headers):
        issues.append("The selected file is missing core headers from the supplied AIS contract upload template.")
        can_download = False
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(request.headers)
    output_rows: list[list[str]] = []
    for index, row in enumerate(request.rows, start=1):
        if len(row) != width:
            issues.append(f"Contract row {index} has {len(row)} values for {width} template columns.")
            can_download = False
            continue
        for col_i, value in enumerate(row):
            if formula_like(str(value)):
                issues.append(f"Contract row {index}, {request.headers[col_i]}: formula-like cell content is blocked for CSV safety.")
                can_download = False
        prepared = list(row)
        for col_i, header in enumerate(request.headers):
            normalized = normalize(header)
            if normalized == "airline":
                if prepared[col_i].strip() and prepared[col_i].strip().upper() != request.airline.upper():
                    issues.append(f"Contract row {index}: airline value conflicts with selected profile {request.airline.upper()}.")
                    can_download = False
                prepared[col_i] = request.airline.upper()
            elif normalized in profile_columns:
                # Approved constants and terms are authoritative for this airline.
                prepared[col_i] = profile_columns[normalized]
        writer.writerow(prepared)
        output_rows.append(prepared)
        for col_i, header in enumerate(request.headers):
            if normalize(header) in {"contractname", "journey1from", "journey1to", "journeytype", "airline", "vendorid"} and not str(prepared[col_i]).strip():
                issues.append(f"Contract row {index}: {header} is blank. Requiredness should be confirmed with AIS.")
    if not request.rows:
        issues.append("No contract rows were provided.")
        can_download = False
    result = {"csv": "", "fileBase64": "", "format": request.format, "issues": issues, "rowCount": len(request.rows), "isDraft": True, "canDownload": can_download}
    if can_download:
        if request.format == "xlsx":
            result["fileBase64"] = xlsx_base64(request.headers, output_rows)
        else:
            result["csv"] = output.getvalue()
    return result
