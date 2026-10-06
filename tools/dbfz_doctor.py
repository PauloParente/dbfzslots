"""
dbfz_doctor.py - Diagnostico do ambiente de mods do Dragon Ball FighterZ.

Uso:
    python dbfz_doctor.py                 # analisa a copia modificada (..\\game)
    python dbfz_doctor.py --game <pasta>  # analisa outra instalacao
    python dbfz_doctor.py --crashes 10    # mostra mais relatorios de crash

O relatorio sai no console e tambem e salvo em tools\\reports\\.
"""
import argparse
import datetime as dt
import hashlib
import os
import re
import struct
import sys
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
DEFAULT_GAME = TOOLS_DIR.parent / "game"
STEAM_GAME = Path(r"C:\Program Files (x86)\Steam\steamapps\common\DRAGON BALL FighterZ")
# saves/config/crashes da copia modificada (slots.ini [user] separate_saves=1); senao, os da Steam
_MODDED_DATA = Path(__file__).resolve().parent.parent / "game" / "UserData" / "DBFighterZ" / "Saved"
USER_DATA = _MODDED_DATA if _MODDED_DATA.exists() else Path(os.environ.get("LOCALAPPDATA", "")) / "DBFighterZ" / "Saved"

GAME_EXES = ["RED-Win64-Shipping.exe", "RED-Win64-Shipping-eac-nop-loaded.exe"]
# DLLs que o Windows carrega da pasta do jogo e que loaders de mod costumam usar
PROXY_DLLS = ["dsound.dll", "dinput8.dll", "version.dll", "winmm.dll", "xinput1_3.dll",
              "xinput1_4.dll", "dxgi.dll", "d3d11.dll", "dwmapi.dll", "winhttp.dll"]
KNOWN_CONFIG_KEYS = {"Enable_Console", "File_Access_Logging", "Loose_File_Loading",
                     "Extra_Costumes_Patch", "Unlock_All_Colors", "Log_Script_Errors"}
PAK_MAGIC = 0x5A6F12E1


class Report:
    def __init__(self):
        self.lines = []
        self.counts = {"OK": 0, "AVISO": 0, "ERRO": 0}

    def section(self, title):
        self._out("")
        self._out("=" * 78)
        self._out(title)
        self._out("=" * 78)

    def info(self, msg):
        self._out(f"  {msg}")

    def status(self, level, msg):
        self.counts[level] += 1
        self._out(f"  [{level:5}] {msg}")

    def _out(self, s):
        self.lines.append(s)
        print(s)


def fmt_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024


def mtime(p):
    return dt.datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")


def sha256_prefix(p, chunk=1 << 22):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()[:16]


# --------------------------------------------------------------------------- #
# Assinaturas (padrao bytes + mascara "xx?x") embutidas nos plugins .asi
# --------------------------------------------------------------------------- #
def extract_signatures(asi_bytes):
    """Encontra mascaras 'xx?x' e le os bytes do padrao logo depois delas."""
    sigs = []
    for m in re.finditer(rb"(?<=\x00)[x?]{8,}(?=\x00)", asi_bytes):
        mask = m.group().decode()
        pos = m.end()
        # pula o terminador e o alinhamento ate o inicio do padrao
        while pos < len(asi_bytes) and asi_bytes[pos] == 0 and pos - m.end() < 16:
            pos += 1
        pattern = asi_bytes[pos:pos + len(mask)]
        if len(pattern) == len(mask):
            sigs.append((m.start(), mask, pattern))
    return sigs


def scan_signature(data, mask, pattern, max_hits=5):
    """Procura o padrao no executavel. Retorna a lista de offsets encontrados."""
    # usa o maior trecho fixo como ancora para o find() e confere o resto
    best_start, best_len, i = 0, 0, 0
    while i < len(mask):
        if mask[i] == "x":
            j = i
            while j < len(mask) and mask[j] == "x":
                j += 1
            if j - i > best_len:
                best_start, best_len = i, j - i
            i = j
        else:
            i += 1
    anchor = pattern[best_start:best_start + best_len]
    fixed = [k for k, c in enumerate(mask) if c == "x"]
    hits, pos = [], data.find(anchor)
    while pos != -1 and len(hits) < max_hits:
        base = pos - best_start
        if base >= 0 and all(data[base + k] == pattern[k] for k in fixed):
            hits.append(base)
        pos = data.find(anchor, pos + 1)
    return hits


