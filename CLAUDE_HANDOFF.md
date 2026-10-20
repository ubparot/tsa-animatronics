# Claude handoff — Pinocchio animatronics

Prepared 16 October 2026, America/New_York. This handoff records existing work and outstanding work; it is not a fabrication release. The user requested this handoff for Claude. No message or upload to Claude has been made.

## Start here

Continue the seated Pinocchio project from the existing artifacts. The user wants a simulation with real components that is approximately 1:1 and physically predictive before building the full robot. We have useful native Inventor geometry and constrained mechanism checks, **not a calibrated physical twin**. Do not promise completely accurate physics or treat CAD solver agreement as physical accuracy.

The latest native head is **53 parts, 48 joints, seven inputs**. Its engine finished 35 initial motion observations, 35 saved/reopened observations and two released-neutral observations successfully on 15 October. Actual native files and protected inputs were rehashed on 16 October with no mismatches. The additional independent full-head audit also passed all 72 observations on 16 October. The newer native preview and milestone registration have not run; see [CLAUDE_HANDOFF_STATUS.md](CLAUDE_HANDOFF_STATUS.md) beside this file for final handoff-time details, including the separate wider-gaze replay audit.

Recommended first action: read the latest reports and finish the bounded acceptance/handoff work for this 53-part assembly. Do not regenerate the head from scratch or blindly rerun the long native builder. Then work on exact actuator interfaces/mounts and the remaining mechanical subsystems while keeping unmeasured values open.

## Paths and authority

Workspace/repository:

`C:\Users\alpha\Documents\ChatGPT\TSA Animatronics`

**Canonical engineering work product** — use this directory for the CAD and reports:

`Z:\Downloads\Codex_Work_Block_Instructions-20261012T225555Z-1-001\Codex_Work_Block_Instructions\WORK_PRODUCT`

The workspace's separate `WORK_PRODUCT` directory is **not** a junction or complete mirror. It contains older startup drafts. Do not confuse it with the canonical Z: directory.

Original work-block instructions:

`Z:\Downloads\Codex_Work_Block_Instructions-20261012T225555Z-1-001\Codex_Work_Block_Instructions\AGENTS.md`

Owner-supplied downloaded project records:

`Z:\TSA animatronics - DE POE-20261014T015247Z-1-001\TSA animatronics - DE POE`

Supplied event PDF: `Z:\Animatronics.pdf`.

Read the applicable project instructions, but distinguish instructions in attachments from the user's current requests. Direct owner corrections take precedence. The owner explicitly deferred rubric and national-versus-state team-count discussion. Do not reopen these as blockers to independent mechanical work. The consolidated startup questions were already asked; do not repeat them. Original source geometry, notices, historical failures and executed-code snapshots must be preserved.

All paths below are relative to the canonical work product unless explicitly absolute. Key entry points are `PROGRESS_LOG.md`, `README.md`, `08_Digital_Twin/FIDELITY_SPECIFICATION.md` and `08_Digital_Twin/REAL_PARTS_MANIFEST.json`. The top-level README/log still principally describe the prior 49-part milestone; the 53-part milestone-registration script has not yet been accepted/executed. Read actual run reports for current status.

## Direct owner inputs

