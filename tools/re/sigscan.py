"""Busca padroes de bytes com curingas (??) nas secoes de codigo de um PE."""
import re, sys
from pe import PE

def _tok(p):
    if p in ("?", "??"):
        return b"."
    if "?" in p:  # meio byte: "b?" = 0xb0..0xbf, "?5" = 0x05,0x15..0xf5
        vals = [v for v in range(256)
                if all(c == "?" or int(c, 16) == (v >> s) & 0xF for c, s in zip(p, (4, 0)))]
        return b"[" + b"".join(re.escape(bytes([v])) for v in vals) + b"]"
    return re.escape(bytes([int(p, 16)]))


def compile_sig(sig):
    return re.compile(b"".join(_tok(p) for p in sig.split()), re.S)

def scan(p, sig, limit=50):
    rx = compile_sig(sig)
    hits = []
    for name, va, vs, raw, rs, ch in p.sections:
        if not ch & 0x20000000:
            continue
        sec = p.data[raw:raw + rs]
        for m in rx.finditer(sec):
            hits.append(va + m.start())
            if len(hits) >= limit:
                return hits
    return hits

if __name__ == "__main__":
    p = PE(sys.argv[1])
    for h in scan(p, sys.argv[2]):
        print(hex(h))
