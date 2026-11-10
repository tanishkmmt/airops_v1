from __future__ import annotations

import unittest

from services.source_service.main import MAX_ROWS, _contract_candidates_from_flights, _departure_contract_candidates, _flight_groups, _parse_csv


class SourceLimitTests(unittest.TestCase):
    def test_paired_summary_uses_pnr_to_decide_ow_or_rt(self) -> None:
        table = {
            "name": "Summary", "sourceFile": "source.xlsb",
            "headers": ["Airline", "Flight No", "Dep Date", "Sector", "PNR", "Flight No2", "Return Date", "Return Sector", "PNR2"],
            "rows": [
                ["AI", "AI-1", "01/12/26", "BOM-BKK", "OUT", "AI-2", "04/12/26", "BKK-BOM", "BACK"],
                ["AI", "AI-3", "02/12/26", "DEL-SIN", "SHARED", "AI-4", "06/12/26", "SIN-DEL", "SHARED"],
            ],
        }
        candidates = _contract_candidates_from_flights(_flight_groups(table))
        self.assertEqual(len(candidates), 3)
        self.assertEqual(sum(item["journeyType"] == "OW" for item in candidates), 2)
        self.assertEqual(sum(item["journeyType"] == "RT" for item in candidates), 1)
        self.assertEqual(next(item for item in candidates if item["journeyType"] == "RT")["endDate"], "06/12/26")

    def test_departures_pair_only_with_matching_pnr_and_use_both_departure_dates(self) -> None:
        candidates, invalid = _departure_contract_candidates(
            ["Airline", "Sector_Onwards", "Sector_Return", "Dep_Date", "Return_Date", "PNR", "PNR2"],
            [["AI", "DEL-DPS", "DPS-DEL", "01/11/26", "10/11/26", "SAME", "SAME"]],
        )
        self.assertEqual(invalid, 0)
        self.assertEqual(candidates[0]["endDate"], "10/11/26")
        self.assertEqual(candidates[0]["journeyType"], "RT")

        separate, _ = _departure_contract_candidates(
            ["Airline", "Sector_Onwards", "Sector_Return", "Dep_Date", "Return_Date", "PNR", "PNR2"],
            [["AI", "DEL-DPS", "DPS-DEL", "01/11/26", "10/11/26", "ONE", "TWO"]],
        )
        self.assertEqual(len(separate), 2)
        self.assertEqual({item["journeyType"] for item in separate}, {"OW"})
        self.assertEqual({(item["journey1From"], item["journey1To"], item["endDate"]) for item in separate},
                         {("DEL", "DPS", "01/11/26"), ("DPS", "DEL", "10/11/26")})

    def test_reciprocal_rows_pair_by_pnr_without_exposing_it(self) -> None:
        groups = [
            {"airline": "AI", "pnr": "SHARED", "direction": "outbound", "legs": [{"origin": "BOM", "destination": "BKK", "date": "01/12/26"}]},
            {"airline": "AI", "pnr": "SHARED", "direction": "return", "legs": [{"origin": "BKK", "destination": "BOM", "date": "05/12/26"}]},
        ]
        candidates = _contract_candidates_from_flights(groups)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["journeyType"], "RT")
        self.assertEqual(candidates[0]["endDate"], "05/12/26")
        self.assertNotIn("SHARED", str(candidates))

    def test_summary_flights_become_dated_contract_candidates(self) -> None:
        groups = [
            {"airline": "AI", "legs": [{"origin": "BOM", "destination": "BKK", "date": "01/12/26"}]},
            {"airline": "AI", "legs": [{"origin": "BOM", "destination": "BKK", "date": "15/12/26"}]},
        ]
        candidates = _contract_candidates_from_flights(groups)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["endDate"], "15/12/26")
        self.assertEqual(candidates[0]["sourceRows"], 2)

    def test_csv_preview_caps_rows_and_marks_partial_source(self) -> None:
        content = "airline,route\n" + "AI,BKK-BOM\n" * (MAX_ROWS + 1)
        table = _parse_csv(content.encode(), "departures.csv")[0]
        self.assertEqual(table["rowCount"], MAX_ROWS)
        self.assertEqual(len(table["rows"]), MAX_ROWS)
        self.assertTrue(table["truncated"])


if __name__ == "__main__":
    unittest.main()
