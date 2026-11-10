"""AIS block field ownership and reusable profile requirements.

Profile fields are the values repeated across the supplied 32-row Block2
reference that are not safely derived from procurement or AIS contract data.
Known optional columns are empty in that reference and may remain blank.
"""
from __future__ import annotations
import re

BLOCK_PROFILE_VALUE_FIELDS = ['blockStatus',
 'cabinClass',
 'currency',
 'fareType',
 'inventoryType',
 'loginCredentials',
 'itineraries.1.itineraryFlights.1.ADULT.fareClass',
 'itineraries.1.itineraryFlights.1.ADULT.cabinClass',
 'itineraries.1.itineraryFlights.1.ADULT.productClass',
 'itineraries.2.itineraryFlights.1.ADULT.productClass',
 'pnrFareInfos.1.underlyingSupplierName',
 'pnrFareInfos.1.underlyingCredentialId',
 'pnrFareInfos.1.paxFares.ADULT.tx',
 'pnrFareInfos.1.paxFares.ADULT.taxBreakups.1.amnt',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.AMENDABLE.droolsBased',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.AMENDABLE.status',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.AMENDABLE.value',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.AMENDABLE.valueType',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.AMENDABLE.unit',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.AMENDABLE.timeWindows.1.airlinePenalty.nonRefundable',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.REFUNDABLE.droolsBased',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.REFUNDABLE.status',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.REFUNDABLE.value',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.REFUNDABLE.valueType',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.REFUNDABLE.unit',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.REFUNDABLE.timeWindows.1.airlinePenalty.nonRefundable',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.CABIN_BAGGAGE_ALLOWANCE.droolsBased',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.CABIN_BAGGAGE_ALLOWANCE.status',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.CABIN_BAGGAGE_ALLOWANCE.value',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.CABIN_BAGGAGE_ALLOWANCE.valueType',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.CABIN_BAGGAGE_ALLOWANCE.unit',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.CHECKIN_BAGGAGE_ALLOWANCE.droolsBased',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.CHECKIN_BAGGAGE_ALLOWANCE.status',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.CHECKIN_BAGGAGE_ALLOWANCE.value',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.CHECKIN_BAGGAGE_ALLOWANCE.valueType',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.CHECKIN_BAGGAGE_ALLOWANCE.unit',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.MEAL.droolsBased',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.MEAL.status',
 'pnrFareInfos.1.paxFares.CHILD.tx',
 'pnrFareInfos.1.paxFares.CHILD.taxBreakups.1.amnt',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.AMENDABLE.droolsBased',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.AMENDABLE.status',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.AMENDABLE.value',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.AMENDABLE.valueType',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.AMENDABLE.unit',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.AMENDABLE.timeWindows.1.airlinePenalty.nonRefundable',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.REFUNDABLE.droolsBased',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.REFUNDABLE.status',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.REFUNDABLE.value',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.REFUNDABLE.valueType',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.REFUNDABLE.unit',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.REFUNDABLE.timeWindows.1.airlinePenalty.nonRefundable',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.CABIN_BAGGAGE_ALLOWANCE.droolsBased',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.CABIN_BAGGAGE_ALLOWANCE.status',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.CABIN_BAGGAGE_ALLOWANCE.value',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.CABIN_BAGGAGE_ALLOWANCE.valueType',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.CABIN_BAGGAGE_ALLOWANCE.unit',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.CHECKIN_BAGGAGE_ALLOWANCE.droolsBased',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.CHECKIN_BAGGAGE_ALLOWANCE.status',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.CHECKIN_BAGGAGE_ALLOWANCE.value',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.CHECKIN_BAGGAGE_ALLOWANCE.valueType',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.CHECKIN_BAGGAGE_ALLOWANCE.unit',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.MEAL.droolsBased',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.MEAL.status',
 'pnrFareInfos.1.paxFares.INFANT.bs',
 'pnrFareInfos.1.paxFares.INFANT.tx',
 'pnrFareInfos.1.paxFares.INFANT.taxBreakups.1.amnt',
 'pnrFareInfos.1.paxFares.INFANT.fareServices.AMENDABLE.droolsBased',
 'pnrFareInfos.1.paxFares.INFANT.fareServices.AMENDABLE.status',
 'pnrFareInfos.1.paxFares.INFANT.fareServices.AMENDABLE.value',
 'pnrFareInfos.1.paxFares.INFANT.fareServices.AMENDABLE.valueType',
 'pnrFareInfos.1.paxFares.INFANT.fareServices.AMENDABLE.unit',
 'pnrFareInfos.1.paxFares.INFANT.fareServices.AMENDABLE.timeWindows.1.airlinePenalty.nonRefundable',
 'pnrFareInfos.1.paxFares.INFANT.fareServices.REFUNDABLE.droolsBased',
 'pnrFareInfos.1.paxFares.INFANT.fareServices.REFUNDABLE.status',
 'pnrFareInfos.1.paxFares.INFANT.fareServices.REFUNDABLE.value',
 'pnrFareInfos.1.paxFares.INFANT.fareServices.REFUNDABLE.valueType',
 'pnrFareInfos.1.paxFares.INFANT.fareServices.REFUNDABLE.unit',
 'pnrFareInfos.1.paxFares.INFANT.fareServices.REFUNDABLE.timeWindows.1.airlinePenalty.nonRefundable',
 'pnrFareInfos.1.paxFares.INFANT.fareServices.CABIN_BAGGAGE_ALLOWANCE.droolsBased',
 'pnrFareInfos.1.paxFares.INFANT.fareServices.CABIN_BAGGAGE_ALLOWANCE.status',
 'pnrFareInfos.1.paxFares.INFANT.fareServices.CABIN_BAGGAGE_ALLOWANCE.value',
 'pnrFareInfos.1.paxFares.INFANT.fareServices.CABIN_BAGGAGE_ALLOWANCE.valueType',
 'pnrFareInfos.1.paxFares.INFANT.fareServices.CABIN_BAGGAGE_ALLOWANCE.unit',
 'pnrFareInfos.1.paxFares.INFANT.fareServices.CHECKIN_BAGGAGE_ALLOWANCE.droolsBased',
 'pnrFareInfos.1.paxFares.INFANT.fareServices.CHECKIN_BAGGAGE_ALLOWANCE.status',
 'pnrFareInfos.1.paxFares.INFANT.fareServices.CHECKIN_BAGGAGE_ALLOWANCE.value',
 'pnrFareInfos.1.paxFares.INFANT.fareServices.CHECKIN_BAGGAGE_ALLOWANCE.valueType',
 'pnrFareInfos.1.paxFares.INFANT.fareServices.CHECKIN_BAGGAGE_ALLOWANCE.unit',
 'pnrFareInfos.1.paxFares.INFANT.fareServices.MEAL.droolsBased',
 'pnrFareInfos.1.paxFares.INFANT.fareServices.MEAL.status',
 'itineraries.1.itineraryFlights.1.CHILD.fareClass',
 'itineraries.1.itineraryFlights.1.CHILD.cabinClass',
 'itineraries.1.itineraryFlights.1.INFANT.fareClass',
 'itineraries.1.itineraryFlights.1.INFANT.cabinClass']

