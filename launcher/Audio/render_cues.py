"""Render the terminal's two short, low-level mono PCM cues using the standard library."""
from array import array
from math import cos, exp, pi, sin, tau
from pathlib import Path
from random import Random
import sys
import wave

RATE = 48000


def key_press():
    noise = Random(79)
    fast = slow = 0.0
    for i in range(round(0.24 * RATE)):
        t = i / RATE
        # Damped switch housing, followed by the quieter spring contact.
        click = exp(-t / 0.010) * (sin(tau * 480 * t) + 0.35 * sin(tau * 1260 * t))
        contact = max(0, t - 0.009)
        click += 0.32 * exp(-contact / 0.006) * sin(tau * 810 * contact)
        # A short, band-limited breath emerging just behind the contact.
        white = noise.uniform(-1, 1)
        fast += 0.37 * (white - fast)
        slow += 0.095 * (white - slow)
        air = max(0, t - 0.012)
        hiss = (fast - slow) * (1 - exp(-air / 0.014)) * exp(-air / 0.053)
        yield click + 0.57 * hiss


def sync_lock():
    for i in range(round(0.16 * RATE)):
        t = i / RATE
        # One rounded, rising tone that settles onto its final pitch.
        phase = tau * (1050 * t - 310 * 0.025 * (1 - exp(-t / 0.025)))
        attack = (1 - cos(pi * min(t / 0.008, 1))) / 2
        yield attack * exp(-t / 0.043) * (sin(phase) + 0.07 * sin(2 * phase))


def write_cue(path, samples, peak_db):
    values = list(samples)
    gain = 32767 * 10 ** (peak_db / 20) / max(map(abs, values))
    fade_samples = round(0.015 * RATE)
    pcm = array("h", (round(value * gain * min(1, (len(values) - i - 1) / fade_samples))
                      for i, value in enumerate(values)))
    if sys.byteorder != "little":
        pcm.byteswap()
    with wave.open(str(path), "wb") as output:
        output.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
        output.writeframes(pcm.tobytes())


if __name__ == "__main__":
    folder = Path(sys.argv[1])
    folder.mkdir(parents=True, exist_ok=True)
    write_cue(folder / "key-press.wav", key_press(), -25)
    write_cue(folder / "pilot-lock.wav", sync_lock(), -31)