# --------------------------------------------------------------------------- #
# .pak
# --------------------------------------------------------------------------- #
def read_pak_footer(p):
    size = p.stat().st_size
    with open(p, "rb") as f:
        f.seek(max(0, size - 1024))
        tail = f.read()
    i = tail.rfind(struct.pack("<I", PAK_MAGIC))
    if i < 0:
        return None
    version, = struct.unpack_from("<i", tail, i + 4)
    index_offset, index_size = struct.unpack_from("<qq", tail, i + 8)
    encrypted = tail[i - 1] == 1 if version >= 4 and i > 0 else False
    return {"version": version, "index_offset": index_offset,
            "index_size": index_size, "encrypted_index": encrypted}


# --------------------------------------------------------------------------- #
# Checagens
# --------------------------------------------------------------------------- #
def check_install(r, game):
    r.section(f"1. INSTALACAO  ({game})")
    if not game.exists():
        r.status("ERRO", "Pasta do jogo nao existe.")
        return False
    win64 = game / "RED" / "Binaries" / "Win64"
    found_any = False
    for name in GAME_EXES:
        p = win64 / name
        if p.exists():
            found_any = True
            r.status("OK", f"{name}: {fmt_size(p.stat().st_size)}, modificado {mtime(p)}, "
                           f"sha256 {sha256_prefix(p)}")
        else:
            r.info(f"(ausente) {name}")
    if not found_any:
        r.status("ERRO", "Nenhum executavel do jogo encontrado em RED\\Binaries\\Win64.")
        return False
    appid = win64 / "steam_appid.txt"
    if appid.exists():
        r.status("OK", f"steam_appid.txt = {appid.read_text().strip()} "
                       "(permite abrir o exe direto, com a Steam aberta)")
    else:
        r.status("AVISO", "steam_appid.txt ausente: abrir o exe direto pode reiniciar via Steam.")
    return True


def check_loader(r, game):
    r.section("2. LOADER DE MODS (ASI)")
    win64 = game / "RED" / "Binaries" / "Win64"
    proxies = [d for d in PROXY_DLLS if (win64 / d).exists()]
    if not proxies:
        r.status("AVISO", "Nenhum loader encontrado: plugins .asi nao serao carregados.")
        return
    for d in proxies:
        data = (win64 / d).read_bytes()
        desc = "Ultimate ASI Loader" if b"U\x00l\x00t\x00i\x00m\x00a\x00t\x00e\x00" in data \
            or b"Ultimate-ASI-Loader" in data else "desconhecido"
        r.status("OK", f"{d} ({desc}, {fmt_size(len(data))}, {mtime(win64 / d)})")
    if len(proxies) > 1:
        r.status("AVISO", f"Mais de uma DLL proxy ({', '.join(proxies)}): pode carregar plugins 2x.")


