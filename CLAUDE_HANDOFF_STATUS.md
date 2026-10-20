# Final handoff status — 16 October 2026

Read [CLAUDE_HANDOFF.md](CLAUDE_HANDOFF.md) for project context, canonical paths, evidence limits and continuation instructions. This status supersedes earlier messages saying the newest native run or independent audits were pending.

| Item | Final status |
| --- | --- |
| 53-part native head | PASS: 35 initial + 35 saved/reopened + two released observations |
| Independent full-head audit | PASS: all 72 observations, 54 native hashes, 48 joint markers, actual inputs and passive jaw/rod |
| Independent wider-gaze replay audit | PASS: 18 wide endpoints + six supporting observations; 4,944 logged requested assignments independently solved |
| New 53-part preview | Not run; prepared script exists |
| New jaw milestone/README/registry registration | Not run; staged script requires preview and review |
| Actual real-part physics | Unfinished; 141 actual property values null; actual assembly path null; readiness/calibration/physical validation false |
| CAD/COM launched for handoff | None. Only file reads, offline audits and handoff document writes |

Canonical work product:

`Z:\Downloads\Codex_Work_Block_Instructions-20261012T225555Z-1-001\Codex_Work_Block_Instructions\WORK_PRODUCT`

Authoritative final artifacts relative to that directory:

- `15_Jaw_Drive/native_functional_jaw_head_01/INTEGRATED_HEAD_PROTOTYPE.iam`
- `15_Jaw_Drive/native_functional_jaw_head_01/native_integrated_head_report.json`
- `15_Jaw_Drive/native_functional_jaw_head_01/FUNCTIONAL_JAW_HEAD_SCOPE_REPORT.json`
- `15_Jaw_Drive/jaw_drive_audit_01/NATIVE_HEAD53_INDEPENDENT_AUDIT.json`
- `14_Ocular_Function/native_wide_gaze_replay_handoff_01/NATIVE53_WIDE_GAZE_REPLAY_AUDIT.json`

Pinned SHA-256:

| Artifact | SHA-256 |
| --- | --- |
| Native head engine report | `03cd06d87a9229d90ef292d98b83b13e9b6f9475bcb8af7d1fc76c69dbce0438` |
| Native head scope report | `82ca09377691ebc9753db9b15dfbde99ac9f1702cf145c3874bc189f85853d4a` |
| Full-head independent audit | `7d00f226cecaec22901c19fecdb645964d36ff89ba7cb7761bbf053c87cf368b` |
| Wider-gaze native replay audit | `cd24dd76a6a1c9251c1d9cd84f14854628d2eaf40f06e361ef2dcecc6398edf8` |
| Frozen wider-gaze packet | `e7a0751305540016baeb7b5748a691ab94b2588eee3798f2a339b31283457a5c` |

The handoff verification JSON records current native/input/code hashes and unknown-property invariants. Numerical agreement above is evidence about the CAD/source models, not measured physical accuracy. The original eye core/cover overlap, source missing hardware, tiny clearances, actual servo/horn/mount/retention and full dynamics remain open.

The first full-head audit helper rejected unchanged target reassertions as new gaze macrosteps; the additive `audit_native_head53_02.py` corrected that bookkeeping while retaining the numeric/geometry/health gates. No frozen source/native data changed. Wider-gaze audit independently re-solves logged requested states; it does not claim observed native passive poses or collision checks after every command.

Copy this into Claude in the same workspace:

> Read `C:\Users\alpha\Documents\ChatGPT\TSA Animatronics\CLAUDE_HANDOFF.md` and `CLAUDE_HANDOFF_STATUS.md`. Continue the existing Pinocchio animatronics engineering project from its canonical Z: work product. The 53-part native head and both independent audits have passed; first finish the prepared native preview and carefully reviewed milestone documentation, then continue real actuator interfaces and the remaining mechanics. Preserve source/history/unrelated work. Treat the CAD as provisional design kinematics: the requested calibrated real-part simulation remains unfinished. Do not restart the questionnaire or assume unknown hardware properties.

No external message or upload was made. Handoff files are available in the workspace and copied to the canonical work product's `00_Progress_and_Decisions/claude_handoff_2026-10-16/` directory.

## Update — Claude session, 16 October 2026 (after handoff)

Steps 1–3 of "Resume in this order" are done. This supersedes the "Not run" rows above for the preview and registration.