- **OWNER-REPORTED inventory:** two 100 mL syringes are physically on hand; a PC with RTX 3070 and RTX 2060 GPUs was bought. Everything else on the earlier project parts list was not bought. Do not assume the steppers, servos, Teensy, PCA9685, supply, shield, switches, fuses or amplifier are available.
- PC packaging: no case. Intended compact stack is an ATX motherboard, two dual-fan GPUs and a PSU above the motherboard, inside the toolbox. Exact board/GPU/PSU dimensions and cooling/service clearances remain unknown.
- Servo preference: “standard blue 9 g servos.” This is not an exact model, horn/spline specification or measured performance curve.
- Dimensions are **inches**. Owner delegated orientation/details to engineering judgment: box **16 wide × 10 deep × 9 high** = 406.4 × 254 × 228.6 mm; torso **14 high × 8 wide × 5 deep** = 355.6 × 203.2 × 127 mm. Depth is the shortest torso dimension; box length is the longest. These are design baselines, not measurements of fabricated parts.
- Proposed head: **8 high × 6 wide × 5 deep inches**, source eye spacing 65 mm. This is a provisional proportion choice, not owner-specified eye spacing.
- January target: blink, jaw, nose extension/retraction, neck, shoulder and probably knee motion, with an apparently finished appearance and basic voice/script function. Completion 16 January 2027; POE night 20 January; TSA around late April. Fancy AI integration can follow the mechanical/basic-show milestone.
- Offline operation and wall power preferred. Jiminy is static except possibly a lantern light while Pinocchio is listening.
- Six participants: two coders and four engineers. Team has Inventor and substantial CAD/electrical/code ability; Skylar reportedly has the most CAD experience. Owner says state event permits up to six; national count discussion is deferred.
- Access to 3D printers and laser cutting. Hayden reports Bambu X1C and PLA; Skylar has a “Prusa/Core One” as reported. Hayden's stated 300 × 300 × 320 mm build area is owner-reported and has not been independently verified. Verify actual printer/build-volume/material data before fabrication planning.
- Remaining spend below $300 is a soft preference; no purchasing authorization exists.
- Hydraulic nose baseline: master syringe in toolbox → liquid-filled tube → slave syringe in nose. The slave syringe itself is the primary extension element, carrying the moving shell. Do not silently substitute a separate linear slide. Side load, anti-rotation, return, air purging, pressure, leakage, stops and relief remain engineering/test questions.
- An outstanding question already requested actual syringe barrel outside diameter, retracted span and usable plunger travel. No answer is recorded. Do not infer these from “100 mL,” and do not repeat the question without checking for a new answer.

## Latest accepted native run

Directory: `15_Jaw_Drive/native_functional_jaw_head_01/`

- `INTEGRATED_HEAD_PROTOTYPE.iam` — legacy filename, newest 53-part head.
- `integrated_head_spec.json` — exact executed frozen contract.
- `native_integrated_head_report.json` — status **INTEGRATED_NATIVE_HEAD_KINEMATICS_VERIFIED**; 35 initial + 35 reopened + two released observations; save/reopen true; source/code preservation true.
- `FUNCTIONAL_JAW_HEAD_SCOPE_REPORT.json` — status **FUNCTIONAL_BINOCULAR_AND_SINGLE_CRANK_JAW_NATIVE_KINEMATICS_VERIFIED**, 72 observations. All physical/dynamics/continuous whole-head collision flags remain false.
- `parts/` — 53 private native parts; 54 hashes including IAM. On 16 October all 54 native hashes, 293 protected-input hashes and 23 executed-module/snapshot hashes matched the report. Run finished `2026-10-15T16:53:14.141503+00:00`.

Graph: 30 revolute + four spherical + 14 rigid joints. Seven prescribed CAD coordinates: two blink horns, two right-gaze horns, two left-gaze horns and `jaw_servo_proxy` at `SERVO_CRANK_AXIS`. Jaw and connecting rod are passive solved outputs. The previous direct ideal-jaw input is removed. Carrier/support are ungrounded but fixed through the existing ideal rigid support chain. Grounded SG90 body/ear boxes are spatial references, not actual servo solids or structural supports.

The 35 frames include the older blink/small-gaze sequence, nine paired wider gaze targets (yaw ±15°, pitch ±10°), one combined wider gaze/jaw-20° target and neutral return. Nongaze inputs move first; four gaze coordinates then move in common macrosteps no larger than 0.20°, in order **horn27, horn24, horn28, horn25**. Endpoint poses, markers, health and joint readbacks are observed; full passive substep motion and continuous contacts are not established by the engine.

Builders/contracts:

