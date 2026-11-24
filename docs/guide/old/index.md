# The film of shots (going)

These pages describe how a film was made before Phase 10: a `film.yml` of **shots** (of
kinds `frames`, `layout`, `card` and `hold_last_of`), with card files, caption files,
tiled layouts composed by `flowreel compose`, and clips finished with their captions.

A film is now made of [scenes](../film/film.md), each a [layout of boxes](../film/layouts.md):
a card is a scene of text and image boxes, a caption is a timed text box, a tiled layout
is a layout of shot and panel boxes, and `compose panel` is `panel draw`. The film of
shots still builds, so films made with it keep working while they move; it is removed,
with these pages, once FlowReel's own tutorials and examples no longer use it.

| Before | Now |
|---|---|
| a shot of kind `frames` | a scene with a [shot box](../film/boxes.md#shot) |
| a `layout` shot, a tiled layout file | a scene whose layout has shot and [panel boxes](../film/boxes.md#panel-and-last_frame) |
| a `card` shot, a card file | a scene of [text](../film/boxes.md#text), [image](../film/boxes.md#image) and [shape](../film/boxes.md#shape) boxes |
| `hold_last_of` | a [`last_frame`](../film/boxes.md#panel-and-last_frame) box |
| a caption, a caption file | a timed text box ([`at`](../film/layouts.md#boxes)) |
| a caption's point in the model | a box that [follows a point](../film/layouts.md#follow-a-box-on-a-point-of-the-flow) |
| `compose panel` | `panel draw` |