- Before starting: canonical paths verified; all five pinned SHA-256 values matched; no COM worker was running. Inventor 2027.1 had 210 owner documents open, none from `15_Jaw_Drive`, so the preview's ownership precondition held. Unrelated documents (including the dirty 49-part head) were not touched.
- **53-part native preview: PASS.** `15_Jaw_Drive/native_functional_jaw_head_01/previews_01/` holds four views + `NEUTRAL_RESTORED.png` + `PREVIEW_REPORT.json`, status `FUNCTIONAL_JAW_HEAD_NATIVE_REVIEW_EXPORTED` at 2026-10-16T20:55:32Z. Max pose error ≤5.6e-10, closure ≤1.3e-11, all joints healthy, all 54 native hashes unchanged, neutral restored with all seven holds released and original visibility restored. The review assembly is left **open and dirty in memory, unsaved**; close only it, without saving, before any future clone.
- **Milestone registration: done** through the additive `15_Jaw_Drive/record_jaw_checkpoint_02.py`. The staged `record_jaw_checkpoint.py` is preserved unexecuted. The revision adds the wider-gaze replay audit as a hash-pinned prerequisite and reference, corrects dates (native run 15 Oct, registration 16 Oct), removes stale goal-loop wording, and guards against overwriting the README. Outputs: new `15_Jaw_Drive/README.md`, a top line in `README.md`, a new top entry in `PROGRESS_LOG.md`, and new references in the manifest's `source_geometry`. Before-copies and `JAW_HEAD_MILESTONE_CHECKPOINT.json` are in `15_Jaw_Drive/handoff_checkpoint_01/`.
- The registry invariants were re-verified afterwards: 141 actual values null, actual `assembly_path` null, `simulation_ready`/`calibrated`/`physical_validation_complete` false, and `parts` unchanged.
- Still open: steps 4–6 (exact servo/horn/shaft/mount/retention, tight blink and rod margins, eye material variant, nose/neck/limbs/PC packaging, calibrated dynamics). The owner has not selected an exact servo variant, and syringe measurements are still pending.

## Update — step 4 started, 16 October 2026

The owner chose to design against the TowerPro SG90 catalogue geometry as a parameterized reference, keeping all dimensions open until a real servo is measured. Results are in `15_Jaw_Drive/servo_interface_study_02/README.md`:

- **Model and study:** `servo_interface_model.py` and `prepare_servo_interface_study.py`. The study passes the nominal set plus 16 placeholder corners at 43 crank samples and all 33 eye states. The minimum non-intended gaps are the designed 0.25, 0.4 and 0.5 mm values, then 0.78 mm at the worst corner.
- **Independent audit:** `servo_interface_audit_01` passes 56 checks.
- **Run 01:** preserved with a superseded note. It found an adapter-on-shaft contact and a weak first relief shape.
- **Rod margin:** a candidate lip-relief yoke raises rod–yoke clearance from 0.5 to 1.0 mm with no kinematic change.
- **Blink margin:** q ≤ 60° is the provisional software limit.
- **Native work:** none yet. The next native step is an additive 53-part variant using the cheek carrier, adapter, shims and relieved yoke, run only after measured servo and horn values replace the placeholders, or explicitly as a placeholder build.
- **Still open:** the eye material partition native variant, the six eye-servo bodies (not modelled), the nose, neck and body, and dynamics.

## Update — eye servo packaging, 16 October 2026

Results are in `14_Ocular_Function/eye_servo_packaging_02/README.md`. The independent audit (`eye_servo_packaging_audit_02`) passes 28 checks. Key outcomes:

- **Blink limit:** lower lids hit the creator's base plates above 57.88°. The provisional limit is now **q ≤ 55°**; the earlier 60° is withdrawn.
- **Outer gaze horns:** their unused inboard arms sit inside the neighbouring inner servos in the creator's own CAD. Use single-arm or trimmed horns.
- **Jaw servo:** it is within 0.05 mm of the outer gaze servo if its shaft is 4 mm from the body end. A 35° rearward tilt fixes this (`15_Jaw_Drive/jaw_servo_tilt_trade_01`), but the cheek still needs regenerating at that angle.
- **Clearances:** support, carrier, covers and jaw moving parts all clear the new parts by at least 3.2 mm.

