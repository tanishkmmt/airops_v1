# AirOps Preparation Workbench

A local prototype for preparing AIS contract and block upload files in CSV or XLSX format. Procurement uploads and generated case files are processed in memory and are not persisted. Approved airline T&C and block profiles are stored separately as versioned JSON configuration (no case database), with replaceable repository adapters for later API-backed storage.

## Run locally

With Docker Compose:

```sh
docker compose up --build
```

Open <http://localhost:8080>. The source, contract, and block APIs are separate services behind the web gateway. The gateway routes `/api/source/`, `/api/contracts/`, and `/api/blocks/` to their respective service.

For local development without Docker, install the pinned requirements and use the included launcher:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run_local.py
```

The launcher starts the same three FastAPI services on loopback ports and serves the frontend through a small standard-library gateway at port 8080. Anyone using the local app can view and edit Airline T&Cs, Block Config profiles, and templates. The gateway binds to `127.0.0.1`; the Docker port mapping is also loopback-only. Press Ctrl+C to stop all four local processes.

## Prototype workflow

1. A user creates or imports an airline profile, resolves conflicts and missing T&Cs, then saves an approved version.
2. An operator uploads the procurement file and selects its airline profile. Paired `Summary` sectors and PNRs take priority when present; otherwise supported `Departures` rows supply route and date groups.
3. Review the contract rows and status warnings, confirm the review checkbox, then download a demo-schema CSV or XLSX without `Contract Id`.
4. BC1 is seeded from the consistent values in the supplied Block2 workbook. Users can update Block Config in Configuration → Block. A completed block file can suggest values that are consistent across its rows; suggestions are not saved until a user reviews and submits them.
5. Upload the contract CSV to AIS. After AIS generates IDs, upload the procurement source and AIS result in the block-preparation flow, then choose the Block Config whose saved pre-submit template matches the AIS upload schema. Confirm each PNR, route/date, contract ID, and seats-to-release value.

The contract and block services expose profile and preparation APIs independently of the UI. Profile JSON is stored separately in the `airline-profiles` and `block-profiles` volumes. Airline profiles and Block Config schemas/defaults are persistent; case files and generated outputs are not. The local app has no user authentication, so anyone with access to this machine can change saved configuration.

## Local checks

Run the focused regression checks before changing the contract mapping, profile store, or API validation:

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check web/app.js
```

For Thailand-style XLSB files with paired `Summary` columns, the source service uses that sheet for contract sectors. It combines reciprocal sectors into one `RT` contract only when both legs share a PNR; different PNRs produce separate `OW` contracts. A supported `Departures` sheet is used when no paired Summary exists. Passenger-level rows and PNR values are omitted from contract candidates. Contract start date uses the creation date in Asia/Kolkata; end date is the latest departure date for the sector or paired sectors. Names use airline, route, and start/end month and year (for example, `AI BKK-BOM-BKK OCT2026-DEC2026`). The AIS contract and block upload headers from the supplied demo samples are bundled under `web/samples/` with headers only and load automatically. Contract template replacements apply to the browser session; each Block Config can save its own block-template header schema with the persistent profile. Contract and block outputs can be downloaded as CSV or XLSX.

This prototype recognizes the sample schemas and the stated Air Ops rules. AIS-required fields and several business rules remain unconfirmed, so generated files are labelled as drafts and the interface reports unresolved fields. An AIS export containing `blockId` is identified as an export, not an upload template.

## Mapping behavior and known boundaries