def check_plugins(r, game):
    r.section("3. PLUGINS E CONFIG")
    pdir = game / "RED" / "Binaries" / "Win64" / "plugins"
    if not pdir.exists():
        r.status("AVISO", "Pasta plugins\\ nao existe.")
        return []
    asis = sorted(pdir.glob("*.asi"))
    for a in asis:
        r.status("OK", f"{a.name} ({fmt_size(a.stat().st_size)}, {mtime(a)})")
    cfg = pdir / "config.toml"
    if not cfg.exists():
        r.status("AVISO", "config.toml ausente: plugins vao usar os valores padrao.")
        return asis
    try:
        conf = tomllib.loads(cfg.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        r.status("ERRO", f"config.toml invalido: {e}")
        return asis
    for k, v in conf.items():
        tag = "OK" if k in KNOWN_CONFIG_KEYS else "AVISO"
        extra = "" if tag == "OK" else "  <- chave desconhecida (erro de digitacao?)"
        r.status(tag, f"{k} = {v}{extra}")
    for k in sorted(KNOWN_CONFIG_KEYS - conf.keys()):
        r.info(f"(nao definido) {k}")
    if not conf.get("Enable_Console"):
        r.info("Dica: Enable_Console = true abre um console com o log dos plugins ao iniciar.")
    return asis


def check_signatures(r, game, asis):
    r.section("4. ASSINATURAS DOS PLUGINS x EXECUTAVEL ATUAL")
    r.info("Cada plugin procura trechos de codigo no exe. Se o jogo atualizou, o trecho")
    r.info("pode ter mudado e o recurso do plugin para de funcionar ('broken').")
    win64 = game / "RED" / "Binaries" / "Win64"
    exes = [(n, (win64 / n).read_bytes()) for n in GAME_EXES if (win64 / n).exists()]
    for a in asis:
        sigs = extract_signatures(a.read_bytes())
        r.info("")
        r.info(f"{a.name}: {len(sigs)} assinaturas encontradas no plugin")
        for idx, (off, mask, pattern) in enumerate(sigs):
            preview = " ".join("??" if c == "?" else f"{b:02X}"
                               for c, b in zip(mask[:12], pattern[:12]))
            results = []
            for exe_name, data in exes:
                hits = scan_signature(data, mask, pattern)
                short = "eac-nop" if "eac" in exe_name else "shipping"
                results.append((short, len(hits)))
            worst = min(n for _, n in results)
            ambiguous = any(n > 1 for _, n in results)
            level = "ERRO" if worst == 0 else ("AVISO" if ambiguous else "OK")
            res = ", ".join(f"{s}={'QUEBRADA' if n == 0 else ('%d hits' % n if n > 1 else 'ok')}"
                            for s, n in results)
            r.status(level, f"#{idx:02d} [{preview}{' ...' if len(mask) > 12 else ''}] -> {res}")


def check_paks(r, game):
    r.section("5. ARQUIVOS .PAK E MODS")
    paks_dir = game / "RED" / "Content" / "Paks"
    for p in sorted(paks_dir.glob("*.pak")):
        ft = read_pak_footer(p)
        sig = p.with_suffix(".sig").exists()
        if ft is None:
            r.status("ERRO", f"{p.name}: rodape de .pak nao encontrado (arquivo corrompido?)")
            continue
        r.status("OK", f"{p.name}: {fmt_size(p.stat().st_size)}, pak v{ft['version']}, "
                       f"indice {'criptografado' if ft['encrypted_index'] else 'aberto'}, "
                       f".sig {'sim' if sig else 'nao'}")
    mods_dir = paks_dir / "~mods"
    mod_paks = sorted(mods_dir.rglob("*.pak")) if mods_dir.exists() else []
    if not mod_paks:
        r.info("Nenhum mod em Paks\\~mods.")
    for p in mod_paks:
        ft = read_pak_footer(p)
        rel = p.relative_to(paks_dir)
        if ft is None:
            r.status("ERRO", f"{rel}: nao e um .pak valido")
        elif ft["version"] > 4:
            r.status("ERRO", f"{rel}: pak v{ft['version']} - o jogo (UE 4.17) so le ate v4. "
                             "Reempacote com UnrealPak/repak na versao 4.")
        else:
            r.status("OK", f"{rel}: {fmt_size(p.stat().st_size)}, pak v{ft['version']}")
    # arquivos soltos (Loose_File_Loading)
    content = game / "RED" / "Content"
    ignore = {"Paks", "Movies", "Splash"}
    loose = [f for d in content.iterdir() if d.is_dir() and d.name not in ignore
             for f in d.rglob("*") if f.is_file()]
    if loose:
        r.status("OK", f"{len(loose)} arquivos soltos em RED\\Content (carregados via Loose_File_Loading)")
        for f in loose[:15]:
            r.info(f"   {f.relative_to(content)}")
        if len(loose) > 15:
            r.info(f"   ... e mais {len(loose) - 15}")
        uassets = {f.with_suffix("") for f in loose if f.suffix == ".uasset"}
        uexps = {f.with_suffix("") for f in loose if f.suffix == ".uexp"}
        for missing in sorted(uassets - uexps)[:10]:
            r.status("AVISO", f"{missing.relative_to(content)}.uasset sem .uexp correspondente")
        for missing in sorted(uexps - uassets)[:10]:
            r.status("ERRO", f"{missing.relative_to(content)}.uexp sem .uasset correspondente")
    else:
        r.info("Nenhum arquivo solto em RED\\Content.")


def check_crashes(r, how_many):
    r.section("6. RELATORIOS DE CRASH (mais recentes)")
    crash_dir = USER_DATA / "Crashes"
    ctxs = sorted(crash_dir.glob("*/CrashContext.runtime-xml"),
                  key=lambda p: p.stat().st_mtime, reverse=True) if crash_dir.exists() else []
    if not ctxs:
        r.info("Nenhum crash registrado.")
        return
    r.info(f"{len(ctxs)} crash(es) em {crash_dir}")
    for c in ctxs[:how_many]:
        try:
            root = ET.parse(c).getroot().find("RuntimeProperties")
        except ET.ParseError:
            r.status("AVISO", f"{c.parent.name}: XML ilegivel")
            continue
        g = lambda tag: (root.findtext(tag) or "").strip()
        where = "COPIA MODIFICADA" if "dbfz modded" in g("BaseDir").lower() else "Steam"
        msg = " ".join(g("ErrorMessage").split())
        r.info("")
        r.info(f"{mtime(c)}  [{where}]  tipo={g('CrashType') or '?'}  "
               f"apos {g('SecondsSinceStart')}s de jogo")
        r.info(f"   erro: {msg[:300] or '(vazio)'}")
        if g("CallStack"):
            for line in g("CallStack").splitlines()[:8]:
                r.info(f"   | {line.strip()}")
        hint = crash_hint(msg)
        if hint:
            r.info(f"   -> {hint}")


def crash_hint(msg):
    m = msg.lower()
    if "device being lost" in m or "887a0005" in m or "887a0006" in m:
        return "Crash de GPU/driver (nao costuma ser mod). Atualize o driver ou reduza overclock."
    if "fatal error" in m and ("serial size mismatch" in m or "serialsize" in m):
        return "Asset de mod incompativel com a versao do jogo (uasset/uexp de outra versao)."
    if "failed to load" in m or "couldn't find" in m or "could not find" in m:
        return "Arquivo nao encontrado: algum mod referencia um asset que nao existe."
    if "access_violation" in m or "access violation" in m:
        return "Leitura de memoria invalida: comum com plugin .asi quebrado ou asset invalido."
    return ""


def check_vanilla(r, game):
    r.section("7. JOGO DA STEAM (deveria ficar vanilla)")
    if game.resolve() == STEAM_GAME.resolve():
        r.info("Analisando a propria pasta da Steam; checagem pulada.")
        return
    win64 = STEAM_GAME / "RED" / "Binaries" / "Win64"
    if not win64.exists():
        r.info("Instalacao da Steam nao encontrada.")
        return
    leftovers = [d for d in PROXY_DLLS if (win64 / d).exists()]
    if (win64 / "plugins").exists():
        leftovers.append("plugins\\")
    mods = STEAM_GAME / "RED" / "Content" / "Paks" / "~mods"
    if mods.exists():
        leftovers.append("Content\\Paks\\~mods\\")
    if leftovers:
        r.status("AVISO", "A pasta da Steam ainda tem mods: " + ", ".join(leftovers))
    else:
        r.status("OK", "Pasta da Steam sem loader/plugins/mods.")
    r.info(f"Saves/config sao COMPARTILHADOS entre Steam e copia: {USER_DATA}")
    backups = sorted((TOOLS_DIR.parent / "backup").glob("saves_*"))
    if backups:
        r.info(f"Ultimo backup de save: {backups[-1].name}")
    else:
        r.status("AVISO", "Nenhum backup de save em ..\\backup\\saves_*")


def main():
    ap = argparse.ArgumentParser(description="Diagnostico de mods do DBFZ")
    ap.add_argument("--game", type=Path, default=DEFAULT_GAME, help="pasta do jogo")
    ap.add_argument("--crashes", type=int, default=5, help="quantos crashes mostrar")
    ap.add_argument("--no-sigs", action="store_true", help="pula a checagem de assinaturas")
    args = ap.parse_args()

    r = Report()
    r._out(f"DBFZ Doctor - {dt.datetime.now():%Y-%m-%d %H:%M:%S}")
    if check_install(r, args.game):
        check_loader(r, args.game)
        asis = check_plugins(r, args.game)
        if not args.no_sigs and asis:
            check_signatures(r, args.game, asis)
        check_paks(r, args.game)
    check_crashes(r, args.crashes)
    check_vanilla(r, args.game)

    r.section("RESUMO")
    r.info(f"OK: {r.counts['OK']}   AVISOS: {r.counts['AVISO']}   ERROS: {r.counts['ERRO']}")
    out_dir = TOOLS_DIR / "reports"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"doctor_{dt.datetime.now():%Y%m%d_%H%M%S}.txt"
    out.write_text("\n".join(r.lines), encoding="utf-8")
    print(f"\nRelatorio salvo em {out}")
    return 1 if r.counts["ERRO"] else 0


if __name__ == "__main__":
    sys.exit(main())
