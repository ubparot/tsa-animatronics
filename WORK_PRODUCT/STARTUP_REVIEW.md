# Startup review

Review date: 12 October 2026 (America/New_York)

Status: historical search review. The missing-package blocker was resolved on 12 October 2026 when the user supplied Z:/Downloads/Codex_Work_Block_Instructions-20261012T225555Z-1-001/. Required instructions were then read. Current startup answers and engineering outputs are in the nested Codex_Work_Block_Instructions/WORK_PRODUCT folder of that package. No dimensions or hardware selections have been frozen.

## Requested startup sequence

1. Read `START_HERE.md`.
2. Read `AGENTS.md` and `INSTRUCTIONS/AUTONOMOUS_WORK_BLOCK.md`.
3. Ask the consolidated startup questions before freezing dimensions or hardware.
4. Save outputs under `WORK_PRODUCT`.

The first three named files are absent from the current checkout. Attempts to read `START_HERE.md` failed because it does not exist. Filename searches found none of the three files in the workspace or its parent ChatGPT directory; searches for START_HERE.md and AUTONOMOUS_WORK_BLOCK.md also found no loose copies in Documents, Downloads, or Desktop. Neither the current Git HEAD nor the locally available origin/main ref contains the requested paths. Git history available locally contains no changes to these paths. No applicable parent AGENTS.md was found from the drive root through the workspace parent.

These findings do not prove that a separate startup package or an archive does not exist. The user has been asked for its folder, ZIP path, or Drive link. Do not reconstruct or claim to have read the missing instructions. Do not substitute the draft questionnaire for their authoritative questionnaire.

### Follow-up source check

On the next goal continuation, the current checkout was inspected again. None of the requested startup files had appeared, and all recorded answers remained pending.

- A live `git ls-remote --heads origin` check returned only `refs/heads/main` at `7316949ed2a90c130907d122cf29d818611be0ac`. The local origin/main resolves to that same commit, whose tree does not contain the requested paths. No checkout or remote files were changed.
- Read-only searches of connected Google Drive for START_HERE, AUTONOMOUS_WORK_BLOCK, AGENTS.md, and Pinocchio returned no matches. Related searches for Animatronics and startup did not identify the startup package. One small Animatronics README result was fetched and describes a different Arduino instrument-servo project; it contains none of the requested startup instructions. Unrelated document contents were not fetched.
- A read-only local ZIP audit checked all 37 eligible archives discovered under Downloads, Desktop, and Documents, excluding application/runtime caches. Across 1,813 ZIP entry names, no exact basename matched START_HERE.md, AGENTS.md, or AUTONOMOUS_WORK_BLOCK.md, case-insensitively. All eligible central directories were readable; nothing was extracted.

The preceding goal turn made progress by saving the startup review and draft questions and presenting the questions. This continuation adds evidence that the available source searches did not locate the required files. The next necessary input remains the package location or the original files. There is no live search process to wait on. The source-location question remains pending; it has not been reissued.

## Existing evidence

### Design reference

Source: `output/Pinocchios_Workshop_Design_Specification.docx`, Revision B, 13 September 2026.

The document calls itself a design specification mockup. Sheet 01B explicitly labels dimensions, loads, timing, costs, and acceptance thresholds as engineering assumptions unless a manufacturer source is cited. It states that the drawings are not fabrication-release CAD.

Its candidate concept is a seated Pinocchio with an extending nose, speech, light, motion, and a Jiminy lantern. The following are reference assumptions requiring user confirmation, not accepted constraints:

