"""
ativacao.py - The mod is only in the game folder WHILE the game runs from our launcher.

  ready      <game>\\DBFZSlots_data\\ready\\     our files when the mod is off (same paths as in the game)
  displaced  <game>\\DBFZSlots_data\\displaced\\ files of other tools that sit where ours go
                                                 (e.g. Unverum's dsound.dll), put back afterwards
  state      <game>\\DBFZSlots_data\\active.json  exists only while the mod is on (journal)

ativar() moves ready -> game, desativar() moves game -> ready and puts the displaced files back.
Same drive, so moving is a rename (instant, even for GBs). desativar() also cleans up after a
crash (the launcher calls it before every launch), so opening the game from Steam finds the folder
without any of our files.
"""
import json
import shutil
import subprocess
import time
from pathlib import Path

DATA_DIR = "DBFZSlots_data"
WIN64 = "RED/Binaries/Win64"
# always ours
OURS = (f"{WIN64}/plugins/DBFZSlots.asi", f"{WIN64}/plugins/DBFZSlots", "RED/Content/Paks/~mods/DBFZSlots")
# can belong to another tool (Unverum puts its own dsound.dll here)
SHARED = (f"{WIN64}/dsound.dll", f"{WIN64}/opengl32.dll", f"{WIN64}/ue4ss")
RUNTIME = Path(__file__).resolve().parent.parent.parent / "runtime"


class Erro(Exception):
    pass


def pastas(jogo):
    d = Path(jogo) / DATA_DIR
    return d / "ready", d / "displaced", d / "active.json"


def _ler(state):
    try:
        return json.loads(state.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _remover(p):
    if p.is_dir():
        shutil.rmtree(p)
    elif p.exists():
        p.unlink()


def _mover(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    _remover(dst)
    shutil.move(str(src), str(dst))


def eh_nosso(jogo, rel):
    """A shared item already in the game is ours if it is the file we install (or our UE4SS)."""
    p = Path(jogo) / rel
    if p.is_dir():
        return (p / "Mods" / "DBFZSlots").exists()
    r = RUNTIME / Path(rel).name
    return p.is_file() and r.is_file() and p.stat().st_size == r.stat().st_size and p.read_bytes() == r.read_bytes()


def ativo(jogo):
    return pastas(jogo)[2].exists()


def desativar(jogo):
    """Our files: game -> ready. Files of other tools: displaced -> game. Safe to call any time."""
    jogo = Path(jogo)
    ready, disp, state = pastas(jogo)
    st = _ler(state)
    n = 0
    for rel in OURS + SHARED:
        g = jogo / rel
        if not g.exists():
            continue
        if rel in OURS or rel in st.get("active", []) or eh_nosso(jogo, rel):
            _mover(g, ready / rel)
            n += 1
    avisos = []
    for rel in st.get("displaced", []):
        src, g = disp / rel, jogo / rel
        if src.exists():
            if g.exists():
                avisos.append(f"{rel}: kept in {disp} (the game folder already has one)")
                continue
            _mover(src, g)
    if state.exists():
        state.unlink()
    if disp.exists() and not any(p.is_file() for p in disp.rglob("*")):
        shutil.rmtree(disp)
    return n, avisos


def ativar(jogo, exigir=True):
    """ready -> game (moving aside any file of another tool that sits where ours go)."""
    jogo = Path(jogo)
    desativar(jogo)
    ready, disp, state = pastas(jogo)
    itens = [rel for rel in OURS + SHARED if (ready / rel).exists()]
    if exigir and not any(rel in itens for rel in OURS):
        raise Erro("the mod is not installed in this folder yet: click Apply first")
    deslocados = [rel for rel in SHARED if (jogo / rel).exists()]
    state.parent.mkdir(parents=True, exist_ok=True)
    # journal first: if anything stops halfway, desativar() knows what to undo
    state.write_text(json.dumps({"active": list(SHARED), "displaced": deslocados,
                                 "since": time.strftime("%Y-%m-%d %H:%M:%S")}, indent=1), encoding="utf-8")
    for rel in deslocados:
        _mover(jogo / rel, disp / rel)
    for rel in itens:
        _mover(ready / rel, jogo / rel)
    return len(itens)


def jogo_rodando(nome=None):
    """Only reads the process list (names). nome=None: any copy of the game or EasyAntiCheat."""
    out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True,
                         creationflags=0x08000000).stdout.lower()
    if nome:
        return f'"{nome.lower()}"' in out
    return "red-win64-shipping" in out or "easyanticheat" in out


def criar_atalho(jogo):
    """Desktop shortcut "DBFZ Slots" = this installer with --launch <game>. Only in the packaged exe."""
    import sys
    if not getattr(sys, "frozen", False):
        return None
    me = Path(sys.executable)
    ps = ("$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell)"
          ".CreateShortcut((Join-Path $d 'DBFZ Slots.lnk')); $s.TargetPath=$env:DBFZ_T; "
          "$s.Arguments=$env:DBFZ_A; $s.WorkingDirectory=$env:DBFZ_W; $s.IconLocation=$env:DBFZ_T+',0'; "
          "$s.Description='DRAGON BALL FighterZ with DBFZ Slots (offline)'; $s.Save(); Join-Path $d 'DBFZ Slots.lnk'")
    import os
    env = dict(os.environ, DBFZ_T=str(me), DBFZ_A="--play", DBFZ_W=str(me.parent))
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], env=env,
                       capture_output=True, text=True, creationflags=0x08000000)
    return r.stdout.strip() if r.returncode == 0 else None


