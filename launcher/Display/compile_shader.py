"""Compile the terminal pixel shader using the Windows 11 Direct3D compiler."""
import ctypes as ct
from pathlib import Path
import sys


def blob_bytes(blob):
    table = ct.cast(blob, ct.POINTER(ct.POINTER(ct.c_void_p))).contents
    pointer = ct.WINFUNCTYPE(ct.c_void_p, ct.c_void_p)(table[3])(blob)
    size = ct.WINFUNCTYPE(ct.c_size_t, ct.c_void_p)(table[4])(blob)
    try:
        return ct.string_at(pointer, size)
    finally:
        ct.WINFUNCTYPE(ct.c_ulong, ct.c_void_p)(table[2])(blob)


if __name__ == "__main__":
    source = Path(__file__).with_name("Tube.hlsl").read_bytes()
    code, errors = ct.c_void_p(), ct.c_void_p()
    compile_shader = ct.WinDLL("d3dcompiler_47").D3DCompile
    compile_shader.argtypes = [ct.c_char_p, ct.c_size_t, ct.c_char_p, ct.c_void_p,
                               ct.c_void_p, ct.c_char_p, ct.c_char_p, ct.c_uint,
                               ct.c_uint, ct.POINTER(ct.c_void_p), ct.POINTER(ct.c_void_p)]
    result = compile_shader(source, len(source), b"Tube.hlsl", None, None, b"main",
                            b"ps_2_0", 0, 0, ct.byref(code), ct.byref(errors))
    if errors:
        print(blob_bytes(errors).decode(errors="replace"), file=sys.stderr)
    if result < 0:
        raise SystemExit(1)
    target = Path(sys.argv[1])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(blob_bytes(code))
