"""
build_char.py - Transforma um mod de SUBSTITUICAO em um personagem com codigo proprio.

  arquivos do jogo em Chara/<BASE>  +  arquivos do mod em Chara/<BASE>  ->  Chara/<NOVO>
  (+ pastas extras do mod, ex. Chara/SOL, copiadas como estao)

Uso:
  python build_char.py NOVO BASE mod.pak [--keep SOL,YGI] [--keep-refs] [--preload-fix]
                       [--move VGS/Costume02=VTS/Costume92] [--ui-paks extra.pak] [--ui-only] [--out pasta]

  --move  arquivos que o mod poe na pasta de OUTRO personagem e que o personagem novo usa
          (ex. modelo do Vegito em VGS/Costume02) vao para uma pasta propria, mesmo tamanho
          de caminho, e as referencias sao trocadas: o personagem original fica intacto.
  --ui-paks  paks de onde tirar a arte que o mod nao tiver (ex. versao antiga do mesmo mod).

Gera <out>/DBFZX_<NOVO>.pak (personagem), <out>/DBFZX_<NOVO>_UI.pak (arte da selecao e
retratos, tirada do mod quando ele tem, senao do jogo) e <out>/DBFZX_<NOVO>.json (relatorio).

Porte do tools/build_char.py e fix_preload_dependencies.py do DBFZ-ExtrasCustomSlots-XboxPC
(MrPopulutus, MIT), adaptado as ferramentas deste projeto. Regras:
  - caminhos /Game/Chara/<BASE>/ e nomes BBS_/COL_<BASE>(EF) viram <NOVO> (mesmo tamanho);
  - arquivos do mod para OUTROS personagens sao ignorados (os originais ficam intactos);
  - arquivos novos em Shared/ sao mantidos; substituicoes de Shared/ existentes sao ignoradas.
"""
import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from pak import PakFile, load_key          # noqa: E402
from pakwrite import write_pak             # noqa: E402
from uasset import Summary, rename_fn      # noqa: E402
from uasset_pkg import Package             # noqa: E402

from caminhos import PAKS, CHARS  # noqa: E402
KINDS = [("Chara_Image/Face_A/", "cp_chara_"), ("Chara_Image/Face_A/", "cp_chara_sparking_"),
         ("Chara_Image/Face_B/", "vs_chara_"), ("Chara_Image/Face_C/", "arcade_chara_"),
         ("Chara_Image/Face_D/", "faceD_"), ("Chara_Image/Story_Stand/", "StoryStand_"),
         ("CharaSelect_S3/tex/", "CS_CharacterImage_")]


class Source:
    """Arquivos de um ou mais paks, por caminho normalizado (RED/Content/...), leitura preguicosa."""
    def __init__(self, paks, key=None):
        self.files = {}
        for p in paks:
            pak = PakFile(p, key)
            for e in pak.entries:
                n = pak.full_path(e)
                if not n.startswith("RED/"):
                    n = "RED/Content/" + n
                self.files[n.lower()] = (n, pak, e)

    def get(self, lower):
        n, pak, e = self.files[lower]
        return pak.read(e)

    def items(self):
        return [(n, (lambda pak=pak, e=e: pak.read(e))) for n, pak, e in self.files.values()]


def make_conv(base, new):
    rx_path = re.compile(r"(/chara/)" + base + r"(/|$)", re.I)
    rx_data = re.compile(r"^(BBS_|COL_)" + base + r"(EF)?$", re.I)
    rx_pkg = re.compile(r"(/)(BBS_|COL_)" + base + r"(EF)?$", re.I)

    def case(src, repl):
        return repl.lower() if src.islower() else repl

    def conv(s):
        t = rx_path.sub(lambda m: m.group(1) + case(m.group(0)[len(m.group(1)):len(m.group(1)) + 3], new) + m.group(2), s)
        t = rx_data.sub(lambda m: m.group(1) + case(m.group(0)[len(m.group(1)):len(m.group(1)) + 3], new) + (m.group(2) or ""), t)
        t = rx_pkg.sub(lambda m: m.group(1) + m.group(2) + new + (m.group(3) or ""), t)
        return t
    return conv


