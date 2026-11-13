"""Offline Cannon-es rigid-body simulation for the native dice tray."""

import json
from functools import lru_cache
from math import sqrt
from secrets import randbelow

from .attacks import MAX_DICE
from .catalog import ASSETS


DICE_FILES = {
    "Dice/cannon-es.cjs.js": "tools/node_modules/cannon-es/dist/cannon-es.cjs.js",
    "Dice/LICENSE-Cannon-es.txt": "tools/node_modules/cannon-es/LICENSE",
}


@lru_cache(maxsize=1)
def engine_source():
    relative = "Dice/cannon-es.cjs.js"
    library = ASSETS / relative
    if not library.is_file():
        library = ASSETS / DICE_FILES[relative]
    return library.read_text(encoding="utf-8"), (ASSETS / "Dice/physics.js").read_text(encoding="utf-8")


class DiceWorld:
    def __init__(self):
        from py_mini_racer import JSEvalException, LibNotFoundError, MiniRacer

        library, script = engine_source()
        try:
            self.context = MiniRacer()
        except LibNotFoundError as error:
            raise RuntimeError("The bundled V8 runtime is unavailable.") from error
        self.js_error = JSEvalException
        try:
            self.evaluate("""
            const console = { warn() {}, error() {} };
            const CANNON = (() => {
                const exports = {};
                const require = name => {
                    if (name !== 'perf_hooks') throw new Error(`Unexpected physics dependency: ${name}`);
                    return { performance: { now: Date.now } };
                };
            """ + library + "\nreturn exports; })();")
            self.evaluate(script)
            self.vertices, self.faces, self.numbers = json.loads(self.evaluate("geometry"))
        except Exception:
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

    def close(self):
        self.context.close()

    def evaluate(self, source):
        try:
            return self.context.eval(source, timeout_sec=2)
        except self.js_error as error:
            raise RuntimeError(str(error)) from error

    def start(self, count, aspect):
        if not 1 <= count <= MAX_DICE:
            raise ValueError(f"Roll between 1 and {MAX_DICE} dice.")
        self.width = max(16, 12 * aspect, sqrt(count * aspect) * 3.65)
        self.height = self.width / aspect
        self.offsets = [randbelow(10) for _ in range(count)]
        self.evaluate(f"startDice({self.width}, {self.height}, {count})")

    def number(self, die, face):
        return self.numbers[(face + self.offsets[die]) % 10]

    def step(self, steps):
        poses, top_faces = json.loads(self.evaluate(f"stepDice({steps})"))
        values = tuple(self.number(die, face) for die, face in enumerate(top_faces)) if top_faces is not None else None
        return poses, values