| Topic | Existing assumption | Confirmation needed |
| --- | --- | --- |
| Competition | TSA high school Animatronics, 2026–27; other compliance text requests a 2027–2028 chapter | Correct season, division, state, level, and applicable rule sources |
| Budget | US $2,000, excluding existing shop equipment and student labor | Actual remaining budget, inclusions, and existing inventory |
| Schedule | 18 December 2026 internal readiness target | Actual event date and prototype milestones |
| Team | Three students with mechanical, electronics, and software roles | Current people, skills, availability, and fabrication resources |
| Size | 900 × 600 × 500 mm chest; 1100 × 900 × 1100 mm swept envelope; 38 kg target assembly | Official limits, transport restrictions, and intended scale |
| Motion | 27 figure axes: 26 rotary servos and one pneumatic nose axis | Required versus optional movements and actual hardware |
| Nose | 80 mm candidate travel | Desired motion and whether pneumatics are appropriate or permitted |
| Runtime | Desktop PC, offline interaction, indoor grounded 120 VAC | Actual computer, available power, networking, and venue conditions |

### Software reference

Source: `software_pipeline/README.md`.

The README describes a hardware-free show-control pipeline. Validated response JSON feeds spoken text, truth-tag/nose behavior, virtual actuators, and show-state transitions. This describes software intent and does not establish purchased or installed mechanical hardware. README runtime and installed-model claims have not been revalidated during this startup review.

The workspace contains pre-existing modified and untracked software and voice-study files. This review leaves those files in place and adds only startup artifacts under `WORK_PRODUCT`.

## Current outputs

- `WORK_PRODUCT/STARTUP_REVIEW.md`: evidence, unresolved inputs, and startup status.
- `WORK_PRODUCT/STARTUP_QUESTIONS_DRAFT.md`: provisional consolidated questions based on the user instruction and existing reference documents.

## Next action

Locate and read the requested startup package in the required order. Reconcile its actual questions with the draft, preserve any answers already received, and ask only outstanding questions. Record user answers and distinguish confirmed requirements from remaining assumptions before any dimension or hardware freeze.

## Completion audit

| Requirement | Evidence | Result |
| --- | --- | --- |
| Read START_HERE.md first | Direct read attempted; requested file absent | Incomplete |
| Read AGENTS.md | Searches and Git inspection show no local copy | Incomplete |
| Read INSTRUCTIONS/AUTONOMOUS_WORK_BLOCK.md | Searches and Git inspection show no local copy | Incomplete |
| Ask the consolidated startup questions | Provisional questions saved and presented to the user in three consolidated groups; source-location question also presented; authoritative questions cannot be verified without source files | Provisional questions asked; source-specific coverage pending |
| Do not freeze dimensions or hardware before questions | Only review and question artifacts created; existing reference assumptions remain provisional | Satisfied for this review |
| Save outputs under WORK_PRODUCT | Both startup artifacts are saved under that directory | Satisfied for this review |

The full goal is incomplete and must not be marked complete based on this partial startup review.

## Historical blocked audit (resolved by supplied source path)

The same source-package blocker has recurred in three consecutive goal turns:

1. The initial startup turn attempted START_HERE.md, searched local files and Git, saved this review and draft questions, and asked the user for the source location.
2. The first continuation rechecked the workspace and expanded the source search to the live Git remote, connected Drive, and eligible local ZIP archives. The named source files remained unavailable.
3. The second continuation again searched the current checkout for all three filenames and inspected the saved review and answer record. No source files had appeared, and the source-location answer remained pending.

The previous continuation made progress by gathering additional source-search evidence. This continuation revalidates the existing blocker and does not claim repeated status checks as substantive design progress.

The requested instruction-reading sequence and authoritative questionnaire cannot be completed without the actual files or their accessible location. No search process remains live, no supplied answer resolves the missing source, and drafting substitute instructions would not satisfy the objective. Further dimension or hardware work cannot complete this startup objective. The three-turn blocked threshold is met.

Resume input: provide the folder or ZIP path, an accessible link, or the original START_HERE.md, AGENTS.md, and INSTRUCTIONS/AUTONOMOUS_WORK_BLOCK.md files. Read them in the requested order, reconcile the questionnaire with already-asked questions, record answers under WORK_PRODUCT, and continue the original goal without treating this review as completion.