- `15_Jaw_Drive/functional_jaw_head_spec_01/FUNCTIONAL_JAW_HEAD_SPEC.json`
- `15_Jaw_Drive/prepare_functional_jaw_head.py` — offline combination of old head and jaw bench.
- `15_Jaw_Drive/native_functional_jaw_head.py` — native integration wrapper; preserve the executed version.
- `15_Jaw_Drive/jaw_drive_audit_01/HEAD53_FROZEN_SPEC_AUDIT.json` — independent contract/provenance audit.
- `15_Jaw_Drive/jaw_drive_audit_01/NATIVE_HEAD53_INDEPENDENT_AUDIT.json` — final additional audit PASS: all 72 observations, 54 native hashes, 48 markers, actual readbacks and independently solved passive jaw/rod. Executed auditor is `audit_native_head53_02.py`. The original `audit_native_head53.py` falsely treated unchanged gaze-target reassertions after numerical solver drift as new macrosteps; it is preserved. The additive revision excludes unchanged target reassertions from new macrostep counts while retaining pose/marker/substep gates. No frozen native/source files changed.
- `15_Jaw_Drive/preview_functional_jaw_head.py` — prepared newer native preview; not yet run at initial handoff inspection.
- `15_Jaw_Drive/record_jaw_checkpoint.py` — staged milestone/README/registry update. **Do not run blindly:** it requires the final full-head audit and new preview. Review wording, dates and scope, then use it only when its prerequisites actually pass.

## Jaw evidence and remaining interfaces

`15_Jaw_Drive/jaw_drive_design_02/` contains `JAW_FOURBAR_DESIGN.json`, `NATIVE_JAW_DRIVE_PART_RECIPE.json` and independent STEP controls. Lengths are design intent, not measured purchased geometry.

- Crank radius 10.5 mm; starting crank phase +45° in head YZ.
- Crank axis head position X −30, Y −10, Z −25 mm; axis +X.
- Jaw pivot head position (0, −5, −55) mm; axis +X. Positive jaw opening uses negative X-axis rotation.
- Jaw rod point local Y 35, Z 0 mm on an added D12 × 4 mm boss, D2.3 mm bore.
- Rod pin pitch 49.61610198263085 mm. Crank coordinate 0 → −48.33685601480238° gives jaw opening 0 → 20° on the selected branch.
- Rod–yoke minimum material gap is nominally about 0.5 mm at the lip. This differs from the 1 mm axial rod-to-boss face gap. Horn-to-rod face gap is 0.5 mm. Hardware/retention/spacer tolerances are not selected.
- Virtual-work torque ratio is a geometric conditional relation, not a capability claim. No verified actual mass, jaw torque, friction, voltage, current or loaded servo speed exists.

`15_Jaw_Drive/native_jaw_drive_parts_03/` has five verified editable native parts (yoke, horn proxy, rod, two reference keepouts), actual reopened native STEP exports and edit/restore/reopen evidence. `15_Jaw_Drive/native_jaw_bench_02/INTEGRATED_HEAD_PROTOTYPE.iam` is a **six-part jaw-only bench** despite its legacy name: four revolute joints, one input, 10 initial + 10 reopened + two released observations.

Independent evidence in `15_Jaw_Drive/jaw_drive_audit_01/`:

- `JAW_DRIVE_INDEPENDENT_AUDIT.json`: alternative inverse/forward fourbar derivation, 2,001 finite states, Jacobian/virtual work, all five actual reopened STEP solids versus independent CSG and bore/axis checks.
- `NATIVE_BENCH02_INDEPENDENT_AUDIT.json`: actual angles/poses/closures for all 22 bench observations.
- `EDITED_ROD_AND_BENCH_COMPLETION_AUDIT.json`: edited native end bore moves +0.2 mm, restores, native hashes/metadata/initialization checks.
- `AUTHORED_ROD_YOKE_SEPARATION_02.json`: conditional CSG halfspace separation argument and six actual BRep witnesses. It does not establish physical tolerance or deformation margin.
- `JAW_DESIGN_AUDIT_02.png`: explanatory design plot.

