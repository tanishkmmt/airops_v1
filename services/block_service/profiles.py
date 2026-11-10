"""Persistent, versioned block profiles, isolated from contract configuration."""
from __future__ import annotations

import json
import math
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from .schema import (
    BLOCK_CONFIG_FIELDS, BLOCK_FALLBACK_FIELDS, REQUIRED_BLOCK_CONFIG_FIELDS,
    derived_field, field_group, optional_field, source_owned,
)

SCHEMA_VERSION = 3
_LOCK = RLock()


def _path() -> Path:
    return Path(os.getenv("AIR_OPS_BLOCK_PROFILE_PATH", "var/block_profiles.json"))


def _read_document(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schemaVersion": SCHEMA_VERSION, "profiles": {}}
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Block profile store is unreadable; no profile data was changed.") from exc
    if not isinstance(document, dict) or not isinstance(document.get("profiles", {}), dict):
        raise RuntimeError("Block profile store has an invalid structure; no profile data was changed.")
    return document


def _write_document(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="block_profiles_", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(document, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if hasattr(os, "O_DIRECTORY"):
            directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _template_fields(profile: dict[str, Any] | None) -> list[str]:
    template = (profile or {}).get("template")
    if not template:
        return list(BLOCK_CONFIG_FIELDS)
    headers = {normalize_field(header) for header in template.get("headers", [])}
    static = [field for field in BLOCK_CONFIG_FIELDS if normalize_field(field) in headers]
    return list(dict.fromkeys([*static, *((profile or {}).get("dynamicFields") or [])]))


def _profile_payload(profile: dict[str, Any]) -> dict[str, Any]:
    result = dict(profile)
    fields = _template_fields(profile)
    result["configFields"] = fields
    result["fieldMetadata"] = config_field_metadata(fields)
    result["templateName"] = (profile.get("template") or {}).get("fileName", "")
    result["templateColumnCount"] = len((profile.get("template") or {}).get("headers", []))
    return result


def normalize_field(value: str) -> str:
    return "".join(char.casefold() for char in value if char.isalnum())


def list_profiles() -> list[dict[str, Any]]:
    path = _path()
    with _LOCK:
        document = _read_document(path)
        return [_profile_payload(item) for item in sorted(document.get("profiles", {}).values(), key=lambda item: item.get("code", ""))]


def get_profile(code: str) -> dict[str, Any] | None:
    normalized = code.strip().upper()
    return next((item for item in list_profiles() if item.get("code") == normalized), None)


def _validate_fields(fields: dict[str, Any], allowed_fields: list[str]) -> dict[str, str]:
    allowed = list(dict.fromkeys(allowed_fields))
    unknown = sorted(set(fields) - set(allowed))
    if unknown:
        raise ValueError("Unknown block configuration fields: " + ", ".join(unknown))
    cleaned = {key: str(fields.get(key, "")).strip() for key in allowed}
    too_long = [key for key, value in cleaned.items() if len(value) > 4_000]
    if too_long:
        raise ValueError("Block profile values exceed the 4,000-character limit: " + ", ".join(too_long))
    formula_like = [key for key, value in cleaned.items()
                    if value.lstrip()[:1] in {"=", "+", "@"}
                    or (value.lstrip().startswith("-") and not re.fullmatch(r"-\d+(?:\.\d+)?", value.lstrip()))]
    if formula_like:
        raise ValueError("Formula-like values are not allowed: " + ", ".join(formula_like))
    for key, value in cleaned.items():
        if not value:
            continue
        normalized = key.casefold()
        if normalized.endswith(".droolsbased") and value.casefold() not in {"true", "false"}:
            raise ValueError(f"{key} must be True or False.")
        if any(token in normalized for token in (".bs", ".tx", ".amnt", ".fareServices.".casefold() + "value")) or normalized.endswith(".value"):
            if normalized.endswith((".bs", ".tx", ".amnt", ".value")):
                try:
                    number = float(value)
                except ValueError as exc:
                    raise ValueError(f"{key} must be a non-negative number.") from exc
                if not math.isfinite(number) or number < 0:
                    raise ValueError(f"{key} must be a finite, non-negative number.")
    return cleaned


def import_preview(headers: list[str], rows: list[list[str]], fields: list[str]) -> dict[str, Any]:
    from services.validation import duplicate_headers, normalize_header

    duplicates = duplicate_headers(headers)
    if duplicates:
        raise ValueError("The reference file has duplicate headers: " + ", ".join(duplicates))
    indexes = {normalize_header(header): index for index, header in enumerate(headers)}
    suggested: dict[str, str] = {}
    conflicts: list[str] = []
    missing: list[str] = []
    for field in fields:
        index = indexes.get(normalize_header(field))
        values = {str(row[index]).strip() for row in rows if index is not None and index < len(row) and str(row[index]).strip()}
        if len(values) == 1:
            suggested[field] = next(iter(values))
        elif len(values) > 1:
            conflicts.append(field)
        else:
            missing.append(field)
    return {"fields": suggested, "conflicts": conflicts, "missing": missing,
            "consistentCount": len(suggested), "totalConfigFields": len(fields),
            "canApply": bool(suggested)}


def _validated_code(code: str) -> str:
    normalized = code.strip().upper()
    if len(normalized) > 16 or not re.fullmatch(r"BC\d+", normalized):
        raise ValueError("Block config name must use the BC1, BC2 format.")
    return normalized


def _version_history(previous: dict[str, Any]) -> list[dict[str, Any]]:
    history = list(previous.get("history", []))
    if previous.get("fields") or previous.get("template"):
        history.append({key: previous[key] for key in ("version", "fields", "dynamicFields", "template", "updatedAt", "updatedBy") if key in previous})
    return history[-20:]


def _save_document_profile(path: Path, document: dict[str, Any], normalized: str,
                           profile: dict[str, Any]) -> None:
    document.update({"schemaVersion": SCHEMA_VERSION})
    document.setdefault("profiles", {})[normalized] = profile
    _write_document(path, document)


def save_profile(code: str, fields: dict[str, Any], actor: str = "admin") -> dict[str, Any]:
    normalized = _validated_code(code)
    with _LOCK:
        path = _path()
        document = _read_document(path)
        previous = document.setdefault("profiles", {}).get(normalized, {})
        allowed = _template_fields(previous)
        cleaned = _validate_fields(fields, allowed)
        profile = {"code": normalized, "version": int(previous.get("version", 0)) + 1,
                   "schemaVersion": SCHEMA_VERSION, "fields": cleaned,
                   "dynamicFields": list(previous.get("dynamicFields", [])),
                   **({"template": previous["template"]} if previous.get("template") else {}),
                   "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "updatedBy": actor, "history": _version_history(previous)}
        _save_document_profile(path, document, normalized, profile)
    return _profile_payload(profile)


def save_template(code: str, headers: list[str], file_name: str, actor: str = "admin") -> dict[str, Any]:
    from services.validation import duplicate_headers, formula_like

    normalized = _validated_code(code)
    if not headers:
        raise ValueError("The block template has no header row.")
    duplicates = duplicate_headers(headers)
    if duplicates:
        raise ValueError("The block template has duplicate headers: " + ", ".join(duplicates))
    if any(formula_like(header) for header in headers):
        raise ValueError("Formula-like template headers are not allowed.")
    header_keys = {normalize_field(header) for header in headers}
    if "blockid" in header_keys:
        raise ValueError("Upload the pre-submit block template, not an AIS block result/export.")
    if not {"contractid", "airlinepnr"}.issubset(header_keys) or not any(key.startswith("itineraries1") for key in header_keys):
        raise ValueError("The block template must include contractId, airlinePnr, and itinerary fields.")
    dynamic = [header for header in headers
               if normalize_field(header) not in {normalize_field(field) for field in BLOCK_CONFIG_FIELDS}
               and not source_owned(header) and not optional_field(header) and not derived_field(header)]
    with _LOCK:
        path = _path()
        document = _read_document(path)
        previous = document.setdefault("profiles", {}).get(normalized, {})
        previous_values = previous.get("fields", {})
        allowed = [field for field in BLOCK_CONFIG_FIELDS if normalize_field(field) in header_keys]
        allowed.extend(dynamic)
        fields = {field: str(previous_values.get(field, "")).strip() for field in allowed}
        template = {"fileName": Path(file_name or "Block upload template").name[:255],
                    "headers": list(headers), "uploadedAt": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        profile = {"code": normalized, "version": int(previous.get("version", 0)) + 1,
                   "schemaVersion": SCHEMA_VERSION, "fields": fields, "dynamicFields": dynamic,
                   "template": template,
                   "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "updatedBy": actor, "history": _version_history(previous)}
        _save_document_profile(path, document, normalized, profile)
    return _profile_payload(profile)


def config_field_metadata(fields: list[str] | None = None) -> list[dict[str, str]]:
    def label(field: str) -> str:
        friendly = {
            "blockStatus": "Block status", "cabinClass": "Cabin class", "fareType": "Fare type",
            "inventoryType": "Inventory type", "loginCredentials": "Supplier login credentials",
            "underlyingSupplierName": "Underlying supplier", "underlyingCredentialId": "Supplier credential ID",
            "droolsBased": "Rules-engine based", "bs": "Base fare", "tx": "Tax",
            "amnt": "Tax amount", "nonRefundable": "Non-refundable",
            "fareClass": "Fare class", "cabinClass": "Cabin class", "fareFamily": "Fare family",
            "productClass": "Product class", "valueType": "Value type", "timeWindows": "Time windows",
        }
        match = re.match(r"pnrFareInfos\.\d+\.paxFares\.(ADULT|CHILD|INFANT)\.(.+)", field, re.I)
        if match:
            passenger = match.group(1).title()
            rest = match.group(2)
            service = re.match(r"fareServices\.([^.]+)\.(.+)", rest, re.I)
            if service:
                leaf = service.group(2).split(".")[-1]
                rest = service.group(1).replace("_", " ").title() + " · " + friendly.get(leaf, leaf)
            elif rest.startswith("taxBreakups."):
                rest = "Tax breakup · " + ("Amount" if rest.endswith("amnt") else rest.split(".")[-1].title())
            else:
                rest = {"bs": "Base fare", "tx": "Tax", "taxBreakups.1.amnt": "Tax amount"}.get(rest, rest)
            return f"{passenger} · {rest}"
        match = re.match(r"itineraries\.\d+\.itineraryFlights\.\d+\.([^.]+)\.(.+)", field, re.I)
        if match:
            passenger, rest = match.group(1).title(), match.group(2).split(".")[-1]
            rest = friendly.get(rest, re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", rest).replace("_", " ").title())
            return f"{passenger} · {rest}"
        leaf = field.split(".")[-1]
        leaf = friendly.get(leaf, re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", leaf).replace("_", " ").title())
        return leaf

    return [{"key": field, "group": field_group(field), "label": label(field),
             "required": field in REQUIRED_BLOCK_CONFIG_FIELDS,
             "description": ("Used only when procurement has no valid value; procurement always takes precedence."
                            if field in BLOCK_FALLBACK_FIELDS else "Optional approved default; leave blank when unknown or not applicable.")}
            for field in (fields if fields is not None else BLOCK_CONFIG_FIELDS)]
