# Phase 19: Detection Eval on Real Footage & Fine-tune Decision - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-14
**Phase:** 19-detection-eval-on-real-footage-fine-tune-decision
**Areas discussed:** Footage source & agility coverage, Ground-truth labeling approach, Metrics & fine-tune threshold, Fine-tune boundary (decide vs execute)

---

## Footage source & agility coverage

| Option | Description | Selected |
|--------|-------------|----------|
| Disc reale + agility da CC0 | Eval on real disc + fill agility/multi_dog cells with CC0 Pexels/Pixabay clips | |
| Solo disc, defer agility | Eval restricted to disc owner footage; agility deferred until real agility footage exists | ✓ |
| Ho footage agility mio | User has consented agility footage to use | |

**User's choice:** Solo disc, defer agility
**Notes:** Owner corpus is disc-only (FIDASC `gara_full.mp4` + per-condition cuts). Do NOT synthesize agility coverage with CC0. DET-01/DET-03 scope to disc for v1.4; agility eval carried forward to a future milestone. Coverage report flags agility cells as carried-forward, not filled.

---

## Ground-truth labeling approach

| Option | Description | Selected |
|--------|-------------|----------|
| Script bbox leggero + sampling sparso | Internal opencv-only tool, sparse per-condition frame sampling, manual in-competition-dog bbox, zero external deps | ✓ |
| CVAT/Roboflow esterno | Assisted labeling in a dedicated tool, COCO/YOLO export | |
| Auto-label modello forte + review | Pre-label with a big YOLO/SAM then correct | |

**User's choice:** Script bbox leggero + sampling sparso
**Notes:** Auto-label rejected — would inherit the same distant-dog miss bias the eval must measure independently. ~few hundred frames total, sampled per condition. "In-competition dog" = the subject the competitor-lock grabs (not handler, not bystander dogs).

---

## Metrics & fine-tune threshold

| Option | Description | Selected |
|--------|-------------|----------|
| Recall distante assoluta + guard precision | distant recall@IoU0.5 < threshold → fine-tune; precision guard against false-lock | ✓ |
| Gap vs cane vicino/pulito | Fine-tune if distant recall is >X points below near/clean recall | |
| Decisione qualitativa dal report | No pre-set numeric threshold; decide from the report case by case | |

**User's choice:** Recall distante assoluta + guard precision
**Notes:** Starting threshold distant-dog recall@IoU0.5 < 0.70 → fine-tune, tunable in CONTEXT once real numbers land. Precision reported as a false-lock guard (handler/shadow/bystander). Measured on the FP16 batched shipped path, not the eager FP32 serial `lock_held` proxy.

---

## Fine-tune boundary (decide vs execute)

| Option | Description | Selected |
|--------|-------------|----------|
| Solo decisione + spec del fine-tune | Stop at go/no-go + fine-tune spec if "go"; training is a separate follow-up | ✓ |
| Decisione + eseguo il fine-tune se 'go' | Include producing the fine-tuned weight (auto-label + training run) and re-measure | |

**User's choice:** Solo decisione + spec del fine-tune
**Notes:** Phase 19 is desk-sized — deliverable is the metrics-backed decision doc; if "go," also a dataset/approach spec. Actual training deferred. Matches roadmap wording ("decision documented" + "drop-in via config path"). "No-go" (COCO dog good enough) is a valid first-class outcome.

## Claude's Discretion

- Exact sampling stride N, GT sidecar file format, labeling-tool UX (opencv-only, no external service).
- Whether recall/precision extend `run_clip_eval`'s return dict or a new sibling eval function.
- Precise structure of the decision doc / report artifact.

## Deferred Ideas

- Agility detection eval (tunnel/contact occlusion, midfield-equidistant, agility multi-dog) — needs real agility footage.
- Running the actual fine-tune training + shipping a fine-tuned weight — follow-up gated on a "go" decision.
- CC0 footage sourcing — only when the deferred agility eval is picked up.
- Framing/tracking seed calibration on real footage — that is Phase 20 (CAL-01/02).