# Values derived from source/contract facts are never user-maintained profile data.
BLOCK_PROFILE_VALUE_FIELDS = [
    field for field in BLOCK_PROFILE_VALUE_FIELDS
    if field.casefold() not in {
        "bookingstartdate", "mmtproductclass",
        "customerticketingdeadlinetype", "customerticketingdeadline",
    }
    and not re.search(r"\.farefamily$", field, re.I)
]

# Child base fare is passenger-specific and is not available in the supported
# procurement summary columns, so it remains an approved Block Config value.
BLOCK_PROFILE_VALUE_FIELDS.append('pnrFareInfos.1.paxFares.CHILD.bs')

BLOCK_FALLBACK_FIELDS: list[str] = []
BLOCK_CONFIG_FIELDS = [*BLOCK_PROFILE_VALUE_FIELDS, *BLOCK_FALLBACK_FIELDS]
REQUIRED_BLOCK_CONFIG_FIELDS: list[str] = []

KNOWN_OPTIONAL_FIELDS = ['mmtProductClass',
 'itineraries.1.itineraryFlights.1.freeSeatPreferences.MIDDLE.price',
 'itineraries.1.itineraryFlights.1.ADULT.fareBasis',
 'itineraries.1.itineraryFlights.1.CHILD.fareBasis',
 'itineraries.1.itineraryFlights.1.CHILD.productClass',
 'itineraries.1.itineraryFlights.1.tchStp.1.durInMins',
 'itineraries.1.itineraryFlights.1.tchStp.1.locInfo.arpCd',
 'itineraries.1.itineraryFlights.1.tchStp.1.depTime',
 'itineraries.1.itineraryFlights.1.tchStp.1.arrTime',
 'itineraries.2.itineraryFlights.1.tchStp.1.durInMins',
 'itineraries.2.itineraryFlights.1.tchStp.1.locInfo.arpCd',
 'itineraries.2.itineraryFlights.1.tchStp.1.depTime',
 'itineraries.2.itineraryFlights.1.tchStp.1.arrTime',
 'itineraries.2.itineraryFlights.1.freeSeatPreferences.MIDDLE.price',
 'itineraries.2.itineraryFlights.1.ADULT.fareClass',
 'itineraries.2.itineraryFlights.1.ADULT.fareBasis',
 'itineraries.2.itineraryFlights.1.ADULT.cabinClass',
 'itineraries.2.itineraryFlights.1.CHILD.fareClass',
 'itineraries.2.itineraryFlights.1.CHILD.fareBasis',
 'itineraries.2.itineraryFlights.1.CHILD.cabinClass',
 'itineraries.2.itineraryFlights.1.CHILD.productClass',
 'itineraries.2.itineraryFlights.1.CHILD.fareFamily',
 'pnrFareInfos.1.paxFares.ADULT.taxBreakups.1.code',
 'pnrFareInfos.1.paxFares.ADULT.taxBreakups.1.msg',
 'pnrFareInfos.1.paxFares.CHILD.taxBreakups.1.code',
 'pnrFareInfos.1.paxFares.CHILD.taxBreakups.1.msg',
 'pnrFareInfos.1.markupSlabs',
 'pnrFareInfos.1.staggeredSlabs',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.AMENDABLE.timeWindows.1.fromTimeWindow',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.AMENDABLE.timeWindows.1.toTimeWindow',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.AMENDABLE.timeWindows.1.airlinePenalty.cancellationPenalty',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.REFUNDABLE.timeWindows.1.fromTimeWindow',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.REFUNDABLE.timeWindows.1.toTimeWindow',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.REFUNDABLE.timeWindows.1.airlinePenalty.cancellationPenalty',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.CHECKIN_BAGGAGE_ALLOWANCE.conversionInfo.unit',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.CHECKIN_BAGGAGE_ALLOWANCE.conversionInfo.value',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.CHECKIN_BAGGAGE_ALLOWANCE.conversionInfo.maxAllowancePerPiece',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.MEAL.value',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.MEAL.valueType',
 'pnrFareInfos.1.paxFares.ADULT.fareServices.MEAL.text',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.AMENDABLE.timeWindows.1.fromTimeWindow',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.AMENDABLE.timeWindows.1.toTimeWindow',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.AMENDABLE.timeWindows.1.airlinePenalty.cancellationPenalty',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.REFUNDABLE.timeWindows.1.fromTimeWindow',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.REFUNDABLE.timeWindows.1.toTimeWindow',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.REFUNDABLE.timeWindows.1.airlinePenalty.cancellationPenalty',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.MEAL.value',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.MEAL.valueType',
 'pnrFareInfos.1.paxFares.CHILD.fareServices.MEAL.text',
 'aggressiveDiscountStartDate',
 'unsoldInventoryPenalty']