## Update — jaw servo tilted 35°, 16 October 2026

- **Current jaw servo candidate:** `15_Jaw_Drive/servo_interface_study_03` (`servo_tilt_deg = 35`). It clears the outer gaze servo by at least 4.08 mm across all placeholder corners. The audits pass: `servo_interface_audit_02` (61 checks) and `eye_servo_packaging_audit_03` (31 checks).
- **Measuring guide:** `06_Test_Plans_and_Results/MEASUREMENT_GUIDE_SERVO_HORN_SYRINGE.md` plus `MEASUREMENT_SHEET_SERVO_HORN.json`. Once filled in, regenerate the mount from the measured values and rerun both studies and audits.
- **Still open:** native Inventor variant, cheek strength, eye material native variant, nose, neck and body, dynamics.

## Update — neck/shoulder/knee layout, 16 October 2026

- **Layout:** `16_Neck_Shoulder_Knee_Layout/layout_study_02/README.md`, a concept layout with no conflicts. Audit `layout_audit_01` passes 18 checks.
- **Neck:** yaw axis 32 mm behind the head centre; the rear cover needs a ~24 mm opening.
- **Actuators:** on high mass estimates, the shoulders and knees are too heavy for 9 g servos.
- **Parallel sessions started from the coordinating session:** the eye core/resin native variant (`eye-partition-native`, writes under `14_Ocular_Function`) and the jaw mount strength check (`jaw-mount-strength`, writes under `15_Jaw_Drive/servo_mount_strength_01`). Their results are integrated into PROGRESS_LOG by the coordinating session.

## Update — parallel session results, 17 October 2026

- **Eye core/resin variant:** `14_Ocular_Function/native_eye_partition_head_01` passes all 72 native observations and its independent audit. It is not registered; the 53-part head stays the milestone.
- **Jaw mount strength** (`15_Jaw_Drive/servo_mount_strength_01`): study 03 is too weak (RF 0.19–0.32 at 2× stall). Variant D is recommended.
- **Variant D is the clearance-checked jaw mount candidate:** `15_Jaw_Drive/servo_interface_study_05`, with audits `servo_interface_audit_03` (74 checks) and `eye_servo_packaging_audit_04` (36 checks).
- **Still to do:** the neck/shoulder/knee layout re-check against variant D was proposed by the variant D session but not run.

## Update — face art direction, procedural face and big eyes, 17–18 October 2026

All work is in `17_Face_Art_Direction`. No native, registry, purchase or physical change. The registered 53-part head is unchanged.

**Owner decisions:**
- **Look:** a stylized marionette look, using a Pinocchio marionette photo as the reference.
- **Eyes:** big round eyes behind 33 × 44 mm oval openings. Keep the lid holders and servos (option A).
- **Gaze:** sideways gaze limited to ±12° in software; vertical stays ±10°.
- **Lower lid:** notch the creator's eye-servo front strip and bases so it keeps its full 55° travel.

**Outputs:**
- Sculpting kit `sculpt_kit_01`; chin block `chin_block_01`.
- Procedural face `face_model.py`: build 03 (small eyes) and build 04 (current, big eyes).
- Big-eye parts and servo notches: `big_eye_variant_01`.
- Feasibility studies: `big_eye_feasibility_01`.

**Checks (all PASS):**
- Face clearance on builds 03 and 04.
- Independent audits `face_model_audit_03` and `_04`.
- Big-eye gaze × blink check, with blink limit 55°.
- Servo-notch mount check.

**Tooling:**
- `clearance_fast.py` gives the same results as `face_check.py` in about 2 minutes instead of 1.8 h (`clearance_fast_validation_01`).
- When piping long runs through `grep`, use `--line-buffered`, or write to a log file instead.

**Open:**
- Physical mass and torque of the bigger lids (about 1.9×) and the new caps.
- The ±12° gaze limit must be enforced in the controller.
- The face parts are not yet in the sculpt kit.
- Not a print release.


## Update — face builds 05–14, overnight improvements, 18 October 2026

**Current:** `17_Face_Art_Direction/face_model_14`, with its README, `ASSEMBLY_AND_PRINT_GUIDE.md` and `PRINT_ESTIMATES.json`.

