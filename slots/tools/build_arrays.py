"""
build_arrays.py - Acrescenta os extras aos arrays de retratos (REDDataTextureArray) do jogo.

Uso: python build_arrays.py <saida.pak> COD=BASE[:C] [...]   (:C = vs_chara_COD_C copiada da imagem normal)

Telas como a de carregamento (vs_chara_), o HUD (cp_chara_) e a selecao buscam o retrato
de um personagem POR NOME nesses arrays, junto com Parameters (enquadramento/espelhamento).
Sem entrada, o extra cai num padrao e aparece fora de enquadramento. Para cada extra, cada
entrada do personagem-base (ex. vs_chara_PCN) e clonada com o nome e a textura do extra
(vs_chara_PCO), mantendo os Parameters do base, para quem a arte foi feita.
"""
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from pak import PakFile, load_key          # noqa: E402
from pakwrite import write_pak             # noqa: E402
from uasset_pkg import Package             # noqa: E402

from caminhos import PAKS  # noqa: E402
GAME_PAK = PAKS[0]
ARRAYS = ["UI/Chara_Image/Face_A/FaceAArray", "UI/Chara_Image/Face_B/FaceBArray",
          "UI/CharaSelect_S3/tex/CharaSelectImages", "UI/Chara_Image/Story_Stand/StoryStandImages"]


class Tags:
    """Leitor minimo de propriedades com tag (UE 4.17) sobre o .uexp."""
    def __init__(self, data, names):
        self.d, self.names = data, names

    def fname(self, p):
        i, n = struct.unpack_from("<ii", self.d, p)
        return self.names[i] + (f"_{n - 1}" if n else "")

    def tag(self, p):
        """-> dict(name, type, size, value_pos, end) ou None se for 'None'."""
        name = self.fname(p)
        if name == "None":
            return None, p + 8
        t = self.fname(p + 8)
        size, = struct.unpack_from("<i", self.d, p + 16)
        q = p + 24
        extra = {}
        if t == "StructProperty":
            extra["struct"] = self.fname(q); q += 8 + 16
        elif t == "BoolProperty":
            q += 1
        elif t in ("ByteProperty", "EnumProperty"):
            q += 8
        elif t == "ArrayProperty":
            extra["inner"] = self.fname(q); q += 8
        has_guid = self.d[q]; q += 1
        if has_guid:
            q += 16
        return dict(name=name, type=t, size=size, size_pos=p + 16, value=q, end=q + size, **extra), q + size

    def struct_fields(self, p):
        """Campos de um struct serializado por tags, ate 'None'. -> (dict nome->tag, fim)."""
        fields = {}
        while True:
            t, p = self.tag(p)
            if t is None:
                return fields, p
            fields[t["name"]] = t