SOURCE_FIELDS = {
    "contractid", "airlinepnr", "supplierpnr", "itineraries1from", "itineraries1to",
    "itineraries1depdate", "itineraries2from", "itineraries2to", "itineraries2depdate",
    "pnrfareinfos1totseats", "pnrfareinfos1paxfaresadultbs",
}
FLIGHT_FIELD_TOKENS = ("mrkal", "opral", "fltno", "arcrftyp", "deparpcd", "depTrml",
                       "arrarpcd", "arrtrml", "deptime", "arrtime", "durinmins")

def normalize_field(header: str) -> str:
    return "".join(char.casefold() for char in header if char.isalnum())

def source_owned(header: str) -> bool:
    key = normalize_field(header)
    if key in SOURCE_FIELDS:
        return True
    return key.startswith("itineraries") and "itineraryflights" in key and any(token.casefold() in key for token in FLIGHT_FIELD_TOKENS)

def optional_field(header: str) -> bool:
    key = normalize_field(header)
    return any(normalize_field(field) == key for field in KNOWN_OPTIONAL_FIELDS)

def derived_field(header: str) -> bool:
    key = normalize_field(header)
    return key in {
        "bookingstartdate", "mmtproductclass",
        "customerticketingdeadlinetype", "customerticketingdeadline",
    } or (
        key.startswith("itineraries") and key.endswith("farefamily")
    )

def field_group(header: str) -> str:
    key = header.casefold()
    if key in {"bookingstartdate", "customerticketingdeadline", "customerticketingdeadlinetype"}:
        return "Block timing and ticketing"
    fare = re.match(r"pnrFareInfos\.\d+\.paxFares\.(ADULT|CHILD|INFANT)\.(.+)", header, re.I)
    if fare:
        passenger, rest = fare.group(1).title(), fare.group(2)
        service = re.match(r"fareServices\.([^.]+)", rest, re.I)
        if service:
            service_name = {
                "AMENDABLE": "Changes", "REFUNDABLE": "Cancellations",
                "CABIN_BAGGAGE_ALLOWANCE": "Cabin baggage", "CHECKIN_BAGGAGE_ALLOWANCE": "Checked baggage",
                "MEAL": "Meals",
            }.get(service.group(1).upper(), service.group(1).replace("_", " ").title())
            return f"{passenger} · {service_name}"
        return f"{passenger} · Fare and taxes"
    if key.startswith("itineraries."):
        passenger = next((p.title() for p in ("adult", "child", "infant") if f".{p}." in key), None)
        return f"{passenger} · Flight class defaults" if passenger else "Flight itinerary defaults"
    return "Block-wide defaults"