- The contract CSV header order is preserved. Duplicate headers, such as the two `contractName` columns in the Flamingo result, are flagged and block export until the correct unique upload template is supplied; the tool does not guess their meanings.
- EML attachments and workbook sheets are inspected in memory. PNR groups and source route/date hints become editable contract candidates; commercial terms are not copied from sample rows.
- In the Thailand XLSB, `Summary` is selected as the operational PNR source and `Terms` as the contract metadata source; derivative tabs such as `Pivot` are excluded to avoid duplicate or transformed records. The `Terms` sheet can supply route, journey type, airline, and contract date suggestions. A separate AIS contract result is still required at the block step.
- Block rows are prepared from procurement PNR groups after the AIS contract result is imported. PNR, route, date, flight and fare fields are derived from procurement where available; contract IDs come from the AIS result. Supplier PNR matches airline PNR. Seats-to-release require operator confirmation.
- Block `bookingStartDate` is copied from the selected AIS contract's `contractStartDate`. Every `fareFamily` field follows that contract's `dummyContract` value (`Yes` → `Tentative`; `No` → `Smart Saver Fare`). These values are excluded from Block Config.
- `mmtProductClass` is generated as `Holiday#N`, where `N` is the count of distinct cities in the itinerary (for example, two cities → `Holiday#2`; three cities → `Holiday#3`).
- Reusable values absent from procurement and the AIS contract result are stored in the approved Block Config. Adult base fare maps from procurement `Fares` / `Fares4`; child base fare remains a configuration value because it is passenger-specific and differs in the supplied Block2 rows. Customer ticketing deadline maps from an explicit ticketing-deadline/time-limit column or from paired `Deadline D-7` / `Deadline 7` date columns; date values are converted to days before departure and the type is set to `BEFORE_DEPARTURE`. Adult base fare and both ticketing-deadline fields are excluded from Block Config. BC1 stores only values consistent across the supplied Block2 rows; conflicting child fares remain blank. A completed block file suggests a value only when its nonblank row values agree; suggestions require review before saving. Known empty demo columns are optional. Replacement-template fields without a registered source, profile value or optional rule block export until mapped.
- Block export checks the saved profile version, template compatibility, duplicate headers and rows, formula-like values, required IDs/PNRs/routes/dates/seats, numeric fare and seat values, and the selected contract's route, airline and date range. It generates one file for each contract ID.
- Procurement seat totals and AIS released/live inventory are different quantities in the supplied examples. The quantity to open is a required operator confirmation.
- The downloaded `blocks_...csv` is an AIS result/export, not the upload template. The tool rejects it as a template because it contains generated `blockId` fields.
- The source service groups sectors by airline and PNR. Reciprocal routes with different PNRs remain separate `OW` contracts. Cancelled source legs remain in schedule ranges pending explicit Air Ops confirmation; their counts are surfaced for review.

The current installation remains a prototype, not a production deployment. The JSON profile repository is safe for a single service instance, but its in-process lock does not coordinate concurrent replicas. Employee-facing shared use requires company SSO/RBAC, a transactional shared profile store, audit events, approved mapping rules, operational monitoring, and deployment/retention controls.

## Service boundaries

- `source-service`: in-memory EML, CSV, TSV, XLSX, and XLSB parsing; worksheet/PNR inspection and privacy-preserving Departures aggregation.
- `contract-service`: versioned airline profile APIs, profile import preview, deterministic Departures-to-contract mapping, template validation, and CSV/XLSX generation.
- `block-service`: versioned Block Config and reference import preview, procurement-to-block mapping, contract-ID association, failure-safe validation, and one CSV/XLSX output per contract ID.
- `web`: responsive frontend and reverse proxy.

Tabular APIs share header, row, and cell size limits plus normalized duplicate-header and formula-injection checks. Row previews are capped at 20,000 rows per sheet, and truncated sources are blocked from export. The Departures sheet is fully scanned into route/date aggregates without returning passenger rows, even when it exceeds the preview limit. The browser uses the same-origin gateway, so service-level CORS access is disabled. Upload limits include multipart overhead at the gateway; the source service enforces the actual 20 MiB file cap.

No business-case database, local file archive, or persistent browser storage is configured. Configuration editing is open to users of the local app; the listener is restricted to loopback. Before shared production use, add company SSO/RBAC, move profile JSON to a transactional shared repository, set deployment limits and retention policy, and confirm the AIS template versions and mandatory-field rules with Air Ops.
