# Experiment A: do the lab's HL7 v2.5.1 messages work in a real interface engine?

Date: 2026-10-03. Everything below was measured on this date unless marked as inferred.

## Short answer

Yes. Open Integration Engine 4.5.2 parsed and acknowledged all 1,064 messages (56 ADT^A04,
1,008 ORU^R01) with AA on both a strict channel and a lenient channel, and a File Reader split the
raw .hl7 files into the same 1,064 messages. The engine's own parsed tree showed every injected
v2-visible defect (6 missing MRN authorities, 6 partial birth dates, 929 local lab codes, 3 padded
upper-case family names), matching a plain-text count of the files exactly.

Two weaker controls need saying plainly. First, the engine's "strict validation" setting did not
reject a malformed date or a non-numeric NM value (both got AA); it only rejected an unknown message
type. An AA from this engine means "parsed", not "valid". Second, HAPI's validator (the library
inside the engine, called directly) found two length problems in our generator output: OBR-3 was 36
characters in all 1,008 ORU messages (max 22), and OBX-2 "CWE" in 150 messages (max 2). The
coordinator fixed both in lab/to_hl7v2.py during this experiment; the rerun of both validators on
the regenerated files shows 0 issues (table 4).

Only 4 of the 7 FHIR defect types reach the v2 feed at all (table 5). See BUGS.md.

## Scope and versions

- Input: `out/run/hl7v2/*.hl7`, 56 files, from `lab/to_hl7v2.py` over `out/run/fhir-messy`
  (Synthea, seed 42, 50 patients, messify rate 0.1). Manifest: `out/run/fhir-messy/defects.manifest.jsonl`.
- Engine: `openintegrationengine/engine:latest`, reports "Open Integration Engine 4.5.2 (Built on
  June 11, 2025)", Derby database, run under amd64 emulation on an arm64 Mac (OrbStack), `-m 2g`.
- HAPI v2 2.3 (hapi-base-2.3.jar and hapi-structures-v251-2.3.jar, the copies shipped inside the engine image).
- hl7apy 1.3.5, Python 3.9.6.
- Unit: message, unless a row says otherwise.

## Method

1. Channel XML. Hand-written Mirth XML fails silently when fields are missing, so `dump_templates.sh`
   runs Rhino inside the container with the engine's own jars and serializes default 4.5.2 objects
   (TCP receiver, MLLP mode, HL7v2 data type, File Reader/Writer). `build_channel.py` builds three
   channels from those shapes and imports them over the REST API (`/api/channels`, admin/admin).
   - `exp-v2-strict`, MLLP on 6661: HL7v2 in, strict parser (HAPI) and strict validation on.
   - `exp-v2-lenient`, MLLP on 6662: HL7v2 in, default Mirth ER7 parser, validation off.
   - `exp-v2-file`: File Reader, batch on (split on MSH), strict parser, reads the raw .hl7 files.
   All three have the same filter (reject if PID-3.1 is empty, which gives AR) and the same
   transformer, which reads PID-3.1, PID-3.4, PID-5, PID-7, OBX-3 and OBX-5 from the engine's parsed
   tree (not the raw text) and writes one JSON line per message through a File Writer.
   ACK: auto-generated after the source transformer.
2. `send_mllp.py` sends every message over one MLLP connection (0x0B ... 0x1C 0x0D), waits for each
   ACK and records MSA-1. It also sends 6 hand-made positive controls, so a run of all-AA can be
   told apart from a listener that accepts anything.
3. `analyze_engine.py` compares three views per message: the manifest, a plain-text read of the
   .hl7 files, and what the engine extracted.