def add_entries(ua, ue, pairs, report):
    pkg = Package(ua, ue)
    tg = Tags(ue, pkg.names)
    outer, p = tg.tag(0)
    if outer is None or outer["type"] != "ArrayProperty" or outer.get("inner") != "StructProperty":
        raise SystemExit("unexpected array format")
    count_pos = outer["value"]
    count, = struct.unpack_from("<i", ue, count_pos)
    inner, _ = tg.tag(count_pos + 4)
    elems_start = inner["value"]          # o tamanho da tag interna cobre todos os elementos
    elems = []
    q = elems_start
    for _ in range(count):
        fields, end = tg.struct_fields(q)
        elems.append((q, end, fields))
        q = end
    if q != outer["end"]:
        raise SystemExit("array end does not match")
    new_elems = bytearray()
    added = 0
    by_name = {tg.fname(f["Name"]["value"]).lower(): (st, en, f) for st, en, f in elems if f.get("Name")}
    for code, base, plain_c in pairs:
        rx = re.compile(r"(?i)" + base + r"(_C)?$")
        for start, end, fields in elems:
            nm = fields.get("Name")
            tx = fields.get("Texture")
            if not nm or not tx or nm["type"] != "NameProperty":
                continue
            ename = tg.fname(nm["value"])
            m0 = rx.search(ename)
            if not m0:
                continue
            fix = lambda t: rx.sub(lambda m: (code.lower() if m.group(0)[:3].islower() else code) + (m.group(1) or ""), t)
            new_name = fix(ename)
            if new_name.lower() in by_name or new_name in report.get("_feitos", []):
                continue
            # variante _C de um mod sem _C proprio: textura _C e copia da imagem normal -> parametros da normal
            src_start, src_end, src_fields = start, end, fields
            if plain_c and m0.group(1):
                plain = by_name.get(ename[:-2].lower())
                if plain:
                    src_start, src_end, src_fields = plain
            chunk = bytearray(ue[src_start:src_end])
            snm, stx = src_fields["Name"], src_fields["Texture"]
            struct.pack_into("<ii", chunk, snm["value"] - src_start, pkg.name_index(new_name), 0)
            tex_idx, = struct.unpack_from("<i", ue, tx["value"])
            if tex_idx >= 0:
                continue
            obj = pkg.imports[-tex_idx - 1]
            pkg_imp = pkg.imports[-obj[4] - 1]
            new_pkg = fix(pkg.names[pkg_imp[5]])
            new_obj = fix(pkg.names[obj[5]])
            pi = pkg.import_index(pkg.names[pkg_imp[0]], pkg.names[pkg_imp[2]], pkg_imp[4], new_pkg)
            ti = pkg.import_index(pkg.names[obj[0]], pkg.names[obj[2]], pi, new_obj)
            struct.pack_into("<i", chunk, stx["value"] - src_start, ti)
            pkg.add_serialize_dep(ti)
            report.setdefault("_feitos", []).append(new_name)
            src_note = f" (parameters from {tg.fname(snm['value'])})" if src_start != start else ""
            report.setdefault("entradas", []).append(f"{ename} -> {new_name} ({new_pkg}){src_note}")
            new_elems += chunk
            added += 1
    if not added:
        return None
    grow = len(new_elems)
    ue2 = bytearray(ue[:outer["end"]]) + new_elems + ue[outer["end"]:]
    struct.pack_into("<i", ue2, count_pos, count + added)
    struct.pack_into("<i", ue2, outer["size_pos"], outer["size"] + grow)
    struct.pack_into("<i", ue2, inner["size_pos"], inner["size"] + grow)
    ua2, ue2 = pkg.serialize(bytes(ue2))
    # confere: reler o resultado
    chk = Package(ua2, ue2)
    t2 = Tags(ue2, chk.names)
    o2, _ = t2.tag(0)
    c2, = struct.unpack_from("<i", ue2, o2["value"])
    assert c2 == count + added and o2["end"] == len(ue2) - (len(ue) - outer["end"])
    return ua2, ue2, added


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    out = sys.argv[1]
    pairs = []
    for a in sys.argv[2:]:      # COD=BASE  ou  COD=BASE:C (variante _C feita da imagem normal do mod)
        code, rest = a.upper().split("=")
        base, _, flag = rest.partition(":")
        pairs.append((code, base, flag == "C"))
    pak = PakFile(GAME_PAK, load_key())
    files = {}
    for a in ARRAYS:
        ua = pak.read(pak.find(f"RED/Content/{a}.uasset")[0])
        ue = pak.read(pak.find(f"RED/Content/{a}.uexp")[0])
        rep = {}
        r = add_entries(ua, ue, pairs, rep)
        if not r:
            print(f"{a}: nothing to add")
            continue
        ua2, ue2, added = r
        files[f"RED/Content/{a}.uasset"] = ua2
        files[f"RED/Content/{a}.uexp"] = ue2
        print(f"{a}: +{added} entries")
        for e in rep.get("entradas", []):
            print("   ", e)
    write_pak(out, files)
    print(f"{out}: {len(files)} files")


if __name__ == "__main__":
    main()
