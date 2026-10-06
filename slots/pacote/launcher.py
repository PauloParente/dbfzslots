"""Entry point of the packaged installer (PyInstaller): puts the tools on the path and opens the window.

  (no arguments)     opens the window
  --cli ...          command line (same options as instalador.py)
  --selftest         opens and closes the window by itself (checks the package); result in the log
The exe is a window app (no console): in --cli mode output goes to the calling console or, if
there is none, to %TEMP%\\DBFZSlots_installer.log.
"""
import os
import runpy
import sys
from pathlib import Path

BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent.parent))
for p in ("tools/re", "tools", "slots/tools"):
    sys.path.insert(0, str(BASE / p))
LOG = Path(os.environ.get("TEMP", ".")) / "DBFZSlots_installer.log"


def console_ou_log():
    if sys.stdout is not None:
        return
    try:
        import ctypes
        if ctypes.windll.kernel32.AttachConsole(-1):
            sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1)
            sys.stderr = sys.stdout
            return
    except Exception:
        pass
    sys.stdout = sys.stderr = open(LOG, "w", encoding="utf-8", buffering=1)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--cli"]:
        console_ou_log()
        sys.argv = [str(BASE / "slots/tools/instalador.py")] + args[1:]
        runpy.run_path(sys.argv[0], run_name="__main__")
    elif args[:1] in (["--selftest"], ["--autoteste"]):
        sys.stdout = sys.stderr = open(LOG, "w", encoding="utf-8", buffering=1)
        g = runpy.run_path(str(BASE / "slots/tools/instalador_gui.py"), run_name="autoteste")
        app = g["App"]()
        import instalador, detectar_mod, assinaturas, instalar, build_char, icon_fix   # noqa: F401
        app.after(800, app.destroy)
        app.mainloop()
        sys.__stdout__ and None
        open(LOG, "a", encoding="utf-8").write("\nSELFTEST OK: window opened and closed; modules imported\n")
    else:
        runpy.run_path(str(BASE / "slots/tools/instalador_gui.py"), run_name="__main__")