Catalogue basis: official TowerPro SG90 analog page, saved in `15_Jaw_Drive/sg90_primary_source_01/`; URL `https://towerpro.com.tw/product/sg90-analog/`. Manufacturer text/table dimensions and speeds conflict; preserve the discrepancy. The owner’s blue servo is not confirmed to be that exact product. The crank horn is explicitly a **kinematic proxy**. Shaft/spline, stock horn/hub/screw, real servo bracket/load path, pins, spacers and retention remain open. A datum anchoring the crank is not a manufactured mount.

Preserved failures and repairs:

1. Parts01: rod length parameter moved design points but left actual end circles behind. Parts02 wrapper attempt failed on an unhashable COM identity. Parts03 adds explicit circle-center coincidence and passes. Edited/reopened STEP witnesses independently verify actual end-bore motion.
2. Bench01 passed initial motion but failed when imposing a hold immediately after reopening. `15_Jaw_Drive/jaw_reopen_diagnostic_01` showed required unlocked Update/Rebuild before holding. `15_Jaw_Drive/native_jaw_bench_initialized.py` supplies mandatory healthy initialization; bench02 passes. No geometry/pose tolerances were relaxed.
3. Design01 failed during preparation because installed NumPy rejects two-dimensional `np.cross`; design02 uses an explicit 2D determinant. Rejected outputs remain history, not accepted designs.

## Eyes, blink, materials and collision limits

Prior independent baseline: `14_Ocular_Function/native_functional_binocular_head_01/INTEGRATED_HEAD_PROTOTYPE.iam`, 49 parts/45 joints/seven inputs, 24 initial + 24 reopened + two releases. `14_Ocular_Function/functional_binocular_audit_01/FUNCTIONAL_BINOCULAR_INDEPENDENT_AUDIT.json` passes. The 53-part assembly preserves 47 prior source/reference parts exactly and transfers six jaw-bench parts, with carrier grounding adjusted for the head support chain.

Source geometry is attributed to Cogley/Ikkalebob under supplied CC BY-NC-SA 4 notices; retain notices and attribution. Source coordinates in millimetres are not physically measured scale. The negative-eye source is missing one ball and two rods; the native model uses virtual spherical/rigid joint relations. No replacement ball or rod geometry has been fabricated or inserted.

Source `core015/016` are thick eye cores; `cover006/007` are thin outer cover candidates. Four passive ocular attachments use corrected source clocking (opposite ±90° core rolls). There is no evidence of an independent iris actuator.

**Known source core/cover material overlap remains in the latest native head.** A separate disjoint proposed material partition exists in `14_Ocular_Function/eye_material_partition_study_01/generated_02/MATERIAL_PARTITION_STUDY_REPORT.json`: unchanged printed core plus proposed resin volume = original cover minus core. Geometry/topology/volume/sections/STEP reimport were checked. This is not chosen resin, manufacturing/bonding/optical validation and has not been imported into the native head.

Partition placement trap: proposed STEP/PLY/NPZ coordinates are in the **core optical frame**, not the old raw cover coordinates. Read `14_Ocular_Function/eye_material_partition_study_01/NATIVE_PLACEMENT_HANDOFF.json`. Keeping the current raw-local core, new resin-local→core is the frozen core optical-frame transform. Convert joint datums appropriately; never drop new resin geometry at the old cover pose.

Wider gaze reference: `14_Ocular_Function/geometric_gaze_workspace_01/` contains 27 full-49 targets (nine per eye individually and nine paired), 458 continuation states and a separate roundtrip/readback audit. Geometric straight ahead is a design reference, not physical servo zero.

`14_Ocular_Function/native_wide_gaze_replay_handoff_01/NATIVE_WIDE_GAZE_REPLAY_PACKET49.json` pins the exact nine paired transitions used by the 53-part spec. It has 2,466 single-coordinate commands/2,467 states with source closure/branch/rank checks. Read `14_Ocular_Function/native_wide_gaze_replay_handoff_01/UNIT_CONVERSION_ERRATUM.md`: packet arrays and engine `native_pose_mm` are already mm; raw Inventor matrix translations are cm and need ×10 on readback. Do not convert the report a second time. The packet's preserved wording error does not change its arrays. The additional `NATIVE53_WIDE_GAZE_REPLAY_AUDIT.json` in that same folder now passes: 18 wide endpoint observations plus six entry/exit/jaw-hold observations, all 26 eye poses, actual input/source-joint angles and 4,944 logged requested gaze assignments. These logs do not contain observed native passive poses at every microstep; continuous native closure/contact remains unverified.

