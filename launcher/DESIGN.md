# Hangar Terminal display

The startup screen follows the supplied mint-phosphor terminal concept at 1920×1080. Bay 01, the instrument faces, the logo and the grille are illustration crops. A simulated Minovsky Density trace scrolls across a fixed grid in the original instrument frame. The four diagnostics on the left report configuration, executable availability, local references and support tools when the configuration loads or reloads.

A dark green-black tube (#08130F), mint lettering (#9EFFC6) and fine green rules (#84E7AB) surround the amber ENTER HANGAR button (#FFB64D). Native controls use the game's Chakra Petch headings, navigation glyphs and orange cursors. Consolas sets terminal readouts. Chamfered buttons retain pressed, focused and disabled states. Narrow windows drop the illustrated bay to preserve the controls. Secondary pages scroll and keep desktop exit accessible from Maintenance.

The WPF root carries one pixel shader for all launcher pages. Bloom, barrel distortion, fine scanlines and a vignette give the screen its tube finish. A soft refresh band rolls from top to bottom every 14 seconds. Phosphor intensity varies by at most 1.1 percent around its normal level. A shared clock updates the tube and visible trace at up to 24 frames per second and pauses when the launcher is hidden or minimized. Turning off Windows animation effects also stops the motion. Timing and signal shape live in Display/MainWindow.Motion.cs. Display/Tube.hlsl controls the band profile and light response.

Pilot Sync uses the same clock for a single 2.4-second acquisition sweep at startup. The illuminated sectors and readout hold at 100% for the session. With Windows animation effects off, the gauge starts locked.

Each key dims and travels 1.5 device-independent pixels on contact. Two small wisps vent from beneath its lower edge and dissipate in 360 milliseconds. On release the backlight recovers in 150 milliseconds. Windows reduced motion keeps the immediate pressed contrast and omits the travel and exhaust.

Key contact sounds a muted mechanical click with a brief pneumatic tail. Pilot Sync plays one rising chirp on lock, including an immediate lock with reduced motion. The two mono WAV cues use separate players so a press can overlap the chirp. Their peak levels are set in Audio/render_cues.py at −25 dBFS for the press and −31 dBFS for lock. Both follow the Windows volume mixer.
