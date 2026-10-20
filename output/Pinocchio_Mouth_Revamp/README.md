# Pinocchio mouth revamp: flexible lips, 7 servos

Modelled on the reference video (YouTube Ke2lJfY4haM): flexible printed lips moved by servos at control points.

- **Expressions:** `Mouth_Expressions.png` (full head) and `Mouth_Poses_Closeup.png` (all 16 poses).
- **Comparison:** `Mouth_Before_After.png` (old build 35 vs new).
- **Mechanism:**
  - `Mouth_Mechanism_XRay.png` (shell hidden);
  - `Head_Internals.png` and `Head_Internals_No_Shell.png` (the whole head, four angles).
- **Bench test rig:** `Bench_Rig_Front.png` and `Bench_Rig_Rear.png`. It's a printable rig to try the mouth with 5 servos before building the head; the print list, wiring and Arduino sketch are in `WORK_PRODUCT\18_Mouth_Revamp\bench_rig_01`.
- **Review model:** `Pinocchio_Mouth_Revamp.blend` (neutral pose, full head).

How it moves:
- Each mouth corner moves up/down and in/out on two servos.
- The upper-lip and lower-lip centres have one servo each.
- The jaw is unchanged.
- TPU lips sit on the face, and skin-tone TPU pads ride on the corners.

The design notes, pose/servo table and checks (all PASS) are in `WORK_PRODUCT\18_Mouth_Revamp\README.md`. This is a concept with catalogue servo dimensions, not a print release.
