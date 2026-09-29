# Soccer interpretation and immediate-action reference

Version: soccer-context-v1. Maintained: 2026-09-29. Owner: PitchState maintainers.

This document is executable domain context: `tactics.py` loads the marked runtime section into every Jev state, hashes it for provenance/cache invalidation, and derives the corresponding geometric features. Update the reference, feature tests and scenario checks together. Sources describe football principles; numeric thresholds below are engineering hypotheses, not FIFA definitions or calibrated likelihoods.

## Sources and scope

- [FIFA: Using wide areas to play around a low block](https://www.fifatrainingcentre.com/en/practice/elite-sessions/in-possession/gygax-attacking-in-wide-areas.php): width, coordinated movements, overlaps, crosses and cutbacks.
- [FIFA: Combination play in the final third](https://www.fifatrainingcentre.com/en/practice/elite-sessions/in-possession/combination-play-in-the-final-third.php): supporting options, timed box occupation and coordinated finishing movements.
- [FIFA: Team organisation out of possession](https://www.fifatrainingcentre.com/en/game/game-analysis/out-of-possession/team-organisation--out-of-possession-.php): compactness, restricted passing lanes and collective pressing.
- [FIFA: Defensive transitions](https://www.fifatrainingcentre.com/en/practice/elite-sessions/transition-to-defending/defensive-transitions.php): immediate pressure versus recovery into defensive shape.
- [FIFA: Mid-block and compactness](https://www.fifatrainingcentre.com/en/fwc2022/technical-and-tactical-analysis/controlling-the-game-without-the-ball--the-mid-block-and-compactness.php): distinguish pressing from holding a compact block.

The interpretations below are our operational synthesis, paraphrased from these coaching concepts. Only visible players are counted. A cropped broadcast view cannot establish a full formation, offside, player identity, dominant foot, body orientation or intent.

<!-- runtime:start -->

## Runtime tactical guidance

Predict the next initiated on-ball action within three seconds. An already travelling pass is context, not a new pass prediction; consider the likely receiver's next action if supported. A turnover means loss to the opponent before a new controlled action. Cross includes wide deliveries and cutbacks into the box; pass excludes these. Carry means maintaining control while moving. Stoppage needs ball-out/dead-play evidence, not merely low motion.

Build-up is controlled circulation/progression from deeper areas. Settled attack works against an established block. Attacking transition begins after a regain; counterattack additionally needs rapid forward movement and a recovering opponent. Defensive transition can lead to counter-pressing or recovery. A nearby defender alone does not prove pressing: use closing movement, supporting pressure and restricted outlets. A compact block may wait without actively pressing.

Roles are contextual: a wide ball carrier can function as a winger or overlapping full-back; do not infer an official position from one frame. Central support can recycle possession; a runner behind defenders provides depth; near/far-post and cutback-zone runners provide different targets. Goalkeepers generally distribute under build-up pressure. Off-ball runs require motion history, not just an advanced position.

Wide final-third control, decreasing distance to the byline, and teammates arriving in the penalty area raise the plausibility of a cross. At the byline, runners behind the ball support a cutback. A blocked delivery lane, empty visible box or an open inside route can favor recycling, a pass or a carry instead. Do not force a cross from location alone. Compare box occupation and run direction over recent history.

Pass becomes more plausible with available support, a clear lane, pressure on the carrier, or a forward runner. Carry is supported by forward space, a manageable isolated defender and limited immediate passing benefit. Shot is supported by central proximity to goal and a shooting lane; a tight wide angle favors delivery more than shooting. Turnover risk rises with converging pressure, contested control and blocked outlets. These are qualitative influences, not fixed percentages.

Overloads are local numerical advantages that may free an attacker, but count carrier and support consistently. Defensive width/depth describe only the visible group. Compact central defending may direct play wide; shifting the ball can create space elsewhere. Progression can be a pass, carry or a run that offers a line-breaking option. Do not equate all forward ball motion with a counterattack.

Uncertainty should broaden the distribution over plausible actions, not automatically choose insufficient_evidence. Unknown exact carrier during a visible ball flight can coexist with useful attacking-team, location and receiving-context evidence. Recent-team or proximity context is weaker than confirmed possession. Abstain when the ball/attacking side/location are genuinely indeterminate, a cut destroys continuity, or missing geometry prevents the relevant judgment. Never invent off-camera targets. Reconstructed trajectories use surrounding observations and are less certain than detections; these are retrospective replay judgments, not leakage-free prospective forecasts.
<!-- runtime:end -->

## Measured features and interpretation

Coordinates are oriented toward the attacking goal. Pitch projection assumes 105 × 68 m; direction is configured by the user. Wide means within 17 m of a touchline; crossing territory begins 35 m from the goal line; byline territory is within 12 m. Box occupation uses the nominal penalty area. These thresholds are intentionally exposed in code and must be evaluated rather than presented as learned rules.

Passing lanes are line segments tested for nearby visible opponents, rather than only asking whether the receiver is unmarked. Box-entry and progression evidence comes from historical player motion. Pressure uses proximity plus closing velocity. In-flight ball context uses a bounded recent attacking team while keeping carrier identity unknown. The runtime sees provenance and context age so weak continuity is not mistaken for control.

## Evaluation and maintenance

Test mirrored attack directions, wide approach with arriving runners, empty-box wide possession, central shooting opportunity, pressured build-up, ball flight and genuinely missing observations. Record distributions, abstention frequency and model version. Synthetic scenarios test sensitivity, not match accuracy. On real footage report context availability separately from confirmed possession and detection coverage. Later add labeled next-action outcomes and proper scoring rules, including a causal-only benchmark that disables retrospective refinement.
