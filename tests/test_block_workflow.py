from __future__ import annotations

import tempfile
import unittest
import csv
import io
import base64
import zipfile
from unittest.mock import patch

from services.block_service.main import BlockRequest, generate_blocks
from services.block_service.profiles import BLOCK_CONFIG_FIELDS, import_preview, save_profile


def valid_fields() -> dict[str, str]:
    fields = {key: "1" for key in BLOCK_CONFIG_FIELDS}
    fields["blockStatus"] = "ACTIVE"
    for key in list(fields):
        lowered = key.casefold()
        if lowered.endswith(".droolsbased"):
            fields[key] = "False"
        elif lowered.endswith((".bs", ".tx", ".amnt", ".value")):
            fields[key] = "0"
    return fields


def request_for(rows: list[list[str]] | None = None, headers: list[str] | None = None, **overrides) -> BlockRequest:
    base_headers = ["contractId", "airlinePnr", "itineraries.1.from", "itineraries.1.to",
                    "itineraries.1.depDate", "itineraries.1.itineraryFlights.1.mrkAl",
                    "itineraries.1.itineraryFlights.1.fltNo", "itineraries.1.itineraryFlights.1.depArpCd",
                    "itineraries.1.itineraryFlights.1.arrArpCd", "pnrFareInfos.1.totSeats",
                    "pnrFareInfos.1.paxFares.ADULT.bs", "pnrFareInfos.1.paxFares.CHILD.bs", "blockStatus"]
    base_rows = [["contract-1", "PNR123", "BOM", "BKK", "15/12/26", "AI", "2354", "BOM", "BKK", "10", "16203", "16203", "ACTIVE"]]
    values = {"headers": headers or base_headers, "rows": rows or base_rows,
              "profileCode": "BC1", "profileVersion": 1,
              "contractReferences": [{"id": "contract-1", "airline": "AI", "startDate": "28/10/26 00:01",
                                      "endDate": "31/12/26 23:59", "routes": [{"from": "BOM", "to": "BKK"}]}]}
    values.update(overrides)
    return BlockRequest(**values)


class BlockWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict("os.environ", {"AIR_OPS_BLOCK_PROFILE_PATH": f"{self.temp.name}/block_profiles.json"})
        self.env.start()
        save_profile("BC1", valid_fields())

    def tearDown(self) -> None:
        self.env.stop()
        self.temp.cleanup()

    def test_profile_import_uses_only_consistent_nonblank_values(self) -> None:
        field = BLOCK_CONFIG_FIELDS[0]
        result = import_preview([field, "airlinePnr"], [["ACTIVE", "PNR001"], ["ACTIVE", "PNR002"]], [field])
        self.assertEqual(result["fields"][field], "ACTIVE")
        self.assertEqual(result["consistentCount"], 1)

    def test_procurement_adult_fare_wins_and_child_fare_comes_from_profile(self) -> None:
        result = generate_blocks(request_for(rows=[
            ["contract-1", "PNR123", "BOM", "BKK", "15/12/26", "AI", "2354", "BOM", "BKK", "10", "16203", "", "client-value"]
        ]))
        self.assertTrue(result["canDownload"], result["issues"])
        archive = zipfile.ZipFile(io.BytesIO(base64.b64decode(result["archiveBase64"])))
        with archive.open(result["files"][0]["fileName"]) as stream:
            data = next(csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8-sig")))
        self.assertEqual(data["pnrFareInfos.1.paxFares.ADULT.bs"], "16203")
        self.assertEqual(data["pnrFareInfos.1.paxFares.CHILD.bs"], "0")

    def test_adult_base_fare_is_not_a_block_profile_field(self) -> None:
        adult_base_fare = "pnrFareInfos.1.paxFares.ADULT.bs"
        self.assertNotIn(adult_base_fare, BLOCK_CONFIG_FIELDS)
        with self.assertRaisesRegex(ValueError, "Unknown block configuration fields"):
            save_profile("BC2", {adult_base_fare: ""})

    def test_generation_splits_and_applies_profile_value(self) -> None:
        request = request_for(rows=[
            ["contract-1", "PNR123", "BOM", "BKK", "15/12/26", "AI", "2354", "BOM", "BKK", "10", "16203", "16203", "client-value"],
            ["contract-2", "PNR456", "BOM", "BKK", "16/12/26", "AI", "2354", "BOM", "BKK", "10", "16203", "16203", "client-value"],
        ], contractReferences=[
            {"id": "contract-1", "airline": "AI", "routes": [{"from": "BOM", "to": "BKK"}]},
            {"id": "contract-2", "airline": "AI", "routes": [{"from": "BOM", "to": "BKK"}]},
        ])
        result = generate_blocks(request)
        self.assertTrue(result["canDownload"], result["issues"])
        self.assertEqual([item["contractId"] for item in result["files"]], ["contract-1", "contract-2"])
        archive = zipfile.ZipFile(io.BytesIO(base64.b64decode(result["archiveBase64"])))
        with archive.open(result["files"][0]["fileName"]) as stream:
            content = stream.read().decode("utf-8-sig")
        self.assertIn("ACTIVE", content)
        self.assertNotIn("client-value", content)

    def test_product_class_uses_distinct_itinerary_city_count(self) -> None:
        headers = ["contractId", "airlinePnr", "itineraries.1.from", "itineraries.1.to",
                   "itineraries.1.depDate", "itineraries.1.itineraryFlights.1.mrkAl",
                   "itineraries.1.itineraryFlights.1.fltNo", "itineraries.1.itineraryFlights.1.depArpCd",
                   "itineraries.1.itineraryFlights.1.arrArpCd", "itineraries.1.itineraryFlights.2.depArpCd",
                   "itineraries.1.itineraryFlights.2.arrArpCd", "pnrFareInfos.1.totSeats",
                   "pnrFareInfos.1.paxFares.ADULT.bs", "mmtProductClass"]
        row = ["contract-1", "PNR123", "BOM", "DEL", "15/12/26", "AI", "2354", "BOM", "BKK",
               "BKK", "DEL", "10", "16203", "Holiday#3"]
        references = [{"id": "contract-1", "airline": "AI", "startDate": "28/10/26 00:01",
                       "endDate": "31/12/26 23:59", "routes": [{"from": "BOM", "to": "DEL"}]}]
        result = generate_blocks(request_for(headers=headers, rows=[row], contractReferences=references))
        self.assertTrue(result["canDownload"], result["issues"])

        row[-1] = "Holiday#2"
        result = generate_blocks(request_for(headers=headers, rows=[row], contractReferences=references))
        self.assertFalse(result["canDownload"])
        self.assertTrue(any("mmtProductClass must be Holiday#3" in issue for issue in result["issues"]))

    def test_wrong_contract_route_blocks_export(self) -> None:
        request = request_for(contractReferences=[{"id": "contract-1", "airline": "AI",
                                                  "routes": [{"from": "DEL", "to": "BKK"}]}])
        result = generate_blocks(request)
        self.assertFalse(result["canDownload"])
        self.assertTrue(any("does not include route" in issue for issue in result["issues"]))

    def test_departure_outside_contract_dates_blocks_export(self) -> None:
        request = request_for(contractReferences=[{"id": "contract-1", "airline": "AI",
                                                  "startDate": "01/01/27", "endDate": "31/01/27",
                                                  "routes": [{"from": "BOM", "to": "BKK"}]}])
        result = generate_blocks(request)
        self.assertFalse(result["canDownload"])
        self.assertTrue(any("before contract" in issue for issue in result["issues"]))

    def test_unknown_template_header_blocks_export(self) -> None:
        request = request_for(headers=["contractId", "airlinePnr", "itineraries.1.from", "itineraries.1.to",
                                       "itineraries.1.depDate", "itineraries.1.itineraryFlights.1.mrkAl",
                                       "itineraries.1.itineraryFlights.1.fltNo", "itineraries.1.itineraryFlights.1.depArpCd",
                                       "itineraries.1.itineraryFlights.1.arrArpCd", "pnrFareInfos.1.totSeats", "pnrFareInfos.1.paxFares.ADULT.bs",
                                       "pnrFareInfos.1.paxFares.CHILD.bs", "unknownImportantField"],
                              rows=[["contract-1", "PNR123", "BOM", "BKK", "15/12/26", "AI", "2354", "BOM", "BKK", "10", "16203", "16203", ""]])
        result = generate_blocks(request)
        self.assertFalse(result["canDownload"])
        self.assertTrue(any("source mapping" in issue for issue in result["issues"]))

    def test_profile_version_change_rejects_stale_draft(self) -> None:
        save_profile("BC1", valid_fields())
        with self.assertRaises(Exception) as raised:
            generate_blocks(request_for())
        self.assertEqual(raised.exception.status_code, 409)

    def test_duplicate_pnr_date_row_blocks_export(self) -> None:
        request = request_for(rows=[
            ["contract-1", "PNR123", "BOM", "BKK", "15/12/26", "AI", "2354", "BOM", "BKK", "10", "16203", "16203", "ACTIVE"],
            ["contract-1", "PNR123", "BOM", "BKK", "15/12/26", "AI", "2354", "BOM", "BKK", "10", "16203", "16203", "ACTIVE"],
        ])
        result = generate_blocks(request)
        self.assertFalse(result["canDownload"])
        self.assertTrue(any("duplicate contract, PNR" in issue for issue in result["issues"]))

    def test_non_integer_seat_quantity_blocks_export(self) -> None:
        request = request_for(rows=[["contract-1", "PNR123", "BOM", "BKK", "15/12/26", "AI", "2354", "BOM", "BKK", "10.5", "16203", "16203", "ACTIVE"]])
        result = generate_blocks(request)
        self.assertFalse(result["canDownload"])
        self.assertTrue(any("positive whole number" in issue for issue in result["issues"]))

    def test_formula_like_cell_blocks_export(self) -> None:
        request = request_for(rows=[["contract-1", "=1+1", "BOM", "BKK", "15/12/26", "AI", "2354", "BOM", "BKK", "10", "16203", "16203", "ACTIVE"]])
        result = generate_blocks(request)
        self.assertFalse(result["canDownload"])
        self.assertTrue(any("formula-like" in issue for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()