**Owner requests completed:**
- slanted lower-lid line;
- hat removed by default, now an optional part;
- hair after the reference: thick and wavy, swooping to the centre;
- eye liner 0.5 mm brown, satin finishes, bigger irises;
- upturned nose (28°, its hole and slide axis tilted);
- cupped ears;
- lip rolls and mouth paint.

**Overnight CAD:**
- locating lip and 6 magnet boss pairs on the front/rear split;
- hair registration bumps and sockets;
- neck cover;
- back-of-head hair locks;
- rounded mouth edges.

**Checks on build 14:**
- Audit `face_model_audit_14`: PASS, 32 checks.
- `clearance_fast.py`: PASS.
- Big-eye check with the tilted nose: PASS, blink limit 55° (`face_model_10/BIG_EYE_CLEARANCE_WITH_BUILD10_NOSE.json`).

**Sculpt kit:** `sculpt_kit_03`, from build 13.

**Backup:** `WORK_PRODUCT/_backups/17_Face_Art_Direction_backup_2026-10-18_0330.tar`.

**Open:**
- head mass of about 540 g (neck torque);
- the 3.4 mm mouth slit comes from the jaw's 2° closing overtravel (owner decision);
- a faint crease on the hat brim;
- not a print release.

## Update — face builds 15–16, 18 October 2026

**Current:** `17_Face_Art_Direction/face_model_16`. It is build 14 plus the following:
- a curved nape on the back hair, and a lighter back base (hair 242.6 cm³);
- the hat as one solid, with drain vents and band paint only on the crown wall;
- 2 magnet pairs that hold the optional hat on.

**Checks:** audit `face_model_audit_16` PASS (32 checks); clearance PASS.

**Mass:** about 503 g without the hat. **Sculpt kit:** `sculpt_kit_04` (build 15).

**Hardware:** 12 shell magnets plus 4 hat magnets, all Ø6 × 3 mm.

## Update — face builds 17–18, 18 October 2026

**Current:** `17_Face_Art_Direction/face_model_18` (v20). It is build 16 plus the following:
- a rounder jaw, from a plan-curved cap (half-width at z −60 goes from 65.1 to 59.2 mm);
- the lower magnet bosses moved to (±56.5, z −50);
- a root web bonding the locating lip;
- a 0.05 mm split gap.

**Rejected:** build 17's flat cap, which left a facet.

**Checks:** audit PASS (32 checks); clearance PASS. The rear head to jaw carrier gap is now 1.141 mm, which is the binding limit: a rounder jaw needs a narrower jaw carrier.

**Mass:** about 502 g without the hat. **Sculpt kit:** `sculpt_kit_05` (build 18).

## Update — face build 19, 18 October 2026

**Current:** `17_Face_Art_Direction/face_model_19` (v21). It is build 18 plus apple cheeks (r 14 bumps, about 4 mm proud at (±44, z −10)).

**Checks:** audit PASS (32 checks); clearance PASS, with the gaps unchanged.

**Mass:** about 503 g without the hat.

**Docs:** `face_model_19/ASSEMBLY_AND_PRINT_GUIDE.md` is current, with the 16 magnets and the new lower boss positions. `sculpt_kit_06` is build 19.

## Update — jaw carrier narrowing study, 18 October 2026

**Studies:** `15_Jaw_Drive/carrier_narrowing_study_01` and `17_Face_Art_Direction/jaw_taper_trimmed_carrier_01`.

**Recommended carrier trim, T2:** a chamfer on the servo-side extension block from Z −47 down to X −42.5. Voxel FE: jaw error 0.78 → 0.81° per stall; lowest p01 RF 1.20 → 1.17.

**What it allows:** a candidate face whose jaw is about 5 mm narrower per side at the bottom (Z −66 half-width 56.8 → 51.4 mm).
- Against T2: clearance PASS (1.063 mm), audit PASS (32 checks).
- It overlaps the as-built carrier, so the face and the carrier change must be adopted together.

**Pending:** owner decision. Build 19 and variant D are unchanged.

## Update — T2 carrier adopted, face build 20, 18 October 2026

**Current face:** `17_Face_Art_Direction/face_model_20` (v22): a narrower lower jaw, half-width at z −66 56.9 → 51.6 mm.
- Audit PASS (32 checks); clearance PASS against the T2 carrier (1.063 mm); mass about 501 g.

