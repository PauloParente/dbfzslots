"""Gera a 4a fileira da mascara do cursor (CharaPositionMask) a partir da 2a fileira.

A grade atual tem fileiras de 15/16/14 slots; fileiras de mesma paridade tem os mesmos X.
A 4a fileira copia a forma exata dos 16 slots da 2a fileira, deslocada 2 fileiras (+128 px),
mantendo formato, arco e espacamento. Os extras ocupam as regioes 45.. da esquerda p/ direita.
"""
import numpy as np

W, H = 1280, 720
ROW_STEP = 64
FIRST_EXTRA_REGION = 45
EMPTY = 255

def load_raw(path):
    return np.frombuffer(open(path, "rb").read(), dtype=np.uint8).reshape(H, W).copy()

def row_regions(mask, ymin, ymax):
    """ids das regioes cujo centro esta em [ymin, ymax), ordenados por x."""
    out = []
    for v in range(0, 128):
        ys, xs = np.nonzero(mask == v)
        if len(xs) and ymin <= ys.mean() < ymax:
            out.append((xs.mean(), v))
    return [v for _, v in sorted(out)]

def fourth_row_slots(mask):
    """Lista (na ordem esq->dir) de arrays booleanos: a forma de cada slot da 4a fileira."""
    row2 = row_regions(mask, 495, 530)
    assert len(row2) == 16, f"2a fileira com {len(row2)} slots (esperado 16)"
    slots = []
    for v in row2:
        shape = np.zeros_like(mask, dtype=bool)
        ys, xs = np.nonzero(mask == v)
        ys2 = ys + 2 * ROW_STEP
        ok = ys2 < H
        shape[ys2[ok], xs[ok]] = True
        slots.append(shape)
    return slots

def build(mask, n_extras):
    assert 0 <= n_extras <= 15
    out = mask.copy()
    # limpa regioes >= 45 de uma mascara anterior (ex.: a da WistfulHopes)
    out[(out >= FIRST_EXTRA_REGION) & (out < 128)] = EMPTY
    slots = fourth_row_slots(mask)
    for i in range(n_extras):
        s = slots[i]
        clash = (out[s] != EMPTY).sum()
        assert clash == 0, f"slot {i} sobrepoe {clash} pixels de outras regioes"
        out[s] = FIRST_EXTRA_REGION + i
    return out

def shift_up(mask, px):
    """Sobe a grade inteira px pixels (para sair de cima da barra de ajuda)."""
    if px <= 0:
        return mask
    ys = np.nonzero((mask != EMPTY).any(1))[0]
    assert ys[0] >= px, f"a grade so tem {ys[0]} px livres acima"
    out = np.full_like(mask, EMPTY)
    out[:H - px] = mask[px:]
    return out

def centers(mask, n_extras):
    res = []
    for i in range(n_extras):
        ys, xs = np.nonzero(mask == FIRST_EXTRA_REGION + i)
        res.append((round(float(xs.mean())), round(float(ys.mean()))))
    return res

def preview(mask, path):
    from PIL import Image
    import colorsys
    pal = []
    for v in range(256):
        if v in (255,):
            pal += [0, 0, 0]
        elif v == 128:
            pal += [60, 60, 60]
        elif v >= FIRST_EXTRA_REGION and v < 128:
            pal += [255, 255, 255]
        else:
            r, g, b = colorsys.hsv_to_rgb((v * 0.618) % 1, 0.6, 0.9)
            pal += [int(r * 255), int(g * 255), int(b * 255)]
    img = Image.frombytes("L", (W, H), mask.tobytes()).convert("P")
    img.putpalette(pal)
    img.convert("RGB").save(path)

if __name__ == "__main__":
    import sys
    base = load_raw(sys.argv[1])
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 15
    m = build(base, n)
    preview(m, sys.argv[3] if len(sys.argv) > 3 else "mask4_preview.png")
    print("centros da 4a fileira:", centers(m, n))
