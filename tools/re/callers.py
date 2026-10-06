"""Conta/lista chamadas diretas (E8 rel32) para um RVA alvo."""
import struct, sys
import numpy as np
from pe import PE

def callers(p, targets):
    res = {t: [] for t in targets}
    for name, va, vs, raw, rs, ch in p.sections:
        if not ch & 0x20000000:
            continue
        sec = np.frombuffer(p.data, dtype=np.uint8, count=rs, offset=raw)
        idx = np.nonzero(sec[:-5] == 0xE8)[0]
        rel = sec[idx + 1].astype(np.int64) | (sec[idx + 2].astype(np.int64) << 8) | \
              (sec[idx + 3].astype(np.int64) << 16) | (sec[idx + 4].astype(np.int64) << 24)
        rel = np.where(rel >= 1 << 31, rel - (1 << 32), rel)
        dest = va + idx + 5 + rel
        for t in targets:
            res[t].extend(int(va + i) for i in idx[dest == t])
    return res

if __name__ == "__main__":
    p = PE(r"C:\dbfz modded\game\RED\Binaries\Win64\RED-Win64-Shipping.exe")
    ts = [int(x, 16) for x in sys.argv[1:]]
    for t, cs in callers(p, ts).items():
        print(f"{t:#x}: {len(cs)} chamadas  ex: {[hex(c) for c in cs[:8]]}")