**Current jaw candidate:** `15_Jaw_Drive/servo_interface_study_06`, variant D plus the T2 extension chamfer.
- Clearance PASS for all 17 sets; audit 04 PASS (79 checks); FE jaw error 0.81° per stall.
- **Face build 20 requires this carrier.**

**Correction:** the lower magnet bosses are now at (±53.25, z −52.5). Builds 18–19 had the −x boss 5.75 mm from the jaw servo envelope, under the 6 mm rule.

**Sculpt kit:** `sculpt_kit_07`.

## Update — reference hair revision, 18 October 2026

Current cosmetic face: `17_Face_Art_Direction/face_model_21`, procedural source v23. Broad smooth asymmetric fringe, rounded off-center tip, much softer front ridges; original sideburn outline and rear service seam retained. HAIR_FRONT and optional HAT regenerated; six other printed STLs byte-identical to build 20. Independent audit 21 PASS, 32 checks. Detailed build-20 clearance inherited by unchanged hashes, not rerun. Sculpt kit 08 and full-resolution rendered review Blender file saved. Convenience model and before/after preview are in workspace `output/Pinocchio_Hair_Revision`. No change to native registered assembly or physical validation.

## Update — raised two-strand hair correction, 18 October 2026

Current cosmetic face is build 23 (source v25), sculpt kit 09. Owner corrected the flattened build 21: preserve its hairline but restore two big raised low-poly strands swooping toward center. Build 23 uses two broad asymmetric locks swept from viewer-left; build 22 is an unselected center-part draft. Full-resolution HAIR_FRONT and optional HAT regenerated. Six other printed STLs byte-identical to build 21. Independent audit 23 PASS, 32 checks. Native assembly and physical validation unchanged. Local `output/Pinocchio_Hair_Revision/Pinocchio_Raised_Hair.blend` is current, and `Pinocchio_Updated_Hair.blend` was also updated.

## Update — leading inner hair strand, 18 October 2026

Current cosmetic face build 24, source v26, sculpt kit 10. Inner raised strand alone forms the final forelock tip; the outer strand ends earlier against its side, fading to zero relief below Z=83.48. Inner path/height, upper outer volume and hairline retained from build 23. Audit 24 PASS, 32 checks; six other printed STLs byte-identical. Current local model `output/Pinocchio_Hair_Revision/Pinocchio_Leading_Strand.blend`; old local model aliases updated too. Native assembly/physical validation unchanged.

## Update — fuller left hair strand, 18 October 2026

Current cosmetic face build 25, source v27, sculpt kit 11. Owner wanted left strand closer to original full sweep. Its build-23 path/width/height are restored; build-24 horizontal cutoff removed. Only the centerward end fades under the unchanged middle strand, which alone forms the final point. Audit 25 PASS, 32 checks. Six other printed STLs byte-identical to build 24. Current local model `output/Pinocchio_Hair_Revision/Pinocchio_Leading_Strand.blend`, preview `Fuller_Left_Strand.png`. Native assembly/physical validation unchanged.

## Update — reference eyebrow placement, 18 October 2026

Current appearance build 26, sculpt kit 12. Eyebrows traced separately from owner photo, calibrated to 65 mm eye spacing and roll corrected; placed higher and outward. Editable helper `eyebrow_placement.py` is called from the main render-asset generator. All 80 centerline points projected onto face; none hidden by hair; front/three-quarter renders inspected. All eight physical STLs and other appearance assets byte-identical to build 25. Physical audit 25 inherited, not rerun. Hair/source remain build 25 / v27. New workspace model `output/Pinocchio_Face_Revision/Pinocchio_Updated_Eyebrows.blend`; old local aliases updated. No native/physical validation change.

## Update — mirrored left eyebrow shape, 18 October 2026

Current appearance build 27, sculpt kit 13. Owner approved right brow and asked to copy/flip it. Right triangle geometry unchanged; left frontal curve is an exact reflected copy, retained at exposed left placement because a center-position mirror is behind hair. Eight physical STLs unchanged. Current local `output/Pinocchio_Face_Revision/Pinocchio_Mirrored_Eyebrows.blend`; local model filenames share one current hard-linked file. Prior canonical versions preserved.

## Update — upward-tilted ears, 18 October 2026