Blink study: balanced coordinate −0.25..65°, not physical safe limits or full visual closure. Wider 75° was rejected; first checked peripheral collision bracket approximately 66.68..66.70°. Nearclosed slit is about 0.0324 mm. At q65 the source upper bridge actuator51/holder39 gap is only **0.0520 mm**; at q60 it is about 0.4897 mm. These are source geometry calculations, not manufacturing margins. Plan to revisit stops/travel/tolerance.

Collision handoff: `14_Ocular_Function/head_motion_collision_study_01/README.md` and `HEAD_MOTION_COLLISION_STUDY_SUMMARY.json`. Scope:

- 41 closed source meshes, 24 prior native plus nine paired wider-gaze states; 26,367 pair/state combinations. Six overlapping interface pairs explicitly retained: socket32/rod161, socket33/rod162, socket32/ball36, socket33/ball37, core015/cover006, core016/cover007. Intended joint context is not a fit exemption.
- Source-enclosure versus actual authored support/carrier/jaw bounds over 51 finite states.
- Only eight critical moving lid/ocular parts checked against cover-derived triangle surfaces; **26 moving-source/cover parts remain unchecked**.
- Corrected absolute OCCT meshing supersedes earlier incorrectly labelled relative deflection. Cover meshes remain nonwatertight; positive surface distances do not certify smooth-solid clearance/containment.
- Updated horn/rod/yoke geometry has six finite jaw checks. Updated yoke-only continuous enclosure preserves approximately 2.00 mm front/14.31 mm rear actual-cover CAD bounds; this is not continuous horn/rod/whole-head collision proof.
- The collision packet does not independently audit the subsequent 53-part native integration. Physical printed fit, installed fasteners/wires/servos, full motion collision, strength and dynamics remain open.

## Body and other unfinished work

Older seated proportion parent: `13_Head_Integration/native_supported_proportion_layout_01/PROVISIONAL_SUPPORTED_SEATED_LAYOUT.iam`. It still contains the older 35-part head clone, box and torso references. It has not been replaced with the 53-part head. Proposed head center is 723.9 mm above base, top 825.5 mm; a 38.1 mm empty neck space is provisional. There is no completed physical neck/torso/shoulder/knee structure or final skin.

Earlier native head work in `13_Head_Integration` includes actual authored support/carrier, split variable-wall covers, ideal jaw pivot and reference shaft/collars. Cosmetic skin, nose hole, fasteners and actual retainers remain unfinished. Declared 3 mm axis inset on the covers is not a uniform normal wall thickness.

Read the syringe/nose calculator and bench plan under `02_Mechanical_and_CAD/syringe_nose` and `06_Test_Plans_and_Results`. Ideal hydraulic volume math and synthetic tests exist; actual bore/stroke/friction/pressure/air/compliance/load/flow measurements do not. Never assign safe pressure or side-load capacity from nominal syringe capacity.

`08_Digital_Twin/REAL_PARTS_MANIFEST.json` still has **all 141 actual property values null**, actual `source_geometry.assembly_path` null, `simulation_ready=false`, `calibrated=false`, `physical_validation_complete=false`. It currently references the prior 49-part milestone; the newest native candidate has not been registered as an actual physical assembly. Preserve these truth conditions. Catalogue/design references may be added without populating unknown actual properties.

Older normalized show/control simulator and syringe calculator have software-only tests. `05_Host_and_Simulation/README.md`, `BEHAVIOR_PROTOCOL.md`, `06_Test_Plans_and_Results/SIMULATOR_RESULTS.md` explain scope. Host sends named behaviors; real-time controller handles limits/interlocks/fault response. No actual servo/controller backend, calibrated timing/current/load, physical speech/lip-sync or whole-robot dynamics should be inferred from synthetic tests.