def convert_uexp(b, base, new):
    for a, c in (("/Chara/%s/" % base, "/Chara/%s/" % new), ("/chara/%s/" % base.lower(), "/chara/%s/" % new.lower())):
        for enc in ("ascii", "utf-16-le"):
            b = b.replace(a.encode(enc), c.encode(enc))
    return b


def rename_path(path, base, new):
    p = re.sub(r"(RED/Content/Chara/)" + base + "/", r"\g<1>" + new + "/", path, flags=re.I)
    return re.sub(r"/(BBS_|COL_)" + base + r"(EF)?\.", lambda m: "/" + m.group(1) + new + (m.group(2) or "") + ".", p, flags=re.I)


# ---- reparo de dependencias de pre-carga (fix_preload_dependencies.py do port Xbox) ----------
PRELOAD_CLASSES = {"REDPawnMaterials", "REDMeshMaterialSet", "REDAnimSet"}


def preload_repair(b, x):
    s = Summary(b)
    ns = [v[0] for v in s.names()]
    p = 32 + struct.unpack_from("<i", b, 28)[0] + 4
    nameoff = struct.unpack_from("<ii", b, p)[1]
    ec, eo, ic, io = struct.unpack_from("<iiii", b, p + 16)
    if ec != 1:
        return b, None
    cls = struct.unpack_from("<i", b, eo)[0]
    if cls >= 0:
        return b, None

    def fn(off):
        idx, num = struct.unpack_from("<ii", b, off)
        return ns[idx] + ("_" + str(num - 1) if num else "")
    if fn(io + (-cls - 1) * 28 + 20) not in PRELOAD_CLASSES:
        return b, None
    if struct.unpack_from("<ii", b, nameoff - 16) != (0, 0):
        return b, None
    count, offset = struct.unpack_from("<ii", b, nameoff - 8)
    if offset + count * 4 != len(b) or struct.unpack_from("<i", b, 24)[0] != len(b):
        return b, None
    first, sbs, cbs, sbc, cbc = struct.unpack_from("<5i", b, eo + 84)
    if first != 0 or sbs + cbs + sbc + cbc != count:
        return b, None
    deps = list(struct.unpack_from("<" + str(count) + "i", b, offset))
    imports = [(fn(io + i * 28 + 20), struct.unpack_from("<i", b, io + i * 28 + 16)[0]) for i in range(ic)]

    def full(i):
        name, outer = imports[-i - 1]
        return full(outer) + "." + name if outer < 0 else name
    added = [-i - 1 for i, (name, outer) in enumerate(imports)
             if outer < 0 and full(-i - 1).startswith("/Game/") and -i - 1 not in deps]
    if not added:
        return b, None
    size, pos = struct.unpack_from("<qq", b, eo + 28)
    bulk = struct.unpack_from("<q", b, nameoff - 24)[0]
    if pos != len(b) or size != len(x) - 4 or bulk != len(b) + len(x) - 4:
        return b, None
    nd = deps[:sbs + cbs] + added + deps[sbs + cbs:]
    new = bytearray(b[:offset] + struct.pack("<" + str(len(nd)) + "i", *nd))
    delta = len(new) - len(b)
    struct.pack_into("<i", new, 24, len(new))
    struct.pack_into("<i", new, nameoff - 8, len(nd))
    struct.pack_into("<q", new, nameoff - 24, bulk + delta)
    struct.pack_into("<q", new, eo + 36, pos + delta)
    struct.pack_into("<i", new, eo + 92, cbs + len(added))
    assert struct.unpack_from("<q", new, eo + 36)[0] == len(new)
    assert [v[0] for v in Summary(bytes(new)).names()] == ns
    return bytes(new), [full(i) for i in added]


