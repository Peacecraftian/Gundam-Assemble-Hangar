# Gundam Assemble Hangar design

The application is a maintenance console for mobile suits. Preserve the current Mission Sortie, Match Console, Service Bay and Tactics behavior while moving toward a browser interface. Retired planning studies and alternate logos are no longer runtime or repository assets; their original versions remain in Git history.

Use the live palette and type roles in `companion/theme.py`: graphite background `#151A1C`, recessed panels `#242B2D`, cream ink `#F2EDE0`, amber actions `#FFB762`, teal Player 1 and salmon Player 2. Chakra Petch Bold supplies headings; Saira Stencil One supplies VP totals. Font and icon license notices accompany their assets.

Use exact opaque swatches from [Pineapple 32](Images/palette_pineapple-32-32x.png) by default when creating Battlefield environment palettes for future releases. The terrain fills, legend swatches, hex dividers, and selection outline draw from this set. Give Ground Level, Height 1, and Height 2 distinct, readable shades.

Keep one clear housing per major panel, readable labels, a visible current phase/round, and independent player lanes. Retain keyboard access, visible focus, meaningful disabled states, accessible non-color cues, and cancel paths. Mission Sortie supports catalog inspection and squad assembly; Match Console exposes timeline, scoring, statuses, reserve/deployment, defeat and undo; Service Bay commits edits as one transaction. Tactics preserves search by printed name or number and card inspection.

Card art remains authoritative to its published original. Preserve transparent corners and the off-white preview/fan rim; crop Hangar portraits to bleed. The authoring and publication pipeline is specified in AGENTS.md. Use content-hashed, appropriately sized raster derivatives in the application, with editable SVG masters retained separately.

Validate match and undo parity, duplicate-unit rules, RWS actions and saved-match compatibility before a browser migration. Exercise minimum-size layouts, high DPI, overflow stacks, keyboard navigation, long labels, missing images and revision conflicts. Use a separate save database for smoke testing. The web interface is a later task; the existing Tk application remains the functional reference.
