# Validation

## Automated

`npm test` exercises temporal interpolation and boundaries, missing/distant ball abstention, event persistence and duplicate suppression, prefix consistency, calibrated metric units, track continuity and expiry, one-to-one/team association, actual pixel segmentation, projective geometry, and bounded ball interpolation.

`npm run build` type-checks strict TypeScript and bundles both the app and worker. `npm run format:check` verifies formatting. GitHub Actions runs these on pushes and pull requests using Node 22.

## Browser smoke test performed

- Loaded the example and checked desktop and narrow-screen layouts.
- Played, paused, sought to a tactical event, selected a player, and enabled the heatmap.
- Uploaded the generated three-second MP4 fixture through the file picker.
- Observed two tracked candidates, original footage, unknown possession, and no fabricated events.
- Marked four corners; the UI switched to calibrated pitch reconstruction.
- Supplied three ball annotations near a detected player; the timeline gained a supported possession event.
- Checked browser console errors during the initial upload test: none recorded.

The fixture validates integration, not soccer recognition accuracy. No held-out match-footage benchmark has been run. Mobile interaction, decoder compatibility across browsers, calibrated speed accuracy, and long-clip performance need broader testing before production claims.
