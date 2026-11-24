# FlowReel

FlowReel makes films of flow simulations from configuration files. Each shot (the data,
the fields, the layers, the camera) is a YAML file. FlowReel renders the frames, on a
laptop or on a cluster, and builds the film from one more file: its scenes, each a
layout of boxes (text, pictures, shapes, shots, plots), with its freezes and sound. Every picture can be made again from the files that
describe it.

![A frame of the tutorial's film](tutorials/steady/images/04-camera.png)

## Where to start

Two [tutorials](tutorials/index.md), in order:

**[The tutorial](tutorials/steady/index.md)** makes a 20-second film of the flow past a
cylinder from a public data set, in eight short chapters, from installing FlowReel to
the finished film. Start there.

**[The second tutorial](tutorials/unsteady/index.md)** films a flow that moves: vortex
shedding behind a cylinder at a Reynolds number of 100, read from PLT files, with the
drag and lift drawn beside it from a CSV file, and rendered on a cluster. It follows
the first.

![The second tutorial's film](tutorials/unsteady/images/film.gif)

## The user guide

A film is described in levels, and the guide follows them, in the order a film is made:

| Level | Pages |
|---|---|
| The project and its data | [projects](guide/projects/project.md), [the rules](guide/projects/rules.md) every project follows, [data and tags](guide/projects/data.md) (each case under `data/<tag>/`), [sources](guide/projects/sources.md), [bodies](guide/projects/bodies.md), [derived fields](guide/projects/fields.md) |
| Shots and panels | [shot files](guide/shots/shots.md), [flow layers](guide/shots/layers-flow.md), [layers without flow data](guide/shots/layers-markers.md), [tracks](guide/shots/tracks.md) (values that change along a shot), [cameras](guide/shots/cameras.md), [the camera editor](guide/shots/camera-editor.md), [long bodies](guide/shots/long-bodies.md), [panels](guide/shots/panels.md) (plots drawn with matplotlib) |
| The film | [the film and its scenes](guide/film/film.md), [layouts and boxes](guide/film/layouts.md) (and the window that designs them), [boxes](guide/film/boxes.md): text, image, shape, shot, panel, a held frame |
| Making it | [rendering and caching](guide/making/rendering.md), [Slurm](guide/making/slurm.md), [building the film](guide/making/build.md), [checking it](guide/making/check.md) |

## The reference

- **[Commands](reference/commands.md):** every command and option, from the commands'
  own help.
- **[YAML keys](reference/yaml.md):** every key of every file FlowReel reads, with its
  type and default, linked to the guide page that explains it.

Both are generated from the code, so they cannot drift from it.

## This site

The site is built from the Markdown pages in `docs/` with
[MkDocs Material](https://squidfunk.github.io/mkdocs-material/), and published to
<https://arunperiyal.github.io/FlowReel/> on every change to `main`. The same pages read
on GitHub, without the site's search and navigation. To build it on your machine:

```text
pip install -e ".[docs]"
mkdocs serve            # the site at http://127.0.0.1:8000, rebuilt as you edit
mkdocs build --strict   # as every pull request does: a broken link or anchor, or a
                        # page left out of the navigation, fails it
```

A new page goes in the `nav` of `mkdocs.yml`. The design is in `plan/` at the
repository's root, outside the site. FlowReel is open source (MIT) on [GitHub](https://github.com/arunperiyal/FlowReel).
