"""
uasset_pkg.py - Editor de pacotes cozidos do UE 4.17 (.uasset + .uexp) do DBFZ.

Le o cabecalho inteiro (resumo, nomes, imports, exports, depends, asset registry,
dependencias de pre-carga), permite acrescentar nomes, imports e dependencias de
pre-carga, e regrava recalculando todos os offsets. Sem alteracoes, a regravacao
e identica ao original (conferido por roundtrip()).

Layout conferido em FaceBArray.uasset:
  resumo | nomes | imports (28 B) | exports (104 B) | depends | asset registry | pre-carga
"""
import struct

from uasset import name_hashes

SUMMARY_FIELDS = ["NameCount", "NameOffset", "GatherCount", "GatherOffset", "ExportCount", "ExportOffset",
                  "ImportCount", "ImportOffset", "DependsOffset", "SoftRefCount", "SoftRefOffset",
                  "SearchableNamesOffset", "ThumbnailTableOffset"]


class Package:
    def __init__(self, uasset, uexp):
        self.ua, self.uexp = bytes(uasset), bytes(uexp)
        d = self.ua
        p = 0

        def r(fmt):
            nonlocal p
            v = struct.unpack_from(fmt, d, p)
            p += struct.calcsize(fmt)
            return v if len(v) > 1 else v[0]
        tag, legacy = r("<Ii")
        if tag != 0x9E2A83C1 or legacy != -7:
            raise ValueError("pacote nao suportado")
        p += 12                                    # UE3 version, UE4 version, licensee
        ncustom = r("<i")
        p += ncustom * 20
        self.ths_pos = p
        r("<i")                                    # TotalHeaderSize
        fl = r("<i")
        p += fl if fl >= 0 else -fl * 2            # FolderName
        r("<I")                                    # PackageFlags
        self.f_pos = p
        self.f = dict(zip(SUMMARY_FIELDS, struct.unpack_from("<13i", d, p)))
        p += 13 * 4 + 16                           # + Guid
        self.gen_pos = p
        gc = r("<i")
        if gc != 1:
            raise ValueError("pacote com mais de uma geracao")
        p += 8
        for _ in range(2):                         # SavedByEngineVersion, CompatibleWithEngineVersion
            p += 10
            n = r("<i")
            p += n if n >= 0 else -n * 2
        p += 4                                     # CompressionFlags
        if r("<i") != 0:
            raise ValueError("pacote comprimido")
        p += 4                                     # PackageSource
        if r("<i") != 0:
            raise ValueError("AdditionalPackagesToCook nao suportado")
        self.ar_pos = p
        p += 4 + 8 + 4                             # AssetRegistryDataOffset, BulkDataStartOffset, WorldTileInfo
        if r("<i") != 0:
            raise ValueError("ChunkIDs nao suportado")
        self.pre_pos = p
        self.preload_count, self.preload_off = r("<ii")
        if p != self.f["NameOffset"]:
            raise ValueError("resumo com tamanho inesperado")
        f = self.f
        if f["GatherCount"] or f["SoftRefCount"] or f["SearchableNamesOffset"] or f["ThumbnailTableOffset"]:
            raise ValueError("secoes opcionais nao suportadas")
        # nomes
        self.names = []
        q = f["NameOffset"]
        for _ in range(f["NameCount"]):
            n, = struct.unpack_from("<i", d, q)
            if n < 0:
                raise ValueError("nome UTF-16 nao suportado")
            self.names.append(d[q + 4:q + 4 + n - 1].decode("latin-1"))
            q += 4 + n + 4
        if q != f["ImportOffset"]:
            raise ValueError("tabela de nomes nao termina nos imports")
        self.imports = [list(struct.unpack_from("<iiiiiii", d, f["ImportOffset"] + 28 * i)) for i in range(f["ImportCount"])]
        self.exports = [bytearray(d[f["ExportOffset"] + 104 * i:f["ExportOffset"] + 104 * (i + 1)]) for i in range(f["ExportCount"])]
        self.depends_blob = d[f["DependsOffset"]:self.asset_registry_offset()]
        self.ar_blob = d[self.asset_registry_offset():self.preload_off]
        self.preload = list(struct.unpack_from(f"<{self.preload_count}i", d, self.preload_off))
        if self.preload_off + 4 * self.preload_count != len(d):
            raise ValueError("pre-carga nao termina no fim do cabecalho")

    def asset_registry_offset(self):
        return struct.unpack_from("<i", self.ua, self.ar_pos)[0]

    # ---- edicao ----------------------------------------------------------------------
    def name_index(self, s, add=True):
        if s in self.names:
            return self.names.index(s)
        if not add:
            raise KeyError(s)
        self.names.append(s)
        return len(self.names) - 1

    def import_index(self, class_pkg, class_name, outer, obj):
        """Indice (negativo) do import; cria se nao existir."""
        rec = [self.name_index(class_pkg), 0, self.name_index(class_name), 0, outer, self.name_index(obj), 0]
        for i, imp in enumerate(self.imports):
            if imp == rec:
                return -i - 1
        self.imports.append(rec)
        return -len(self.imports)

    def import_name(self, idx):
        imp = self.imports[-idx - 1]
        return self.names[imp[5]] + (f"_{imp[6] - 1}" if imp[6] else "")

    def export_deps(self, i=0):
        e = self.exports[i]
        first, sbs, cbs, sbc, cbc = struct.unpack_from("<5i", e, 84)
        return first, [sbs, cbs, sbc, cbc]

    def add_serialize_dep(self, import_idx, i=0):
        """Acrescenta o import as dependencias 'serializar antes de serializar' do export."""
        first, counts = self.export_deps(i)
        seg = self.preload[first:first + counts[0]]
        if import_idx in seg:
            return
        self.preload.insert(first + counts[0], import_idx)
        counts[0] += 1
        struct.pack_into("<4i", self.exports[i], 88, *counts)
        for j in range(len(self.exports)):        # exports seguintes
            if j != i:
                fj, _ = self.export_deps(j)
                if fj > first:
                    struct.pack_into("<i", self.exports[j], 84, fj + 1)

    def rename_names(self, fn):
        """Aplica fn a cada nome (tamanho livre: a gravacao recalcula os offsets)."""
        changed = []
        for i, n in enumerate(self.names):
            m = fn(n)
            if m != n:
                self.names[i] = m
                changed.append((n, m))
        return changed

    # ---- gravacao --------------------------------------------------------------------
    def serialize(self, uexp=None):
        uexp = self.uexp if uexp is None else uexp
        names = bytearray()
        for s in self.names:
            b = s.encode("latin-1") + b"\0"
            names += struct.pack("<i", len(b)) + b + struct.pack("<HH", *name_hashes(s))
        imports = b"".join(struct.pack("<iiiiiii", *imp) for imp in self.imports)
        head = bytearray(self.ua[:self.f["NameOffset"]])
        name_off = self.f["NameOffset"]
        import_off = name_off + len(names)
        export_off = import_off + len(imports)
        depends_off = export_off + 104 * len(self.exports)
        ar_off = depends_off + len(self.depends_blob)
        pre_off = ar_off + len(self.ar_blob)
        total = pre_off + 4 * len(self.preload)
        f = dict(self.f, NameCount=len(self.names), ImportCount=len(self.imports), ImportOffset=import_off,
                 ExportCount=len(self.exports), ExportOffset=export_off, DependsOffset=depends_off)
        struct.pack_into("<i", head, self.ths_pos, total)
        struct.pack_into("<13i", head, self.f_pos, *[f[k] for k in SUMMARY_FIELDS])
        struct.pack_into("<ii", head, self.gen_pos + 4, len(self.exports), len(self.names))
        struct.pack_into("<i", head, self.ar_pos, ar_off)
        struct.pack_into("<q", head, self.ar_pos + 4, total + len(uexp) - 4)   # BulkDataStartOffset
        struct.pack_into("<ii", head, self.pre_pos, len(self.preload), pre_off)
        exports = bytearray()
        off = total
        if len(self.exports) != 1:
            raise ValueError("so pacotes com um export sao suportados na gravacao")
        e = bytearray(self.exports[0])
        struct.pack_into("<qq", e, 28, len(uexp) - 4, off)                      # SerialSize, SerialOffset
        exports += e
        out = bytes(head + names + imports + exports + self.depends_blob + self.ar_blob +
                    struct.pack(f"<{len(self.preload)}i", *self.preload))
        assert len(out) == total
        return out, uexp


def roundtrip(uasset, uexp):
    p = Package(uasset, uexp)
    ua2, ue2 = p.serialize()
    return ua2 == uasset and ue2 == uexp
