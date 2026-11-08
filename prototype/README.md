# Prototype

`afms/` holds the scripts that made the AFMS 2026 competition film, as they were on
2026-11-08. They are the reference for FlowReel's golden-frame tests and are kept
unchanged; the package in `src/flowreel/` is written fresh from them.

They expect the research data and assets, which are not in this repository: the case
folders with PLT files, the displacement and force series, an institutional logo and a
licensed music track. Run order and settings are in `afms/make_film.py` and
`afms/film_text.toml`.

| Script | Does |
|---|---|
| `fxplt.py` | Reads binary Tecplot PLT files |
| `render_frames.py` | Flow shots: lambda2 from velocity, iso surfaces, slices, the reveal |
| `render_frozen.py` | The domain shot: frozen time, moving camera, set-up markers |
| `render_carve.py` | The carving shot: a parametric grooved cylinder, no data |
| `surface_data.py` | Wall shear and sectional forces from the velocity gradient |
| `render_extras.py` | 2D panels: groove section, span cuts, wall strips, lift map |
| `compose_compare.py` | Stacked layouts and live plots |
| `extract_series.py` | Displacement and forces from OTHD and OISD |
| `make_film.py`, `film_text.toml` | Cards, captions, freezes, rates, audio, assembly |
| `prepare_logo.py` | Turns a logo into a white mark for the title card |
| `render_airavata.slurm` | The Slurm job used on the cluster |
