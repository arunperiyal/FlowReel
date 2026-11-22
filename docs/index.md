# FlowReel

FlowReel makes films of flow simulations from configuration files. You describe each
shot (the data, the fields, the layers, the camera) in YAML, and FlowReel renders the
frames and builds the film with its captions, cards and sound.

- **New to FlowReel?** Start with [the tutorial](tutorial/index.md): a 20-second film
  of the flow past a cylinder, from a public data set, in eight short chapters.
- **The user guide** explains each part, starting with [projects](project.md) and
  [the rules](rules.md) every project follows.
- **The reference** lists every [command](commands.md).

FlowReel is open source (MIT) on [GitHub](https://github.com/arunperiyal/FlowReel).

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

A new page goes in the `nav` of `mkdocs.yml`. The design, `docs/PLAN.md`, stays out of
the site.