Current face build 28/source v28/sculpt kit 14. Both ears tilted outward/upward 32°, centers raised 9 mm, cup/rim dimensions retained. Four shell/hair parts rebuilt at 0.6 mm. Approved eyebrows and other appearance assets preserved. Independent audit 28 PASS, 32 checks; fast clearance PASS. Chin/nose/neck/hat unchanged. Local `output/Pinocchio_Face_Revision/Pinocchio_Upturned_Ears.blend`; other local names are current hard-linked aliases. Native assembly and physical validation unchanged.

## Update — eyebrows restored, ears retained, 18 October 2026

Current face build 29 / physical source v28 / sculpt kit 15. Original pre-edit eyebrows restored exactly from build 25. All eight physical parts (including upward-tilted ears) and other appearance assets unchanged from 28; inherited physical validation, no new audit run. Active eyebrow generator reverted, ear blush retained. Front and three-quarter renders reviewed. Current local `output/Pinocchio_Face_Revision/Pinocchio_Restored_Eyebrows.blend`; earlier local model filenames are hard-linked aliases.

## Update — face build 30, 18 October 2026

**Current face:** `17_Face_Art_Direction/face_model_30` (v30). It is Codex's build 29 plus:
- cheeks widest (half-width 76.8 mm at z −8);
- temples and eye level pinched 8–13 mm a side;
- ear-level magnet bosses at (±69, z 0).

**Checks:** audit PASS (32 checks); clearance PASS; mass about 496 g.

**Sketches:** `hourglass_sketch_01` and `hourglass_sketch_02`.

**Not yet regenerated:** the sculpt kit; the latest is Codex's kit 15, which is build 29.

## Update — face build 32, 18 October 2026

**Current face:** `17_Face_Art_Direction/face_model_32` (v32). It is build 30 plus:
- the side above the eyes made straight (v31);
- a near-semicircle lower face, with no pinch below the cheeks (v32).

The cheeks stay the widest part (76.9 mm).

**Checks:** audit PASS (32 checks); clearance PASS; mass about 499 g.

**Not yet regenerated:** the sculpt kit; the latest is Codex's kit 15, which is build 29.

## Update — face build 33, 18 October 2026

**Current face:** `17_Face_Art_Direction/face_model_33` (v33b). It is build 32 with wider cheeks (82.9 mm half-width, was 76.9), and the round lower face scaled to match.

**Checks:** audit PASS (32 checks); clearance PASS; mass about 508 g.

**Not yet regenerated:** the sculpt kit; the latest is Codex's kit 15, which is build 29.

## Update — face build 34, 18 October 2026

**Current face:** `17_Face_Art_Direction/face_model_34` (v34):
- one smooth cheek mass per side (no ball look), cheeks 82.6 mm half-width;
- a slimmer jaw;
- the blush is the original, moved to x ±64.

**Checks:** audit PASS (32 checks); clearance PASS; mass about 504 g.

**Not yet regenerated:** the sculpt kit; the latest is Codex's kit 15, which is build 29.

## Update — deeper profile, 18 October 2026

Current face build/source 35, sculpt kit 16, based on latest canonical build 34. Forehead +6 forward/rear cranium +14 back, cheeks +7, chin +10, nose root/bore +8 mm. Eye centers/jaw pivot/neck axis fixed. Body depth +17% at lower face. Original brows, raised hair styling and upward ear geometry retained. Eight parts remeshed, including neck cover refitted after inherited-cover overlap was caught by first audit; 32-check final independent audit PASS and clearance PASS. Local `output/Pinocchio_Face_Revision/Pinocchio_Deeper_Profile.blend`; comparison `Side_Profile_Before_After.png`. No physical validation.

## Update — mouth revamp, face build 36, 18 October 2026

Owner asked to completely revamp the mouth after YouTube Ke2lJfY4haM and chose the 7-servo option.

**Design:** `18_Mouth_Revamp` (README, `mouth_poses.py`, `mouth_model.py`, `check_mouth.py`, `render_mouth.py`); outputs in `mouth_design_01`.
- The jaw drive is unchanged.
- Each corner uses a two-servo planar five-bar.
- The upper-lip and lower-lip centres have one servo each; the lower one rides on the jaw yoke.
- The lips are TPU, and skin-tone TPU corner pads cover the corner slots.
- A black frame plate sits on four FACE_FRONT posts.

**Shell:** `17_Face_Art_Direction/face_model_36` (v36). The lip rolls are removed and a hidden mouth opening, slots, notch and posts are added.