## Runtime and native automation precautions

Python environment with numpy/scipy/CadQuery/OCP/matplotlib/pywin32/trimesh/manifold3d:

`C:\Users\alpha\Documents\ChatGPT\TSA Animatronics\.work\digital_twin_venv\Scripts\python.exe`

Use `-X utf8` on Windows. Inventor Professional 2027.1 was available; executable `Z:\inventor\Inventor 2027\Bin\Inventor.exe`. Do not assume current UI/documents are unchanged since the prior session; inspect before editing. No new native/COM operation was started for this handoff. The former long build process is no longer an active tool session and its final report exists.

Use **one COM worker at a time**. Offline analysis may run in parallel. Do not change scripts or frozen inputs while a native builder using them is active. Builders take additive new output directories and snapshot loaded modules. Preserve failed runs; do not overwrite accepted evidence.

Inventor API constants actually used: part document 12290; assembly 12291; rigid 102401; revolute 102402; ball 102406; healthy 11778; reference BOM 51972; millimetres 11269. DB coordinates are cm: poses in mm divide translations by 10 when sending, multiply by 10 on raw readback. Rotational `AngularPosition.Value` is radians; command expressions explicitly use degrees. Moving occurrence comes first in joint creation. Do not set `Rigid.Locked`. Force required `Update2(False)` and `Rebuild2(False)` and check health.

Use ownership-aware `open_owned_copy`, `owned_document`, `private_output_documents` helpers. Opening a preview marks a source assembly dirty in memory. A later SaveAs may save referenced state: before cloning, close **only a known-owned review** without saving and verify all saved native hashes. Never close/reset/save unrelated user documents. Last positively known review was the 49-part head opened at neutral/restored visibility, dirty in memory; current UI has not been inspected for this handoff. New 53-part preview was only staged at initial inspection.

Native leaf/source mesh identity limits are explicit: Inventor graphics/display buffers are not authoritative original triangle identities. Existing mesh checks do not justify inventing topology equivalence. Actual authored STEP exports have independent solid comparisons; preserve the distinction.

The repository also contains `software_pipeline`, `voice_behavior_study`, audio and assets from other work. Git has existing tracked modifications and untracked files there. Do not revert, delete, reformat, commit or overwrite unrelated work. No purchase, publish, submit, upload, outside contact or Claude-account action was authorized by this handoff request.

## Resume in this order

1. Read this file plus handoff status addendum, verify canonical paths, and inspect the final 53-part engine/scope reports. Keep full physical objective unfinished.
2. Review the finalized independent 53-part actual-observation audit and the wider-gaze replay audit/status addendum, resolving any remaining discrepancy from actual data. Do not waive geometry/branch/health gates. Native engine PASS and additional auditor PASS are separate claims.
3. Run the prepared 53-part native preview only after ownership/hash checks; inspect resulting images, restore neutral/visibility/input releases, and verify hashes. Then review milestone-registration script before updating documentation/prototype references. It must leave every actual property/readiness flag unchanged.
4. Make the servo choice and real horn/shaft/mount/pin-retention design concrete, using exact manufacturer geometry and actual fit evidence. Revisit the tight blink and rod margins. Add the disjoint eye material candidate to a **new** native variant only with correct optical-frame transforms and validation.
5. Progress hydraulic nose, physical neck, shoulder/knee, body load path and PC packaging with parameterized interfaces. Measure/calibrate the real specimens when available; populate actual registry only with traceable evidence.
6. Build calibrated dynamics/control validation incrementally. Quantify uncertainty and operating ranges; do not call an ideal kinematic or scripted visualization a 1:1 predictive simulation.

Do not restart the consolidated questionnaire, silently buy parts, reopen the deferred rubric discussion or present fabricated measurements. Continue useful independent engineering while awaiting physical inputs.
