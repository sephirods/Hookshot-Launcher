#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate multi-size hookshot.ico and Win32 hookshot.res from embedded PNG asset."""

import base64
import io
import os
import struct
from PIL import Image

SIZES = (16, 24, 32, 48, 64, 128, 256)

ICON_B64 = """
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
nAQYoPU/AYdEDvblp9UAAAAASUVORK5CYII=
"""


def square(im, size):
    im = im.convert("RGBA")
    return im.resize((size, size), Image.LANCZOS)


def png_of(im):
    b = io.BytesIO()
    im.save(b, "PNG", optimize=True)
    return b.getvalue()


def res_entry(kind, name, data, flags=0x1010):
    header = struct.pack("<II", len(data), 32) + struct.pack("<HHHH", 0xFFFF, kind, 0xFFFF, name)
    header += struct.pack("<IHHII", 0, flags, 0x0409, 0, 0)
    return header + data + b"\0" * (-len(data) & 3)


def generate_icons(out_dir="assets"):
    os.makedirs(out_dir, exist_ok=True)
    raw_png = base64.b64decode(ICON_B64)
    im = Image.open(io.BytesIO(raw_png))
    images = [(s, png_of(square(im, s))) for s in SIZES]

    head = struct.pack("<HHH", 0, 1, len(images))
    offset = len(head) + 16 * len(images)
    entries, body = b"", b""
    group = head
    for i, (s, data) in enumerate(images):
        b = s & 255
        entries += struct.pack("<BBBBHHII", b, b, 0, 0, 1, 32, len(data), offset + len(body))
        group += struct.pack("<BBBBHHIH", b, b, 0, 0, 1, 32, len(data), i + 1)
        body += data

    ico_path = os.path.join(out_dir, "hookshot.ico")
    with open(ico_path, "wb") as f:
        f.write(head + entries + body)

    res = res_entry(0, 0, b"", 0)
    for i, (_, data) in enumerate(images):
        res += res_entry(3, i + 1, data)
    res += res_entry(14, 1, group, 0x1030)
    res_path = os.path.join(out_dir, "hookshot.res")
    with open(res_path, "wb") as f:
        f.write(res)
    print("Generated:", ico_path, res_path, len(res))


if __name__ == "__main__":
    generate_icons()
