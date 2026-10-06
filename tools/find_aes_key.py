"""
find_aes_key.py - Descobre a chave AES dos .pak do DBFZ.

O executavel e protegido, entao a chave nao aparece no arquivo em disco.
Este script le a memoria do jogo EM EXECUCAO e testa cada candidato tentando
decifrar o indice de um .pak: a chave certa produz "../../../" no inicio.

Uso:
    1. Abra a copia do jogo (pode ficar na tela de titulo).
    2. python find_aes_key.py            (salva em tools\\aes_key.txt)
    python find_aes_key.py --static      (so procura nos .exe em disco)
"""
import argparse
import ctypes
import re
import struct
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path

from aes_win import AesEcb

TOOLS_DIR = Path(__file__).resolve().parent
GAME = TOOLS_DIR.parent / "game"
WIN64 = GAME / "RED" / "Binaries" / "Win64"
PAK = GAME / "RED" / "Content" / "Paks" / "pakchunk1-WindowsNoEditor.pak"
KEY_FILE = TOOLS_DIR / "aes_key.txt"
ASCII_KEY = re.compile(rb"(?<![\x21-\x7e])[\x21-\x7e]{32}(?![\x21-\x7e])")


def first_index_block(pak=PAK):
    size = pak.stat().st_size
    with open(pak, "rb") as f:
        f.seek(size - 44)
        off, = struct.unpack_from("<q", f.read(44), 8)
        f.seek(off)
        return f.read(32)


def looks_valid(plain):
    n, = struct.unpack_from("<i", plain, 0)
    return 0 < n < 512 and plain[4:7] == b"../"


class Tester:
    def __init__(self):
        self.block = first_index_block()
        self.seen = set()
        self.tested = 0

    def __call__(self, key):
        if key in self.seen:
            return False
        self.seen.add(key)
        self.tested += 1
        with AesEcb(key) as aes:
            return looks_valid(aes.decrypt(self.block))


def scan_buffer(buf, test, raw_windows):
    for m in ASCII_KEY.finditer(buf):
        if test(m.group()):
            return m.group()
    if raw_windows:
        mv = memoryview(buf)
        for off in range(0, len(buf) - 31, 8):
            w = bytes(mv[off:off + 32])
            # chaves sao aleatorias: descarta janelas com poucos bytes distintos
            if len(set(w)) >= 24 and test(w):
                return w
    return None


# --------------------------------------------------------------------------- #
# Leitura de memoria de processo (Windows)
# --------------------------------------------------------------------------- #
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)
PROCESS_QUERY_INFORMATION, PROCESS_VM_READ = 0x0400, 0x0010
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
MEM_COMMIT, MEM_IMAGE, PAGE_GUARD, PAGE_NOACCESS = 0x1000, 0x1000000, 0x100, 0x01


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", wintypes.DWORD), ("PartitionId", wintypes.WORD),
                ("RegionSize", ctypes.c_size_t), ("State", wintypes.DWORD),
                ("Protect", wintypes.DWORD), ("Type", wintypes.DWORD)]


k32.OpenProcess.restype = wintypes.HANDLE
k32.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(MBI), ctypes.c_size_t]
k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]


def list_processes():
    """(pid, caminho completo) de todos os processos, sem pedir acesso de leitura."""
    arr = (wintypes.DWORD * 4096)()
    needed = wintypes.DWORD()
    psapi.EnumProcesses(arr, ctypes.sizeof(arr), ctypes.byref(needed))
    for pid in arr[:needed.value // 4]:
        h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            continue
        buf = ctypes.create_unicode_buffer(1024)
        n = wintypes.DWORD(1024)
        ok = k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n))
        k32.CloseHandle(h)
        if ok:
            yield pid, Path(buf.value)


def find_game_pid():
    """So aceita o jogo rodando a partir da COPIA e sem EasyAntiCheat ativo."""
    procs = list(list_processes())
    # o servico do EAC roda como SYSTEM e nao revela o caminho; checa pelo nome via tasklist
    tasks = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True,
                           text=True, errors="replace").stdout.lower()
    if "easyanticheat" in tasks:
        print("EasyAntiCheat esta rodando. Feche o jogo da Steam: ler a memoria de um")
        print("processo protegido pelo anti-cheat pode gerar punicao na conta.")
        return None, None
    copy_root = GAME.resolve()
    for pid, path in procs:
        if path.name.lower().startswith("red-win64-shipping"):
            if copy_root not in path.resolve().parents:
                print(f"O jogo aberto NAO e a copia: {path}")
                print(f"Feche-o e abra {WIN64 / 'RED-Win64-Shipping.exe'}")
                return None, None
            return pid, path.name
    print("Jogo nao esta rodando. Abra a copia (RED-Win64-Shipping.exe) e rode de novo.")
    return None, None


def regions(h):
    addr, mbi = 0, MBI()
    while k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
        if (mbi.State == MEM_COMMIT and not mbi.Protect & (PAGE_GUARD | PAGE_NOACCESS)):
            yield mbi.BaseAddress, mbi.RegionSize, mbi.Type
        addr = (mbi.BaseAddress or 0) + mbi.RegionSize
        if addr >= 0x7FFFFFFFFFFF:
            break


def read(h, addr, size):
    buf = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t()
    k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size, ctypes.byref(got))
    return buf.raw[:got.value]


def scan_process(test):
    pid, name = find_game_pid()
    if not pid:
        return None
    print(f"Lendo memoria de {name} (pid {pid})...")
    h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        print(f"Nao foi possivel abrir o processo (erro {ctypes.get_last_error()}).")
        return None
    try:
        regs = list(regions(h))
        # passo 1: texto ASCII em toda a memoria; passo 2: bytes crus so na imagem do exe
        for raw_windows, label in ((False, "texto"), (True, "bytes crus (imagem do exe)")):
            print(f"  passo: {label}")
            for base, size, typ in regs:
                if raw_windows and typ != MEM_IMAGE:
                    continue
                for off in range(0, size, 64 << 20):
                    buf = read(h, base + off, min(64 << 20, size - off) + (32 if raw_windows else 0))
                    if buf and (key := scan_buffer(buf, test, raw_windows)):
                        return key
    finally:
        k32.CloseHandle(h)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--static", action="store_true", help="procura so nos .exe em disco")
    args = ap.parse_args()
    test = Tester()
    key = None
    if args.static:
        for exe in sorted(WIN64.glob("RED-Win64-Shipping*.exe")):
            print(f"Procurando em {exe.name}...")
            if key := scan_buffer(exe.read_bytes(), test, raw_windows=False):
                break
    else:
        key = scan_process(test)
    print(f"{test.tested} candidatos testados.")
    if not key:
        print("Chave nao encontrada.")
        return 1
    hexkey = "0x" + key.hex().upper()
    print(f"CHAVE ENCONTRADA: {hexkey}")
    KEY_FILE.write_text(hexkey + "\n")
    print(f"Salva em {KEY_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
