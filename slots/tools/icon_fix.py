"""
icon_fix.py - Ajusta a textura do icone de um extra ao formato do slot onde ele fica.

Na grade do DBFZ cada icone (CS_CIconNN, DXT5 256x256) vem recortado no formato do seu slot:
as fileiras sao inclinadas, e os slots de um lado tem a borda inclinada ao contrario dos do
outro. O icone de um mod feito para um slot da esquerda, posto num slot da direita, fica
"desalinhado". Aqui a imagem e cisalhada na horizontal (sem espelhar o personagem) para que a
borda esquerda siga a do icone-molde do slot, e o contorno (alfa) do molde e aplicado.

Uso (teste): python icon_fix.py <ui.pak> <molde NN> <saida.png>
"""
import struct
import sys
from pathlib import Path

import numpy as np

# ---- DXT5 --------------------------------------------------------------------------------------


def _565(c):
    r = ((c >> 11) & 31) * 255 // 31
    g = ((c >> 5) & 63) * 255 // 63
    b = (c & 31) * 255 // 31
    return np.stack([r, g, b], -1)


def decode_dxt5(raw, w, h):
    d = np.frombuffer(raw[:w * h], dtype=np.uint8).reshape(-1, 16)
    n = len(d)
    a0 = d[:, 0].astype(np.int32)
    a1 = d[:, 1].astype(np.int32)
    abits = np.zeros(n, dtype=np.uint64)
    for b in range(6):
        abits |= d[:, 2 + b].astype(np.uint64) << np.uint64(8 * b)
    c0 = d[:, 8].astype(np.int32) | (d[:, 9].astype(np.int32) << 8)
    c1 = d[:, 10].astype(np.int32) | (d[:, 11].astype(np.int32) << 8)
    cbits = d[:, 12].astype(np.uint32) | (d[:, 13].astype(np.uint32) << 8) | \
        (d[:, 14].astype(np.uint32) << 16) | (d[:, 15].astype(np.uint32) << 24)
    p0, p1 = _565(c0), _565(c1)
    pal = np.stack([p0, p1, (2 * p0 + p1) // 3, (p0 + 2 * p1) // 3], 1)      # DXT5: sempre 4 cores
    out = np.zeros((n, 16, 4), dtype=np.uint8)
    hi = a0 > a1
    for p in range(16):
        ai = ((abits >> np.uint64(3 * p)) & np.uint64(7)).astype(np.int32)
        interp = np.where(hi, ((8 - ai) * a0 + (ai - 1) * a1) // 7,
                          np.where(ai < 6, ((6 - ai) * a0 + (ai - 1) * a1) // 5, np.where(ai == 6, 0, 255)))
        out[:, p, 3] = np.where(ai == 0, a0, np.where(ai == 1, a1, interp))
        ci = ((cbits >> np.uint32(2 * p)) & np.uint32(3)).astype(np.int32)
        out[:, p, :3] = pal[np.arange(n), ci]
    return out.reshape(h // 4, w // 4, 4, 4, 4).transpose(0, 2, 1, 3, 4).reshape(h, w, 4)


def encode_dxt5(img):
    h, w, _ = img.shape
    blk = img.reshape(h // 4, 4, w // 4, 4, 4).transpose(0, 2, 1, 3, 4).reshape(-1, 16, 4).astype(np.int32)
    n = len(blk)
    out = np.zeros((n, 16), dtype=np.uint8)
    # alfa: extremos do bloco, 8 niveis
    a = blk[:, :, 3]
    amax, amin = a.max(1), a.min(1)
    flat = amax == amin
    amin2 = np.where(flat, np.maximum(amax - 1, 0), amin)
    amax2 = np.where(flat & (amax == 0), 1, amax)
    levels = np.stack([amax2, amin2] + [((7 - i) * amax2 + i * amin2) // 7 for i in range(1, 7)], 1)
    ai = np.abs(a[:, :, None] - levels[:, None, :]).argmin(2).astype(np.uint64)
    out[:, 0], out[:, 1] = amax2, amin2
    bits = np.zeros(n, dtype=np.uint64)
    for p in range(16):
        bits |= ai[:, p] << np.uint64(3 * p)
    for b in range(6):
        out[:, 2 + b] = ((bits >> np.uint64(8 * b)) & np.uint64(255)).astype(np.uint8)
    # cor: extremos no eixo de maior variacao (aproximacao pela luminancia)
    rgb = blk[:, :, :3]
    lum = rgb @ np.array([3, 6, 1])
    hi_c = rgb[np.arange(n), lum.argmax(1)]
    lo_c = rgb[np.arange(n), lum.argmin(1)]

    def to565(c):
        return ((c[:, 0] * 31 + 127) // 255 << 11) | ((c[:, 1] * 63 + 127) // 255 << 5) | ((c[:, 2] * 31 + 127) // 255)
    c0, c1 = to565(hi_c), to565(lo_c)
    swap = c0 < c1
    c0, c1 = np.where(swap, c1, c0), np.where(swap, c0, c1)
    same = c0 == c1
    c0 = np.where(same & (c0 < 0xFFFF), c0 + 1, c0)            # garante o modo de 4 cores (c0 > c1)
    c1 = np.where(same & (c0 == 0xFFFF), c1 - 1, c1)
    p0, p1 = _565(c0), _565(c1)
    pal = np.stack([p0, p1, (2 * p0 + p1) // 3, (p0 + 2 * p1) // 3], 1)
    ci = ((rgb[:, :, None, :] - pal[:, None, :, :]) ** 2).sum(3).argmin(2).astype(np.uint32)
    cb = np.zeros(n, dtype=np.uint32)
    for p in range(16):
        cb |= ci[:, p] << np.uint32(2 * p)
    out[:, 8], out[:, 9] = c0 & 255, c0 >> 8
    out[:, 10], out[:, 11] = c1 & 255, c1 >> 8
    for b in range(4):
        out[:, 12 + b] = (cb >> np.uint32(8 * b)) & np.uint32(255)
    return out.tobytes()

# ---- textura (UE 4.17): mips no .uexp ou no .ubulk ----------------------------------------------


FORMATS = (b"PF_DXT5", b"PF_B8G8R8A8")


def pixel_format(uexp):
    for f in FORMATS:
        i = uexp.find(f + bytes(1))
        if i >= 0:
            return f, i
    raise ValueError("unsupported texture format (only DXT5 and B8G8R8A8)")


def mips(uexp):
    """[(w, h, local, offset, size, pos_do_dado_no_uexp)] de cada mip; local = 'uexp'/'ubulk'.
    Formato apos o nome do formato: FirstMip i32, NumMips i32 e, por mip: bCooked i32, bulk
    (flags u32, count i32, size i32, offset i64, [dados se no .uexp]), SizeX i32, SizeY i32.
    No .ubulk os offsets sao relativos a um base desconhecido: os mips ficam em sequencia."""
    fmt, i = pixel_format(uexp)
    sx, sy = struct.unpack_from("<ii", uexp, i - 16)
    k = i + len(fmt) + 1
    first, num = struct.unpack_from("<ii", uexp, k)
    k += 8
    out, ub_base = [], None
    for _ in range(num):
        k += 4                                           # bCooked
        flags, count, size, off = struct.unpack_from("<Iiiq", uexp, k)
        k += 20
        if flags & 0x100:                                # BULKDATA_PayloadInSeperateFile
            ub_base = off if ub_base is None else ub_base
            where, pos, off = "ubulk", None, off - ub_base
        else:
            where, pos = "uexp", k
            k += size
        w, h = struct.unpack_from("<ii", uexp, k)
        k += 8
        out.append((w, h, where, off, size, pos))
    return sx, sy, out


def read_rgba(uexp, ubulk):
    sx, sy, ms = mips(uexp)
    w, h, where, off, size, pos = ms[0]
    raw = ubulk[off:off + size] if where == "ubulk" else uexp[pos:pos + size]
    if pixel_format(uexp)[0] == b"PF_B8G8R8A8":
        bgra = np.frombuffer(raw[:w * h * 4], dtype=np.uint8).reshape(h, w, 4)
        return bgra[:, :, [2, 1, 0, 3]].copy()
    return decode_dxt5(raw, w, h)


def write_rgba(uexp, ubulk, img):
    """Regrava todos os mips (reduzindo a imagem) nos mesmos lugares e tamanhos."""
    sx, sy, ms = mips(uexp)
    bgra = pixel_format(uexp)[0] == b"PF_B8G8R8A8"
    ue, ub = bytearray(uexp), bytearray(ubulk or b"")
    cur = img.astype(np.float32)
    for w, h, where, off, size, pos in ms:
        while cur.shape[1] > w:
            cur = (cur[0::2, 0::2] + cur[1::2, 0::2] + cur[0::2, 1::2] + cur[1::2, 1::2]) / 4
        px = np.clip(cur + 0.5, 0, 255).astype(np.uint8)
        data = px[:, :, [2, 1, 0, 3]].tobytes() if bgra else encode_dxt5(px)
        assert len(data) == size, (w, h, len(data), size)
        if where == "ubulk":
            ub[off:off + size] = data
        else:
            ue[pos:pos + size] = data
    return bytes(ue), bytes(ub) if ubulk else None

# ---- ajuste ao slot ----------------------------------------------------------------------------


def left_edge(alpha):
    """Reta (a*y + b) da borda esquerda da area opaca."""
    m = alpha > 128
    ys = np.where(m.any(1))[0]
    ys = ys[4:-4] if len(ys) > 16 else ys
    xs = np.array([np.argmax(m[y]) for y in ys])
    return np.polyfit(ys, xs, 1)


def fit_to_slot(src, tmpl):
    """Cisalha src (RGBA) para a borda esquerda seguir a do molde e aplica o alfa do molde."""
    h, w, _ = src.shape
    sa, sb = left_edge(src[:, :, 3])
    ta, tb = left_edge(tmpl[:, :, 3])
    out = np.zeros_like(src)
    xs = np.arange(w)
    for y in range(h):
        shift = (ta * y + tb) - (sa * y + sb)           # quanto a linha y anda para a direita
        x0 = np.clip(xs - shift, 0, w - 1)
        lo = np.floor(x0).astype(int)
        hi = np.minimum(lo + 1, w - 1)
        f = (x0 - lo)[:, None]
        out[y] = (src[y, lo] * (1 - f) + src[y, hi] * f + 0.5).astype(np.uint8)
    out[:, :, 3] = tmpl[:, :, 3]
    return out


def needs_fit(src, tmpl, tol=3.0):
    (sa, sb), (ta, tb) = left_edge(src[:, :, 3]), left_edge(tmpl[:, :, 3])
    h = src.shape[0]
    return max(abs((sa - ta) * y + (sb - tb)) for y in (40, h - 40)) > tol


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import re
    from PIL import Image
    from build_char import Source, PAKS, load_key
    k = load_key()
    s = Source([Path(sys.argv[1])], k)
    g = Source(PAKS, k)
    st = [x for x in s.files if re.search(r"/cs_cicon\d\d\.uexp$", x)][0][:-5]
    src = read_rgba(s.get(st + ".uexp"), s.get(st + ".ubulk") if st + ".ubulk" in s.files else b"")
    ts = f"red/content/ui/charaselect_s3/tex/cs_cicon{sys.argv[2]}"
    tm = read_rgba(g.get(ts + ".uexp"), b"")
    fit = fit_to_slot(src, tm)
    Image.fromarray(np.concatenate([src, tm, fit], 1)).save(sys.argv[3])
    print("precisa ajuste:", needs_fit(src, tm))


# ---- remontagem com a moldura nativa ------------------------------------------------------------
# A moldura dourada e a sombra fazem parte da textura. Os icones do jogo de um mesmo "lado" da
# grade tem moldura identica: o que varia entre eles e so o retrato. Daqui sai, por lado, a
# moldura (pixels constantes) e o miolo (pixels que variam).

LEFT_ICONS = ["35", "31", "25", "11", "03", "12", "13", "42"]      # slots 1-8 da 2a fileira
RIGHT_ICONS = ["44", "15", "07", "16", "21", "26", "14", "36"]     # slots 9-16


def frame_model(icons):
    st = np.stack([i.astype(np.float32) for i in icons])
    var = st[..., :3].std(0).mean(-1)
    alpha = st[..., 3].mean(0)
    interior = (var > 12) & (alpha > 200)
    # miolo = maior regiao "variavel"; fecha buracos por linha (entre o 1o e o ultimo pixel)
    # contorno limpo: retas (minimos quadrados, sem os extremos) nas bordas esquerda e direita
    ys, ls, rs = [], [], []
    for y in range(interior.shape[0]):
        xs = np.where(interior[y])[0]
        if len(xs) > 100:
            ys.append(y); ls.append(xs[0]); rs.append(xs[-1])
    ys, ls, rs = np.array(ys), np.array(ls), np.array(rs)
    y0, y1 = ys[0] + 2, ys[-1] - 2

    def robust(v):
        keep = np.abs(v - np.median(v)) < 6
        return np.polyfit(ys[keep], v[keep], 1)
    lf, rf = robust(ls), robust(rs)
    filled = np.zeros_like(interior)
    for y in range(y0, y1 + 1):
        a_, b_ = int(np.ceil(np.polyval(lf, y))) + 1, int(np.floor(np.polyval(rf, y))) - 1
        filled[y, a_:b_ + 1] = True
    return {"frame": icons[0].copy(), "interior": filled}


def spans(mask):
    out = {}
    for y in range(mask.shape[0]):
        xs = np.where(mask[y])[0]
        if len(xs):
            out[y] = (xs[0], xs[-1])
    return out


def classify(src_alpha, models):
    """Qual moldura (lado) o icone do mod usa: a de alfa mais parecido."""
    scores = {k: np.abs((src_alpha > 128).astype(int) - (m["frame"][:, :, 3] > 128).astype(int)).mean()
              for k, m in models.items()}
    return min(scores, key=scores.get), scores


def rebuild_icon(src, src_model, dst_model):
    """Retrato do miolo do src (moldura src_model) no miolo de dst_model, com a moldura dele."""
    s_sp, d_sp = spans(src_model["interior"]), spans(dst_model["interior"])
    ys_s = sorted(s_sp)
    ys_d = sorted(d_sp)
    out = dst_model["frame"].copy()
    for y in ys_d:
        # linha correspondente no src (alturas proporcionais)
        t = (y - ys_d[0]) / max(1, ys_d[-1] - ys_d[0])
        sy = ys_s[0] + t * (ys_s[-1] - ys_s[0])
        y0 = int(np.floor(sy)); y1 = min(y0 + 1, src.shape[0] - 1); fy = sy - y0
        a0, b0 = s_sp.get(y0, s_sp[min(s_sp, key=lambda q: abs(q - y0))])
        da, db = d_sp[y]
        xs = np.arange(da, db + 1)
        u = (xs - da) / max(1, db - da)
        sx = a0 + u * (b0 - a0)
        x0 = np.floor(sx).astype(int); x1 = np.minimum(x0 + 1, src.shape[1] - 1); fx = (sx - x0)[:, None]
        row = (src[y0, x0] * (1 - fx) + src[y0, x1] * fx) * (1 - fy) + (src[y1, x0] * (1 - fx) + src[y1, x1] * fx) * fy
        out[y, da:db + 1, :3] = (row[:, :3] + 0.5).astype(np.uint8)
    return out