def restaurar(jogo):
    """Takes the mod out now (after a PC crash or if the launcher was closed). Not while the modded
    game is running."""
    jogo = Path(jogo)
    offline = [p.name for p in (jogo / WIN64).glob("*.exe") if "eac-nop" in p.name.lower()]
    if any(jogo_rodando(n) for n in offline):
        raise Erro("the modded game is running. Close it first.")
    return desativar(jogo)


def pasta_do_jogo(caminho):
    """Game folder (the one with RED\\) that contains this path."""
    p = Path(caminho).resolve()
    for d in [p] + list(p.parents):
        if (d / "RED" / "Content" / "Paks").is_dir():
            return d
    return None


def opcao_steam():
    """Text for Steam > Properties > Launch Options: every Steam launch goes through --steam first."""
    import sys
    me = Path(sys.executable) if getattr(sys, "frozen", False) else None
    return f'"{me}" --steam %command%' if me else None


def steam(cmd):
    """Steam launch wrapper: cleans up any mod file left in the folder, then starts the normal game
    exactly as Steam asked (cmd = %command%)."""
    if not cmd:
        raise Erro("--steam needs %command% after it (Steam > Properties > Launch Options)")
    jogo = pasta_do_jogo(Path(cmd[0]).parent)
    if jogo:
        restaurar(jogo)
    subprocess.Popen(cmd, cwd=str(Path(cmd[0]).parent))


def lancar(jogo, exe=None):
    """Turns the mod on, starts the offline exe, waits for the game to close, turns the mod off."""
    jogo = Path(jogo)
    win64 = jogo / WIN64
    if exe:
        exe = Path(exe)
    else:
        cands = sorted(p for p in win64.glob("*.exe") if "eac-nop" in p.name.lower())
        if len(cands) != 1:
            raise Erro(f"could not find a single offline exe (*eac-nop*.exe) in {win64}")
        exe = cands[0]
    if jogo_rodando():
        raise Erro("the game (or EasyAntiCheat) is already running. Close it first.")
    ativar(jogo)
    try:
        subprocess.Popen([str(exe)], cwd=str(win64)).wait()
        time.sleep(3)
        while jogo_rodando(exe.name):  # the game may restart itself once
            time.sleep(3)
    finally:
        desativar(jogo)
