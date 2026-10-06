"""
detectar_mod.py - Descobre sozinho a receita de um mod de personagem (para o instalador).

Uso: python detectar_mod.py <zip | rar | 7z | pasta | pak> [...]     -> imprime a receita (JSON)

Um mod de SUBSTITUICAO poe arquivos em Chara/<COD>/ de um personagem do jogo. Para virar um
personagem novo, a receita diz:
  base      o personagem substituido: a pasta de personagem do jogo com o moveset (BBS_<COD>)
            e, em empate, com mais arquivos;
  keep      pastas de Chara/ que NAO sao personagens do jogo (assets proprios do mod: GOD, SRG,
            VGF, WTN, _ULT...): copiadas como estao;
  move      pastas de OUTRO personagem do jogo que o mod altera e que os arquivos do base
            referenciam (ex.: modelo do Vegito em VGS/Costume02): realocadas para a pasta do novo
            personagem (mesmo tamanho de caminho), o personagem original fica intacto. Pastas de
            outros personagens que o base nao usa sao ignoradas (eram so substituicoes extras);
  textos    text.json do Unverum junto do pak, ou o proprio pak se ele tiver Localization;
  nomes     CHARA_NAME_L/S do base nos textos do mod (ou o nome do arquivo);
  codigo    sugestao de 3 letras livres.
"""
import collections
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from pak import PakFile, load_key          # noqa: E402
from uasset import Summary                 # noqa: E402

GAME_CODES = {"GKS", "VGS", "PCN", "GHT", "FRN", "GNN", "TRS", "CEN", "AEN", "GTL", "KRN", "BUK", "BUN", "NPN",
              "ASN", "YMN", "TNN", "GHU", "HTN", "GKB", "VGB", "BSN", "GBR", "TON", "TOA", "TOZ", "GKN", "VGN",
              "BRS", "ZMB", "BDN", "VTB", "AVP", "CLF", "JRN", "VDN", "SGN", "JNN", "NHY", "EST", "KFS", "MGS",
              "MTN", "OSM", "GFF", "TOP", "DMY", "DGF"}
SHARED_CODES = {"CMN"}        # pastas comuns do jogo (nao sao personagens)


def unpack(src, work):
    """Lista de .pak (e a pasta onde ficam) a partir de zip/rar/7z/pasta/pak."""
    src = Path(src)
    if src.is_dir():
        root = src
    elif src.suffix.lower() == ".pak":
        return [src], src.parent
    elif src.suffix.lower() == ".zip":
        root = Path(work) / src.stem
        zipfile.ZipFile(src).extractall(root)
    elif src.suffix.lower() in (".rar", ".7z"):
        root = Path(work) / src.stem
        root.mkdir(parents=True, exist_ok=True)
        subprocess.run([r"C:\Windows\System32\tar.exe", "-xf", str(src.resolve())], cwd=root, check=True,
                       creationflags=0x08000000)    # sem janela de console
    else:
        raise SystemExit(f"{src}: unsupported format")
    paks = sorted(root.rglob("*.pak"))
    return paks, root


def scan(paks, key):
    files = {}
    for p in paks:
        pak = PakFile(p, key)
        for e in pak.entries:
            files[pak.full_path(e)] = (pak, e)
    return files


def chara_of(path):
    parts = path.split("/")
    return parts[3] if len(parts) > 4 and parts[2] == "Chara" else None


def same_len_dest(sub, new):
    """X/Costume02 -> NEW/Costume92 (mesmo tamanho; o 1o digito vira 9)."""
    m = re.fullmatch(r"(Costume)(\d)(\d)", sub)
    return f"{new}/{m.group(1)}9{m.group(3)}" if m else None


