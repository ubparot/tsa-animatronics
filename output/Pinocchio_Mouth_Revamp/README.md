# Pinocchio mouth revamp: flexible lips, 7 servos

Modelled on the reference video (YouTube Ke2lJfY4haM): flexible printed lips moved by servos at control points.

- **Expressions:** `Mouth_Expressions.png` (full head) and `Mouth_Poses_Closeup.png` (all 16 poses).
- **Comparison:** `Mouth_Before_After.png` (old build 35 vs new).
- **Mechanism:**
  - `Mouth_Mechanism_XRay.png` (shell hidden);
  - `Head_Internals.png` and `Head_Internals_No_Shell.png` (the whole head, four angles).
- **Bench test rig:** `Bench_Rig_Front.png` and `Bench_Rig_Rear.png`. It's a printable rig to try the mouth with 5 servos before building the head; the print list, wiring and Arduino sketch are in `WORK_PRODUCT\18_Mouth_Revamp\bench_rig_01`.
- **Corner pads (19 Oct):**
  - `Corner_Pad_V1_V2_V3.png`: v1 square pad (hit the opening chin), v2 trimmed pad (slot showing), v3 now.
  - `Corner_Band_neutral_Closeup.png` and `Corner_Band_big_smile_Closeup.png`.
  - The corners now stay above the chin line. The pads are small smile-crease crescents, and the frown is milder.
  - `Corner_Pad_Trim_Problem.png` is the earlier v2 problem.
- **Review model:** `Pinocchio_Mouth_Revamp.blend` (mouth design 03, face build 38, neutral pose).

How it moves:
- Each mouth corner moves up/down and in/out on two servos.
- The upper-lip and lower-lip centres have one servo each.
- The jaw is unchanged.
- TPU lips sit on the face, and skin-tone TPU pads ride on the corners.

The design notes, pose/servo table and checks (all PASS) are in `WORK_PRODUCT\18_Mouth_Revamp\README.md`. This is a concept with catalogue servo dimensions, not a print release.
