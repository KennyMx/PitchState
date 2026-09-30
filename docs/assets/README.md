# Demo media

The README preview is a 12-second presentation replay rendered from actual PitchState analysis. It is not a recording of the application UI and does not use simulated tracking or invented probabilities.

- **Footage:** `2e57b9_0.mp4`, DFL Bundesliga Data Shootout sample linked by [Roboflow's soccer example](https://github.com/roboflow/sports/tree/main/examples/soccer). Source footage rights remain with their owners; no redistribution license is asserted here.
- **Analysis:** `.local/real-analysis.json`, produced by the documented neural pipeline with Jev enabled. Track labels are internal IDs, not jersey numbers. Forecasts are uncalibrated model estimates.
- **Exports:** MP4 at 60 FPS with freshly interpolated overlays on every output frame; the 25 FPS source footage repeats frames without synthesizing new camera motion; animated GIF at 7 FPS and 840 px wide as an optional lightweight preview. Both show the same saved 5 Hz analysis.

The root README embeds the MP4 through a GitHub video attachment so visitors can play it directly on the repository page. If regenerating the video, upload the new MP4 in GitHub’s Markdown editor and replace the attachment URL in the root README.

## Reproduce

First generate `.local/real-analysis.json` using the real-footage instructions in the root README. Rendering itself makes no API calls. The renderer uses the backend environment's OpenCV, NumPy, and Pillow packages, plus Arial at the macOS system font path. Exporting requires FFmpeg.

```sh
.venv/bin/python scripts/render_readme_demo.py
ffmpeg -y -i .local/readme-demo.avi -c:v libx264 -crf 24 -pix_fmt yuv420p -movflags +faststart docs/assets/pitchstate-demo.mp4
ffmpeg -y -i docs/assets/pitchstate-demo.mp4 -filter_complex 'fps=7,scale=840:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse' -loop 0 docs/assets/pitchstate-demo.gif
```

The full source footage, model weights, and private analysis caches are not bundled with these presentation assets.