def apply_moves(moves, conv):
    """Envolve conv (nomes do uasset) com as realocacoes de pasta (mesmo tamanho)."""
    if not moves:
        return conv
    rxs = [(re.compile(r"(?i)/chara/" + re.escape(a) + r"(?=/|$)"), b) for a, b in moves]

    def f(t):
        for rx, b in rxs:
            t = rx.sub(lambda m, b=b: "/chara/" + b.lower() if m.group(0)[1:6].islower() else "/Chara/" + b, t)
        return conv(t)
    return f


def move_bytes(b, moves):
    for a, c in moves:
        for x, y in (("/Chara/" + a + "/", "/Chara/" + c + "/"), (("/chara/" + a + "/").lower(), ("/chara/" + c + "/").lower())):
            for enc in ("ascii", "utf-16-le"):
                b = b.replace(x.encode(enc), y.encode(enc))
    return b


def build(new, base, mod_paks, keep, keep_refs, preload_fix, out_dir, moves=(), ui_paks=(), extra_files=()):
    new, base = new.upper(), base.upper()
    for a, c in moves:
        assert len(a) == len(c), f"--move precisa de caminhos do mesmo tamanho: {a} / {c}"
    assert len(new) == len(base) == 3
    key = load_key()
    print("reading game paks...")
    game = Source(PAKS, key)
    mod = Source(mod_paks, key)
    rep = dict(novo=new, base=base, mods=[str(p) for p in mod_paks], keep=keep, do_jogo=0, do_mod=0,
               shared_novos=0, shared_substituicoes_ignoradas=0, ignorados=[], referencias_faltando=[], preload=[])
    base_prefix = ("RED/Content/Chara/%s/" % base).lower()
    files = {}
    for lower, (n, pak, e) in game.files.items():
        if lower.startswith(base_prefix):
            files[lower] = (n, lambda pak=pak, e=e: pak.read(e))
            rep["do_jogo"] += 1
    move_src = [(("RED/Content/Chara/" + a + "/").lower(), "RED/Content/Chara/" + c + "/") for a, c in moves]
    rep["movidos"] = 0
    for lower, (n, pak, e) in mod.files.items():
        parts = n.split("/")
        getter = lambda pak=pak, e=e: pak.read(e)
        mv = next(((ls, dst) for ls, dst in move_src if lower.startswith(ls)), None)
        if mv:
            nn = mv[1] + n[len(mv[0]):]
            files[nn.lower()] = (nn, getter)
            rep["movidos"] += 1
        elif lower.startswith(base_prefix):
            files[lower] = (files[lower][0] if lower in files else n, getter)
            rep["do_mod"] += 1
        elif len(parts) > 3 and parts[2] == "Chara" and parts[3].upper() in keep:
            files[lower] = (n, getter)
            rep["do_mod"] += 1
        elif len(parts) > 2 and parts[2] == "Shared":
            if lower in game.files:
                rep["shared_substituicoes_ignoradas"] += 1
            else:
                files[lower] = (n, getter)
                rep["shared_novos"] += 1
        elif any(lower.endswith(x.lower()) for x in extra_files):
            files[lower] = (n, getter)       # arquivo do mod pedido pela receita (ex. config do DIO)
            rep.setdefault("extras", []).append(n)
        elif len(parts) > 2 and parts[2] in ("UI", "Audio") or "/Localization/" in n:
            pass   # UI vai para o pak de UI; audio/texto do personagem-base nao sao copiados
        else:
            rep["ignorados"].append(n)
    conv = apply_moves(moves, make_conv(base, new))
    out = {}
    for lower, (n, get) in files.items():
        parts = n.split("/")
        data = get()
        if keep_refs and len(parts) > 3 and parts[2] == "Chara" and parts[3].upper() in keep:
            out[n] = data
            continue
        np_ = rename_path(n, base, new) if lower.startswith(base_prefix) else n
        if n.endswith(".uasset"):
            data, _ = rename_fn(data, conv)
        elif n.endswith(".uexp"):
            data = convert_uexp(move_bytes(data, moves), base, new)
        out[np_] = data
    if preload_fix:
        for n in list(out):
            if not n.endswith(".uasset") or "/Material/Color" not in n:
                continue
            x = out.get(n[:-6] + "uexp")
            if x is None:
                continue
            b2, added = preload_repair(out[n], x)
            if added:
                out[n] = b2
                rep["preload"].append([n, added])
    have = {k[len("RED/Content/"):].rsplit(".", 1)[0].lower() for k in out if k.endswith(".uasset")}
    have |= {k[len("red/content/"):].rsplit(".", 1)[0] for k in game.files if k.endswith(".uasset")}
    for n, data in out.items():
        if not n.endswith(".uasset"):
            continue
        for s, *_ in Summary(data).names():
            if s.lower().startswith("/game/") and not s.lower().startswith("/game/localization"):
                k = s[len("/Game/"):].lower()
                if k not in have and not any(h.startswith(k + "_") for h in ()):
                    rep["referencias_faltando"].append([n, s])
    rep["referencias_faltando"] = rep["referencias_faltando"][:200]
    rep["ignorados"] = sorted(set(rep["ignorados"]))
    out_dir.mkdir(parents=True, exist_ok=True)
    write_pak(out_dir / f"DBFZX_{new}.pak", out)
    ui_files, icon = build_ui(new, base, game, mod, Source(list(ui_paks), key) if ui_paks else None)
    rep["vs_C_da_imagem_normal"] = ui_files.pop("_c_from_plain")
    write_pak(out_dir / f"DBFZX_{new}_UI.pak", ui_files)
    rep["icone"] = icon
    (out_dir / f"DBFZX_{new}.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{new}: {len(out)} files (game {rep['do_jogo']}, mod {rep['do_mod']}, new shared {rep['shared_novos']}, "
          f"shared ignored {rep['shared_substituicoes_ignoradas']}, other ignored {len(rep['ignorados'])}, "
          f"missing refs {len(rep['referencias_faltando'])}, preload {len(rep['preload'])}); UI {len(ui_files)} files; icon {icon}")
    return rep


