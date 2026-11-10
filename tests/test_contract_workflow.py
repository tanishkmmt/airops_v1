from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError
from services.block_service.main import BlockRequest, generate_blocks
from services.contract_service.departures_mapper import prepare_candidate_groups
from services.contract_service.main import ContractRequest
from services.contract_service.profiles import PROFILE_FIELDS, required_profile_fields, save_profile
from services.validation import duplicate_headers, formula_like


def approved_fields() -> dict[str, str]:
    fields = {key: "1" for key in PROFILE_FIELDS}
    fields.update({"dummyContract": "No", "tnc.dummyToRealPNRDeadline": ""})
    return fields


class ContractWorkflowTests(unittest.TestCase):
    def test_expired_departure_groups_are_excluded(self) -> None:
        profile = {"airline": "AI", "version": 3, "fields": approved_fields()}
        source = [
            {"airline": "AI", "journeyType": "OW", "journey1From": "BOM", "journey1To": "BKK", "endDate": "01/01/25", "sourceRows": 2},
            {"airline": "AI", "journeyType": "OW", "journey1From": "DEL", "journey1To": "BKK", "endDate": "01/12/26", "sourceRows": 3},
        ]
        with patch("services.contract_service.departures_mapper._contract_creation_date", return_value=date(2026, 10, 28)):
            result = prepare_candidate_groups(source, profile, "AI")
        self.assertEqual(result["rowCount"], 1)
        self.assertEqual(result["records"][0]["contractEndDate"], "01/12/26 23:59")
        self.assertTrue(any("historical" in issue for issue in result["issues"]))

    def test_departure_contract_uses_creation_date_and_month_year_name(self) -> None:
        profile = {"airline": "AI", "version": 3, "fields": approved_fields()}
        source = [{
            "airline": "AI", "journeyType": "RT", "journey1From": "BKK", "journey1To": "BOM",
            "journey2From": "BOM", "journey2To": "BKK", "endDate": "15/12/26", "sourceRows": 8,
        }]
        with patch("services.contract_service.departures_mapper._contract_creation_date", return_value=date(2026, 10, 28)):
            result = prepare_candidate_groups(source, profile, "AI")

        record = result["records"][0]
        self.assertEqual(record["contractStartDate"], "28/10/26 00:01")
        self.assertEqual(record["contractEndDate"], "15/12/26 23:59")
        self.assertEqual(record["contractName"], "AI BKK-BOM-BKK OCT2026-DEC2026")
        self.assertNotIn("OW", record["contractName"])
        self.assertNotIn("RT", record["contractName"])

    def test_dummy_deadline_is_optional_only_when_dummy_contract_is_no(self) -> None:
        fields = approved_fields()
        self.assertNotIn("tnc.dummyToRealPNRDeadline", required_profile_fields(fields))
        fields["dummyContract"] = "Yes"
        self.assertIn("tnc.dummyToRealPNRDeadline", required_profile_fields(fields))

    def test_profiles_persist_and_version_without_touching_project_data(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "profiles.json"
            with patch.dict("os.environ", {"AIR_OPS_PROFILE_PATH": str(target)}):
                first = save_profile("AI", approved_fields())
                second = save_profile("AI", approved_fields())

            stored = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(first["version"], 1)
            self.assertEqual(second["version"], 2)
            self.assertEqual(stored["profiles"]["AI"]["history"][0]["version"], 1)

    def test_non_finite_profile_values_are_rejected(self) -> None:
        fields = approved_fields()
        fields["tnc.minSeatsToOperate"] = "NaN"
        with self.assertRaisesRegex(ValueError, "non-negative number"):
            save_profile("AI", fields)

    def test_shared_header_and_formula_checks(self) -> None:
        self.assertEqual(duplicate_headers(["contractName", "Contract Name", "airline"]), ["Contract Name", "contractName"])
        self.assertTrue(formula_like("=1+1"))
        self.assertFalse(formula_like("-42"))

    def test_api_models_bound_nested_table_cells(self) -> None:
        with self.assertRaises(ValidationError):
            ContractRequest(headers=["contractName"], rows=[["x" * 10_001]], airline="AI")

    def test_block_export_rejects_normalized_duplicate_headers(self) -> None:
        from services.block_service.profiles import BLOCK_CONFIG_FIELDS as BLOCK_FIELDS, save_profile as save_block_profile

        block_fields = {key: "1" for key in BLOCK_FIELDS}
        block_fields.update({key: "False" for key in BLOCK_FIELDS if key.casefold().endswith(".droolsbased")})
        block_fields.update({key: "0" for key in BLOCK_FIELDS if key.casefold().endswith((".bs", ".tx", ".amnt", ".value"))})
        with tempfile.TemporaryDirectory() as folder, patch.dict("os.environ", {"AIR_OPS_BLOCK_PROFILE_PATH": f"{folder}/profiles.json"}):
            save_block_profile("BC1", block_fields)
            request = BlockRequest(headers=["contractId", "Contract Id"], rows=[["1", "1"]], confirmed=True,
                                   profileCode="BC1", profileVersion=1,
                                   contractReferences=[{"id": "1"}])
            result = generate_blocks(request)
        self.assertFalse(result["canDownload"])
        self.assertTrue(any("Duplicate headers" in issue for issue in result["issues"]))

if __name__ == "__main__":
    unittest.main()
