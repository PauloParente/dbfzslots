"""
exportar_perfil.py - Grava um perfil compilado do plugin em texto (formato do perfil.txt).

Uso: python exportar_perfil.py <indice> <saida.txt>     (0 = eac-nop, 1 = shipping)
Serve de referencia para o gerar_perfil.py e para testes.
"""
import ctypes
import sys
from pathlib import Path

DLL = Path(__file__).resolve().parent.parent / "out" / "dbfzslots.dll"


def export(index, out):
    dll = ctypes.CDLL(str(DLL))
    dll.dbfz_profile_export.argtypes = [ctypes.c_int, ctypes.c_wchar_p]
    if not dll.dbfz_profile_export(index, str(Path(out).resolve())):
        raise SystemExit(f"perfil {index} nao existe")


if __name__ == "__main__":
    export(int(sys.argv[1]), sys.argv[2])
    print(f"perfil {sys.argv[1]} -> {sys.argv[2]}")
