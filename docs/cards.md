# Cards

Phase 4, branch 3. A card is a still shot, such as an opening title or the credits at the
end. It is a file of blocks placed down a background, not code, so a different
competition's layout is a different file (plan Section 10.5). A film names it as a shot:

```yaml
# film.yml
shots:
  - {name: opening, card: cards/opening.yml, seconds: 7, fade: [1.5, 1.5]}
```

## The card file

```yaml
# cards/opening.yml
background: black
blocks:
  - {image: ../assets/logo.png, height: 190, y: 110}
  - title: ['Effect of Helical Grooves on Suppression of',
            'Vortex-Induced Vibration in Flexible Cylinders']
    size: 60
    spacing: 82
    gap: 70
  - {divider: 320, gap: 38}
  - {heading: CREATED BY, names: ['A. Author'], gap: 46}
  - {heading: CO-AUTHORED BY, names: ['B. Author, C. Author,', 'D. Author and E. Author'], gap: 26}
  - {text: ['Made with FlowReel'], gap: 60}
```

This is the AFMS film's opening card. Its numbers are the prototype's, and
`tests/test_golden_card.py` checks that the file draws the same card as the prototype's
`make_film.opening_card`, pixel for pixel.

| Key | Type | Default | Meaning |
|---|---|---|---|
| `blocks` | list | required | the blocks, top to bottom (below) |
| `size` | `[width, height]` | `[1920, 1080]` | the size the card's pixels are written for; a film of another size scales the whole card |
| `background` | colour | `black` | |
| `background_image` | file | none | a picture scaled to cover the card and centred, beneath the blocks |

All positions, sizes and spacing are **pixels** of a card `size` large. `y` is down from
the top.

## Where a block goes

Each block is centred across the card by its measured width. Its top is either:

- `y`: pixels from the card's top, or
- `gap`: pixels below the **end** of the block before it (default `0`; it may be negative).

A block ends where what it draws ends: an image's height; a divider's `thickness`; lines
times their `spacing`; for names, the `heading_gap` (if there is a heading) plus the names
times their `spacing`. So editing a title from two lines to three moves everything after
it down, unless those blocks give `y`.

Text is placed by the top of its font (Pillow's ascender line), as the prototype placed it.

## Blocks

Each block is one of `image`, `title`, `divider`, `names` or `text`.

| Block | Keys | Defaults | Draws |
|---|---|---|---|
| `image` | `image` (file), `height` or `width` | the file's own size | a picture, scaled keeping its shape, with its transparency |
| `title` | `title` (lines), `size`, `spacing`, `weight`, `colour` | `size: 60`, `spacing: 1.3 × size`, `regular`, the film's text colour | the title |
| `divider` | `divider` (length, or `true`), `thickness`, `colour` | `320`, `2`, the film's muted colour | a horizontal line |
| `names` | `names` (lines), `heading`, `size`, `spacing`, `weight`, `colour`, `heading_size`, `heading_gap`, `heading_weight`, `heading_colour` | `size: 42`, `spacing: 58`, `light`, text colour; heading `28`, `44`, `regular`, muted colour | a heading (optional) and a list of names under it |
| `text` | `text` (lines), `size`, `spacing`, `weight`, `colour` | `size: 24`, `spacing: 1.3 × size`, `regular`, the film's muted colour | small print: a licence, a credit, a date |

- `size` is the font's size in pixels.
- `weight` is `regular`, `light`, `bold` or `italic`, all of the bundled Lato.
- The font is the film's `style.font`, as for captions: Lato by default, or any family
  installed on the machine that builds the film, such as `Times New Roman`, at its
  nearest weight (Times New Roman has no light weight, so its names are regular). A
  family that is not installed is an error naming it.
- The film's colours are `style.colours.text` and `style.colours.muted` in `film.yml`
  (`'#f2f2f2'` and `'#96a5b2'`), so a film's cards follow its style unless a block sets
  `colour`.
- Lines are a list of strings, or one string. Quote a line holding `: `.
- A card has no mathematics: it is drawn by Pillow, like the prototype's. Captions,
  drawn by matplotlib, have maths.

**Logos and pictures stay outside the repository.** `image` and `background_image` are
taken from the card file's folder and must exist; a card for a real film lives with that
film's files (plan Section 24, question 4).

Unknown keys are errors naming the card file and the key path, as everywhere in FlowReel.

## From Python

```python
from flowreel.film.cards import card_image, layout, load_card

card = load_card("cards/opening.yml")
print(layout(card))                       # each block's (top, bottom) in pixels
card_image(card).save("opening.png")      # the film's default style
card_image(card, style, size=(1280, 720)) # a film's style, at another size
```

The film build (branch 4) draws a card once, keyed by its file and the film's style, and
holds it for the shot's `seconds`.

## Example

`examples/film_cards/run.py` draws a card file with a generated logo, every kind of
block, and prints where each block falls. It needs no data.
