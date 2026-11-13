"""Match cinematics, procedural effects, and their runtime media allowlist.

Keep this module lightweight: importing the asset list must not decode animation
frames or initialize Tk. Authoring videos such as MOV files are not published.
"""

ANIMATION_FILES = (
    "Freight Lift.webp",
    "Deploy_P1.webp",
    "Deploy_P2.webp",
    "UNIT-DEFEATED.webp",
    "REACTOR-SURGE.webp",
    "SONIC-WAKE.webp",
    "VICTORY-STANDARD.webp",
)