def build_ui(new, base, game, mod, extra=None):
    """Retratos (7 tipos) e icone da selecao: do mod se ele tiver (nomeados pelo base), senao dos
    paks extras (--ui-paks), senao do jogo."""
    files = {}
    for folder, prefix in KINDS:
        stem = ("RED/Content/UI/" + folder + prefix + base).lower()
        src = mod if stem + ".uasset" in mod.files else (
            extra if extra is not None and stem + ".uasset" in extra.files else game)
        if stem + ".uasset" not in src.files:
            continue
        for ext in (".uasset", ".uexp", ".ubulk"):
            if stem + ext not in src.files:
                continue
            data = src.get(stem + ext)
            if ext == ".uasset":
                rx = re.compile(re.escape(prefix) + base + "$", re.I)
                data, _ = rename_fn(data, lambda s, rx=rx, prefix=prefix: rx.sub(
                    lambda m: (prefix + new).lower() if m.group(0).islower() else prefix + new, s))
            files["RED/Content/UI/" + folder + prefix + new + ext] = data
    # variante _C da tela de VS (usada no 1P): do mod; senao copia da imagem normal do mod (a
    # variante do personagem-base mostraria o personagem errado); senao a do jogo, se existir
    c_from_plain = False
    stem_c = ("RED/Content/UI/Chara_Image/Face_B/vs_chara_" + base + "_C").lower()
    stem_n = ("RED/Content/UI/Chara_Image/Face_B/vs_chara_" + base).lower()
    if stem_c + ".uasset" in mod.files:
        src, stem = mod, stem_c
    elif stem_n + ".uasset" in mod.files and stem_c + ".uasset" in game.files:
        src, stem, c_from_plain = mod, stem_n, True
    elif stem_c + ".uasset" in game.files:
        src, stem = game, stem_c
    else:
        src = None
    if src is not None:
        ua = src.get(stem + ".uasset")
        ue = src.get(stem + ".uexp")
        pkg = Package(ua, ue)
        rx = re.compile(r"(?i)vs_chara_" + base + r"(_C)?$")
        pkg.rename_names(lambda s: rx.sub(lambda m: ("vs_chara_" + new + "_C").lower()
                                           if m.group(0).islower() else "vs_chara_" + new + "_C", s))
        ua, ue = pkg.serialize()
        files["RED/Content/UI/Chara_Image/Face_B/vs_chara_" + new + "_C.uasset"] = ua
        files["RED/Content/UI/Chara_Image/Face_B/vs_chara_" + new + "_C.uexp"] = ue
        if stem + ".ubulk" in src.files:
            files["RED/Content/UI/Chara_Image/Face_B/vs_chara_" + new + "_C.ubulk"] = src.get(stem + ".ubulk")
    icons = sorted(k for k in mod.files if re.search(r"/charaselect_s3/tex/cs_cicon\d\d\.uasset$", k))
    if not icons and extra is not None:
        icons = sorted(k for k in extra.files if re.search(r"/charaselect_s3/tex/cs_cicon\d\d\.uasset$", k))
        mod = extra
    if not icons:     # sem icone no mod: o do personagem-base no jogo
        from build_ui import icon_index_of
        icons = [f"red/content/ui/charaselect_s3/tex/cs_cicon{icon_index_of(base) + 1:02d}.uasset"]
        mod = game
    icon = None
    if icons:
        stem = icons[0][:-len(".uasset")]
        leaf = mod.files[icons[0]][0].rsplit("/", 1)[1][:-len(".uasset")]
        for ext in (".uasset", ".uexp", ".ubulk"):
            if stem + ext in mod.files:
                data = mod.get(stem + ext)
                if ext == ".uasset":
                    data, _ = rename_fn(data, lambda s: s.replace("/CharaSelect_S3/tex/", f"/CharaSelect_S3/{new}/"))
                files[f"RED/Content/UI/CharaSelect_S3/{new}/{leaf}{ext}"] = data
        icon = f"/Game/UI/CharaSelect_S3/{new}/{leaf}.{leaf}"
    files["_c_from_plain"] = c_from_plain
    return files, icon


