"""Deterministic contract candidates from airline Departures-style tables."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

from .profiles import PROFILE_FIELDS, required_profile_fields

AIS_CONTRACT_HEADERS = [
    "contractName", "journey.1.from", "journey.1.to", "journey.2.from", "journey.2.to",
    "journeyType", "airline", "contractStartDate", "contractEndDate", "dummyContract",
    "isTicketingRequired", "vendorId", "toEmails", "toNames", "ccEmails", "tnc.applicable",
    "tnc.utilizationPercentage", "tnc.dummyToRealPNRDeadline", "tnc.saleCutOffDeadline",
    "tnc.namingDeadline", "tnc.ticketingDeadline", "tnc.minSeatsToOperate", "tnc.advancePaidAmount",
    "tnc.advancePaidPercentage", "tnc.safeReleaseDeadline", "tnc.finalReleaseDeadline",
    "tnc.nilCancellationPercentage", "tnc.contractPenaltyClause.penaltyType",
    "tnc.contractPenaltyClause.basePenalty", "tnc.contractPenaltyClause.penalty", "optionalTicketing",
]


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def _date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        try:
            serial = float(text)
            if 1 <= serial <= 100000:
                return (datetime(1899, 12, 30) + timedelta(days=serial)).date()
        except (OverflowError, ValueError):
            return None
    for fmt in ("%d/%m/%y %H:%M", "%d/%m/%Y %H:%M", "%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d-%b-%Y", "%d-%b-%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _fmt(value: date, end: bool = False) -> str:
    return value.strftime("%d/%m/%y") + (" 23:59" if end else " 00:01")


def _name_date(value: date) -> str:
    return value.strftime("%b%Y").upper()


def _contract_creation_date() -> date:
    india_time = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(india_time).date()


def _contract_name(airline: str, from1: str, to1: str, to2: str, start: date, end: date) -> str:
    route = f"{from1}-{to1}" + (f"-{to2}" if to2 else "")
    return f"{airline} {route} {_name_date(start)}-{_name_date(end)}"


def prepare_candidate_groups(candidates: list[dict[str, Any]], profile: dict[str, Any], requested_airline: str) -> dict[str, Any]:
    airline = requested_airline.strip().upper()
    fields = profile.get("fields", {})
    missing = [key for key in required_profile_fields(fields) if not str(fields.get(key, "")).strip()]
    if missing:
        raise ValueError("The selected airline profile is incomplete: " + ", ".join(missing))
    selected = [item for item in candidates if str(item.get("airline", "")).upper() == airline]
    if not selected:
        raise ValueError(f"No complete Departures rows matched airline {airline}.")
    created_on = _contract_creation_date()
    expired = [item for item in selected if (end := _date(item.get("endDate"))) and end < created_on]
    selected = [item for item in selected if (end := _date(item.get("endDate"))) and end >= created_on]
    if not selected:
        raise ValueError(f"No {airline} route group has a departure on or after the contract creation date.")
    records = []
    for item in selected:
        end = _date(item.get("endDate"))
        if not end:
            continue
        start = created_on
        route_type = str(item.get("journeyType", "OW")).upper()
        from1, to1 = str(item.get("journey1From", "")).upper(), str(item.get("journey1To", "")).upper()
        from2, to2 = str(item.get("journey2From", "")).upper(), str(item.get("journey2To", "")).upper()
        if not from1 or not to1:
            continue
        has_second_leg = bool(from2 and to2)
        name = _contract_name(airline, from1, to1, to2 if has_second_leg else "", start, end)
        values = {header: "" for header in AIS_CONTRACT_HEADERS}
        values.update({"contractName": name, "journey.1.from": from1, "journey.1.to": to1,
                       "journey.2.from": from2 if has_second_leg else "",
                       "journey.2.to": to2 if has_second_leg else "",
                       "journeyType": route_type, "airline": airline,
                       "contractStartDate": _fmt(start), "contractEndDate": _fmt(end, True)})
        values.update({field: str(fields.get(field, "")).strip() for field in PROFILE_FIELDS})
        records.append(values)
    if not records:
        raise ValueError("Matched Departures groups have no usable contract date range or route.")
    status_counts: dict[str, int] = {}
    for item in selected:
        for status, count in item.get("statusCounts", {}).items():
            status_counts[status] = status_counts.get(status, 0) + int(count)
    cancelled = sum(count for status, count in status_counts.items() if status.casefold() in {"cancelled", "canceled"})
    return {"headers": AIS_CONTRACT_HEADERS, "rows": [[record[h] for h in AIS_CONTRACT_HEADERS] for record in records],
            "records": records, "rowCount": len(records), "matchedSourceRows": sum(int(x.get("sourceRows", 0)) for x in selected),
            "profileVersion": profile.get("version"), "statusCounts": status_counts, "cancelledRows": cancelled,
            "issues": ["Contract start date is the creation date; contract end date is the latest departure date for each route group.",
                       *([f"{len(expired)} historical route group(s) were excluded because their last departure is before the contract creation date."] if expired else []),
                       *([f"{cancelled} cancelled booking row(s) are present in matched groups; verify whether they should count toward contract date ranges before export."] if cancelled else [])]}
