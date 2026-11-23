# FlowReel

FlowReel makes films of flow simulations from configuration files. Each shot (the data,
the fields, the layers, the camera) is a YAML file. FlowReel renders the frames, on a
laptop or on a cluster, and builds the film from one more file, with its cards,
captions, freezes and sound. Every picture can be made again from the files that
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

Each part of FlowReel, in the order a film is made:

| Part | Pages |
|---|---|
| Projects and data | [projects](guide/projects/project.md), [the rules](guide/projects/rules.md) every project follows, [sources](guide/projects/sources.md) of data, [bodies](guide/projects/bodies.md), [derived fields](guide/projects/fields.md) |
| Shots | [shot files](guide/shots/shots.md), [flow layers](guide/shots/layers-flow.md), [layers without flow data](guide/shots/layers-markers.md), [tracks](guide/shots/tracks.md) (values that change along a shot), [cameras](guide/shots/cameras.md), [the camera editor](guide/shots/camera-editor.md) |
| Rendering | [rendering and caching](guide/rendering/rendering.md), [long bodies](guide/rendering/long-bodies.md), [Slurm](guide/rendering/slurm.md) |
| Composing | [compose](guide/composing/compose.md), [layouts](guide/composing/layouts.md), [panels](guide/composing/panels.md) |
| The film | [the film file](guide/film/film.md), [captions and shapes](guide/film/captions.md), [cards](guide/film/cards.md), [clips](guide/film/clips.md), [building the film](guide/film/build.md) |

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