def build_ui_only(new, base, mod_paks, out_dir):
    """Arte de um mod (de substituicao ou de slot) para um extra que ja tem personagem proprio."""
    key = load_key()
    game, mod = Source(PAKS, key), Source(mod_paks, key)
    files, icon = build_ui(new, base, game, mod)
    c_plain = files.pop("_c_from_plain")
    from_mod = sorted({n.rsplit("/", 1)[1].rsplit(".", 1)[0] for n in files})
    out_dir.mkdir(parents=True, exist_ok=True)
    write_pak(out_dir / f"DBFZX_{new}_UI.pak", files)
    print(f"{new}: UI {len(files)} files ({', '.join(from_mod)}); _C from the normal image: {c_plain}; icon {icon}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("new")
    ap.add_argument("base")
    ap.add_argument("paks", nargs="+")
    ap.add_argument("--keep", default="")
    ap.add_argument("--keep-refs", action="store_true")
    ap.add_argument("--preload-fix", action="store_true")
    ap.add_argument("--move", action="append", default=[], help="ORIGEM=DESTINO, ex. VGS/Costume02=VTS/Costume92")
    ap.add_argument("--ui-paks", nargs="*", default=[])
    ap.add_argument("--extra-file", action="append", default=[], help="arquivo do mod copiado como esta (ex. Config/Windows/WindowsEngine.ini)")
    ap.add_argument("--ui-only", action="store_true", help="so o pak de arte (DBFZX_<NOVO>_UI.pak)")
    ap.add_argument("--out", default=str(CHARS))
    a = ap.parse_args()
    keep = [k.upper() for k in a.keep.split(",") if k]
    if a.ui_only:
        build_ui_only(a.new.upper(), a.base.upper(), [Path(p) for p in a.paks], Path(a.out))
        return
    moves = [tuple(m.split("=", 1)) for m in a.move]
    build(a.new, a.base, [Path(p) for p in a.paks], keep, a.keep_refs, a.preload_fix, Path(a.out),
          moves, [Path(p) for p in a.ui_paks], a.extra_file)


if __name__ == "__main__":
    main()
