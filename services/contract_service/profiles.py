"""Versioned airline configuration storage, separate from transient case files.

The JSON repository is a replaceable adapter for this single-instance prototype.
It stores only approved configuration, never procurement uploads or case outputs.
"""
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

PROFILE_FIELDS = [
    "dummyContract", "isTicketingRequired", "vendorId", "toEmails", "toNames", "ccEmails",
    "tnc.applicable", "tnc.utilizationPercentage", "tnc.dummyToRealPNRDeadline",
    "tnc.saleCutOffDeadline", "tnc.namingDeadline", "tnc.ticketingDeadline",
    "tnc.minSeatsToOperate", "tnc.advancePaidAmount", "tnc.advancePaidPercentage",
    "tnc.safeReleaseDeadline", "tnc.finalReleaseDeadline", "tnc.nilCancellationPercentage",
    "tnc.contractPenaltyClause.penaltyType", "tnc.contractPenaltyClause.basePenalty",
    "tnc.contractPenaltyClause.penalty", "optionalTicketing",
]
TNC_FIELDS = [field for field in PROFILE_FIELDS if field.startswith("tnc.")]
_LOCK = RLock()


def _path() -> Path:
    return Path(os.getenv("AIR_OPS_PROFILE_PATH", "var/airline_profiles.json"))


def list_profiles() -> list[dict[str, Any]]:
    path = _path()
    with _LOCK:
        if not path.exists():
            return []
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("Airline profile store is unreadable; no profile data was changed.") from exc
        return sorted(content.get("profiles", {}).values(), key=lambda item: item["airline"].casefold())


def get_profile(airline: str) -> dict[str, Any] | None:
    code = airline.strip().upper()
    return next((item for item in list_profiles() if item["airline"].upper() == code), None)


def required_profile_fields(fields: dict[str, Any]) -> list[str]:
    required = list(PROFILE_FIELDS)
    if str(fields.get("dummyContract", "")).strip().casefold() == "no":
        required.remove("tnc.dummyToRealPNRDeadline")
    return required


def save_profile(airline: str, fields: dict[str, Any], actor: str = "admin") -> dict[str, Any]:
    code = airline.strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{1,8}", code):
        raise ValueError("Enter a valid airline code (1–8 characters).")
    cleaned = {key: str(fields.get(key, "")).strip() for key in PROFILE_FIELDS}
    missing = [key for key in required_profile_fields(cleaned) if not cleaned[key]]
    if missing:
        raise ValueError("Complete every profile field before saving: " + ", ".join(missing))
    too_long = [key for key, value in cleaned.items() if len(value) > 4_000]
    if too_long:
        raise ValueError("Profile values exceed the 4,000-character limit: " + ", ".join(too_long))
    unsafe = [key for key, value in cleaned.items() if value.lstrip() and (value.lstrip()[0] in "=+@" or (value.lstrip()[0] == "-" and not re.fullmatch(r"-\d+(?:\.\d+)?", value.lstrip())))]
    if unsafe:
        raise ValueError("Formula-like values are not allowed in airline profile fields: " + ", ".join(unsafe))
    for key in ("tnc.utilizationPercentage", "tnc.advancePaidPercentage", "tnc.nilCancellationPercentage"):
        try:
            number = float(cleaned[key])
        except ValueError as exc:
            raise ValueError(f"{key} must be a number from 0 to 100.") from exc
        if not math.isfinite(number) or not 0 <= number <= 100:
            raise ValueError(f"{key} must be between 0 and 100.")
    for key in ("tnc.minSeatsToOperate", "tnc.advancePaidAmount"):
        try:
            number = float(cleaned[key])
        except ValueError as exc:
            raise ValueError(f"{key} must be a non-negative number.") from exc
        if not math.isfinite(number) or number < 0:
            raise ValueError(f"{key} must be a non-negative number.")
    if not cleaned["vendorId"]:
        raise ValueError("Vendor ID is required.")
    with _LOCK:
        path = _path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            try:
                document = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeError("Airline profile store is unreadable; no profile data was changed.") from exc
        else:
            document = {"profiles": {}}
        previous = document.setdefault("profiles", {}).get(code, {})
        history = list(previous.get("history", []))
        if previous.get("fields"):
            history.append({"version": previous["version"], "fields": previous["fields"], "updatedAt": previous["updatedAt"], "updatedBy": previous["updatedBy"]})
        profile = {
            "airline": code,
            "version": int(previous.get("version", 0)) + 1,
            "fields": cleaned,
            "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "updatedBy": actor,
            "history": history[-20:],
        }
        document["profiles"][code] = profile
        fd, temporary = tempfile.mkstemp(prefix="airline_profiles_", suffix=".tmp", dir=path.parent)
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
    return profile