4. Validators: `validate_hapi.sh` (HAPI 2.3 PipeParser with default validation, plus required
   segments/fields and maximum field lengths from HAPI's v2.5.1 structure classes) and
   `validate_hl7apy.py` (hl7apy, VALIDATION_LEVEL.STRICT). Both also run the controls in `controls/`.

## Results

### 1. ACKs from the engine (`results/*-ack-summary.json`)

| Messages | Strict channel (6661) | Lenient channel (6662) |
|---|---|---|
| ADT^A04, 56 | 56 AA | 56 AA |
| ORU^R01, 1,008 | 1,008 AA | 1,008 AA |
| Control: valid ADT | AA | AA |
| Control: PID-7 = `2002-10-19` (ISO date, not a v2 TS) | **AA** | AA |
| Control: OBX-2 NM with value `abc` | **AA** | AA |
| Control: PID-3.1 empty (our filter) | AR | AR |
| Control: MSH-9 = `ZZZ^Z99` | AE | AA |
| Control: plain text, not HL7 | AE, in a garbled ACK (the engine took delimiters from the text) | same |

Engine statistics (`results/engine-stats.json`): strict 1,070 received, 1,067 sent, 1 filtered,
2 errors (the two AE controls); lenient 1,070 / 1,068 / 1 / 1; file 1,064 / 1,064 / 0 / 0.
`results/engine.log` holds 1 ERROR line in the final run (the plain-text control).

### 2. Defects visible in the engine (`results/engine-analysis.json`)

| Defect (v2 location) | Manifest, patients in v2 | In .hl7 text | Engine strict | Engine lenient | Engine file reader |
|---|---|---|---|---|---|
| MRN without system (PID-3.4 empty), unit patient | 6 | 6 | 6 | 6 | 6 |
| Partial DOB (PID-7 `YYYYMM`), unit patient | 6 | 6 | 6 | 6 | 6 |
| Local lab code (OBX-3.3 = `L`), unit OBX | 994 | 929 | 929 | 929 | 929 |
| Upper-case padded family name (PID-5.1), unit patient | 3 | 3 | 3, trailing spaces kept | 3 | 3 |

Per-message agreement between engine and text: 1,064 of 1,064 on all four checks, all three channels.
The 65 local codes missing from v2 sit on lab Observations that no LAB DiagnosticReport references,
so to_hl7v2 never writes them (`results/coverage.txt`).

### 3. Validators on the original files (before the generator fix)

| Validator | ADT^A04 (56) | ORU^R01 (1,008) |
|---|---|---|
| HAPI 2.3 parse + default validation | 56 parse, 0 errors | 1,008 parse, 0 errors |
| HAPI required segments/fields (v2.5.1 optionality) | 0 missing | 0 missing |
| HAPI max field length | 0 | 1,008 with OBR-3 36 > 22; 150 with OBX-2 3 > 2 |
| hl7apy STRICT | 56 pass | 1,008 pass |

Positive controls (what each check actually catches):

| Control | HAPI 2.3 direct | hl7apy STRICT | Engine strict channel |
|---|---|---|---|
| ISO date in PID-7 | rejected | rejected | AA |
| NM value `abc` | rejected | **passed** | AA |
| ADT with no PV1 | missing required segment | missing required child | not sent |
| MSH-9 `ZZZ^Z99` | parsed as generic message | **passed** | AE |
| PID-3.1 empty | passed | passed | AR (our filter) |
| not HL7 | parse error | parse error | AE |

hl7apy did not flag the 36-character OBR-3 or the NM text value, so "passes hl7apy strict" is a
weaker statement than "passes HAPI with lengths".

OBR-3 truncation check (`results/obr3.txt`): cutting the 1,008 36-character values to 22 characters
leaves 999 distinct values; 18 messages share a truncated key, because Synthea ids share a per-patient
prefix. A receiver that truncates would merge results from different reports.

### 4. Validators after the coordinator's fix (`results/after-fix/`)

The coordinator changed OBR-3 to `R` + 21 hex characters of a SHA-1 and coded OBX-2 to `CE`, and
regenerated `out/run/hl7v2`. Only the validators were rerun; the engine was not.

| Check | Before | After |
|---|---|---|
| HAPI: ORU with OBR-3 longer than 22 | 1,008 | 0 (all 22 characters) |
| HAPI: ORU with OBX-2 longer than 2 | 150 | 0 |
| HAPI: messages clean | 56 of 1,064 | 1,064 of 1,064 |
| hl7apy STRICT pass | 1,064 of 1,064 | 1,064 of 1,064 |
| OBR-3 distinct values; collisions at 22 characters | 1,008; 18 | 1,008; 0 |

Inferred, not measured: the engine results in tables 1 and 2 should not change, since the engine
did not enforce lengths. Rerun `run_all.sh` to confirm.

### 5. Which FHIR defects can reach v2 at all (`results/coverage.txt`)

| Defect | Count in manifest | Reaches v2 |
|---|---|---|
| lab_local_code (unit Observation) | 994 | 929 (in a LAB report), 65 not |
| birthdate_partial, mrn_missing_system, name_case_whitespace (unit Patient) | 6, 6, 3 | all |
| duplicate_patient (unit Patient) | 2 | 0 (to_hl7v2 uses the first Patient only) |
| weight_in_lbs (unit Observation) | 68 | 0 (vital signs are not exported) |
| missing_encounter_ref (unit Observation) | 1,762 | not representable (ORU has no PV1 or visit number) |

## What failed or did not work as expected

- First channel version: strict serialization with non-strict deserialization made the destination
  log "Error populating ER7 metadata" for every message and returned AE for the bad-value controls.
  Setting both sides strict fixed it, and then the bad values got AA. The AE in the first version
  came from the mismatch, not from validation. I did not trace the exact code path.
- `POST /api/channels` returns `false` for an existing id; updates need `PUT /api/channels/{id}?override=true`.
- The global Deploy script did not run with no channels deployed, so templates were dumped with a
  standalone Rhino run inside the container instead.
- The ACK to the plain-text control is not parseable as HL7 (`MSHlo, tl...`); `send_mllp.py`
  records it as `?`. Its MSA-1 is AE.
- Screenshots of the engine UI were not taken (the web UI needs the desktop launcher; time ran out).

## Rerun

```bash
cd experiments/v2-engine
python3 -m venv /tmp/expvenv && /tmp/expvenv/bin/pip install hl7apy
HL7APY_PY=/tmp/expvenv/bin/python ./run_all.sh   # starts exp-oie on 8443/6661/6662, about 2 min
docker rm -f exp-oie
```

`run_all.sh` recreates the container, deploys the channels, sends everything, collects
`results/`, and runs both validators. Ports 8443, 6661 and 6662 must be free.

Files: `oie_api.py`, `dump_templates.sh/.js`, `build_channel.py` (writes `channel-*.xml`),
`send_mllp.py`, `channel_stats.py`, `inspect_messages.py`, `analyze_engine.py`, `validate_hapi.sh/.js`,
`summarize_hapi.py`, `validate_hl7apy.py`, `coverage_check.py`, `obr3_length_check.py`, `controls/`.
Generator issues: `BUGS.md`.