def suggest_code(name, used):
    letters = re.sub(r"[^A-Za-z]", "", name).upper() or "XXX"
    cands = [letters[:3], letters[0] + letters[-2:], letters[0] + letters[2:4] if len(letters) > 3 else ""]
    for c in cands + [letters[0] + a + b for a in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" for b in "XYZQKW"]:
        if len(c) == 3 and c not in GAME_CODES and c not in used and c not in SHARED_CODES:
            return c
    raise SystemExit("no free code left")


def text_pairs_json(path):
    raw = path.read_bytes().decode("utf-8-sig")
    try:
        d = json.loads(raw)
    except json.JSONDecodeError:
        d = json.loads(re.sub(r",\s*([\]}])", r"\1", raw))
    return {e["header"]: e["text"] for e in d.get("Entries", []) if "header" in e}


def detect(src, used_codes=(), key=None, work=None):
    key = key or load_key()
    work = work or tempfile.mkdtemp(prefix="dbfz_mod_")
    paks, root = unpack(src, work)
    if not paks:
        raise SystemExit(f"{src}: no .pak found")
    files = scan(paks, key)
    count = collections.Counter(chara_of(n) for n in files if chara_of(n))
    game = [c for c in count if c in GAME_CODES]
    if not game:
        raise SystemExit(f"{src}: the mod does not replace any game character (nothing in Chara/<CODE>/)")
    has_moveset = {c for c in game if any(re.search(rf"/Chara/{c}/Common/Data/BBS_{c}\.uasset$", n) for n in files)}
    base = max(game, key=lambda c: (c in has_moveset, count[c]))
    keep = sorted(c for c in count if c not in GAME_CODES and c not in SHARED_CODES)

    # referencias dos arquivos do base para pastas de outros personagens do jogo que o mod traz
    shipped = {n.rsplit(".", 1)[0].replace("RED/Content/", "/Game/").lower() for n in files}
    refs = collections.Counter()
    for n, (pak, e) in files.items():
        if chara_of(n) == base and n.endswith(".uasset"):
            for s, *_ in Summary(pak.read(e)).names():
                m = re.match(r"/Game/Chara/([^/]+)/([^/]+)/", s)
                if m and m.group(1) in GAME_CODES and m.group(1) != base and s.lower() in shipped:
                    refs[f"{m.group(1)}/{m.group(2)}"] += 1
    others = sorted(set(game) - {base})

    # textos e nomes
    texts, pairs = [], {}
    tj = sorted(root.rglob("text.json")) if Path(root).is_dir() else []
    if tj:
        texts.append(str(tj[0]))
        pairs = text_pairs_json(tj[0])
    else:
        for p in paks:
            pak = PakFile(p, key)
            loc = [e for e in pak.entries if pak.full_path(e).lower().endswith("localization/int/redgame.uexp")]
            if loc:
                texts.append(str(p))
                from build_texts import parse
                try:
                    pairs = dict(parse(pak.read(loc[0]))[2])
                except SystemExit:
                    pairs = {}
                break
    stem = Path(src).stem
    long_ = pairs.get(f"CHARA_NAME_L_{base}") or re.sub(r"[_\-]+", " ", stem).strip()
    short = pairs.get(f"CHARA_NAME_S_{base}") or long_
    code = suggest_code(short, set(used_codes) | set(keep))   # nunca igual a uma pasta propria do mod
    moves, warn = [], []
    for sub in sorted(refs):
        dest = same_len_dest(sub.split("/", 1)[1], code)
        if dest:
            moves.append(f"{sub}={dest}")
        else:
            warn.append(f"the character uses {sub} (changed by the mod) and it cannot be relocated; the original game files will be used")
    ignored = [c for c in others if not any(m.startswith(c + "/") for m in moves)]
    ui = sorted({n.split("/")[-1].rsplit(".", 1)[0] for n in files if "/UI/" in n and n.endswith(".uasset")})
    recipe = {"codigo": code, "base": base,
              "nomes": {"en": [long_, short]},
              "construir": {"paks": [str(p) for p in paks]},
              "textos": texts}
    if keep:
        recipe["construir"]["keep"] = keep
    if moves:
        recipe["construir"]["move"] = moves
    info = {"arquivos": len(files), "por_pasta": dict(count), "moveset": sorted(has_moveset),
            "outros_personagens_ignorados": ignored, "arte_ui": ui, "avisos": warn}
    return recipe, info


if __name__ == "__main__":
    used = []
    for a in sys.argv[1:]:
        r, info = detect(a, used)
        used.append(r["codigo"])
        print(json.dumps({"receita": r, "detalhes": info}, indent=1, ensure_ascii=False))