**Checks (all PASS):**
- mouth clearance, 7,865 measurements;
- kinematics tests, 8;
- face clearance;
- audit 36, 43 checks.

**Impact:**
- about +76 g, head about 580 g;
- 13 head servo channels, so a second PCA9685 is needed.

**Open:**
- real servo/horn/TPU measurements and lip forces;
- clip and fork details;
- controller integration (`software_pipeline` only knows `jaw`);
- the nose drive, kept clear by a provisional r 14 corridor.

**Review files:** local previews in `output/Pinocchio_Mouth_Revamp`. The review `.blend` stays only in the canonical folder because C: is full (about 0.3 GB free).

No native, registry, purchase or physical change. Not a print release.

## Update — overnight follow-ups, 19 October 2026

**Neck** (`16_.../neck_head36_recheck_01`):
- Current head estimated at 0.71–1.06 kg, about double the old estimate.
- Bearing tipping moment 0.22–0.33 N·m.
- Recommendation: a metal-gear standard servo (or a geared 9 g servo) on the neck yaw, plus a turntable bearing.

**Electrical** (`03_.../channel_power_after_mouth_01`, planning only):
- Two PCA9685 boards: head channels 0–12, body 0–8.
- Planning current ranges; the measurement gate is unchanged.

**Mouth:**
- `print_ready/`: clips, pins, screw holes, C-frame lower bracket, plate in two halves. Clearance PASS.
- `bench_rig_01`: printable 5-servo rig with an Arduino sketch.

**Sculpt kit:** `sculpt_kit_17`.

**C: drive:** cleaned from 0.19 to about 16 GB free.
- Removed: caches and old temp files.
- Moved: Downloads moved to `Z:\C_Drive_Offload` (log there).
- Left for the owner: Windows' page file is about 47 GB because many apps had been open for days, so a reboot would free more.

## Update — narrower chin seams, face build 37, 19 October 2026

Current face: `17_Face_Art_Direction/face_model_37` (v37).
- The chin side seams are 0.6 mm (lateral to the jaw axis), down from ~2 mm, with crisper edges.
- A skin-tone backing strip on the face sits behind the visible part of each seam.

**Checks:** face clearance PASS (seam 0.773 mm under a new ≥ 0.55 rule for side seams only); audit 37 PASS (46 checks); mouth clearance PASS.

**Physical:** jaw pivot side play under ~0.3 mm.

**Not yet updated:** sculpt kit 17 still has build 36 seams.

## Update — mouth box, mouth design 02, 19 October 2026

**Current mouth design:** `18_Mouth_Revamp/mouth_design_02`.
- A fixed roof (bonded in the face), a jaw tray with tongue (bonded in the chin) and a fabric mouth bag hide the servos when the jaw opens.
- The upper-lip hooks moved to x ±21.5.

**Checks:** mouth clearance PASS vs face build 37; print details PASS.

**Git:** the workspace previews were pushed earlier on branch `pinocchio-mouth-revamp` (*.blend excluded). The canonical CAD on Z: is not in git.

## Update — corner pads vs moving chin, 19 October 2026

**Finding:** the v1 corner pads collided with the opening chin (pre-existing bug; the checks used only the closed chin).

**Now:**
- `check_mouth` tests against the moving chin;
- pads are trimmed clear (PASS);
- a jaw/corner interlock has been added;
- but the trimmed pads leave the corner slot visible.

**Owner decision pending:** (A) corner travel above the mouth line, (B) silicone corner skin, or (C) accept the gaps. See PROGRESS_LOG.

## Update — corner band, pad v3, face build 38, 19 October 2026

**Owner chose option A** (corner travel above the mouth line).

**Current versions:** `18_Mouth_Revamp/mouth_design_03` and `17_Face_Art_Direction/face_model_38`.
- The corners move in a band >= 1.7 mm above the chin line.
- The chin has no corner slots.
- The pads are derived smile-crease crescents that stay >= 1.56 mm off the opening chin.
- The frown is milder (narrow and down).
- Interlock: corners >= 2.5 mm above the band's lower edge before any jaw < 0.

**Checks:** mouth clearance PASS (8,866 measurements), face clearance and audit PASS (50), print details PASS, tests 9/9.

**Not yet updated:** bench_rig_01 (v1 poses) and sculpt_kit_17 (build 36).
