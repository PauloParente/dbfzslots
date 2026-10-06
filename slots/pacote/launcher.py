"""Entry point of the packaged installer (PyInstaller): puts the tools on the path and opens the window.

  (no arguments)     opens the window
  --launch GAME      starts the game with the mod (desktop shortcut): mod in, game, mod out
  --restore GAME     takes the mod out now (after a crash): Steam starts the normal game
  --steam %command%  Steam launch option: cleans up leftovers, then starts the normal game
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
# LGPL libraries (pystray) ship as plain files next to the exe, so they can be replaced
LGPL = Path(sys.executable).parent / "lgpl"
if getattr(sys, "frozen", False) and LGPL.is_dir():
    sys.path.insert(0, str(LGPL))


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
    modo = {"--launch": "lancar", "--restore": "restaurar", "--steam": "steam"}.get(args[0] if args else "")
    if modo and (len(args) >= 2 or modo == "steam"):
        sys.stdout = sys.stderr = open(Path(os.environ.get("TEMP", ".")) / "DBFZSlots_launch.log", "w",
                                       encoding="utf-8", buffering=1)
        import ativacao
        msg = None
        try:
            if modo == "lancar":
                ativacao.lancar(args[1])
            elif modo == "restaurar":
                ativacao.restaurar(args[1])
                msg = "The mod is off: the game folder is back to normal (Steam starts the normal game)."
            else:
                ativacao.steam(args[1:])
        except Exception as e:
            import traceback
            traceback.print_exc()
            msg = f"ERROR: {e}"
        if msg:
            import tkinter as tk
            from tkinter import messagebox
            r = tk.Tk()
            r.withdraw()
            (messagebox.showerror if msg.startswith("ERROR") else messagebox.showinfo)("DBFZ Slots", msg)
            r.destroy()
    elif args[:1] == ["--cli"]:
        console_ou_log()
        sys.argv = [str(BASE / "slots/tools/instalador.py")] + args[1:]
        runpy.run_path(sys.argv[0], run_name="__main__")
    elif args[:1] in (["--selftest"], ["--autoteste"]):
        sys.stdout = sys.stderr = open(LOG, "w", encoding="utf-8", buffering=1)
        g = runpy.run_path(str(BASE / "slots/tools/instalador_gui.py"), run_name="autoteste")
        app = g["App"](teste=True)
        import instalador, ativacao, detectar_mod, assinaturas, instalar, build_char, icon_fix   # noqa: F401
        import pystray, PIL.ImageTk   # noqa: F401,E401
        app.after(300, app.to_tray)          # tray icon (pystray from lgpl\) on and off again
        tray = {}
        app.after(900, lambda: tray.update(ok=app.tray is not None))
        app.after(1200, app.from_tray)
        app.after(1600, app.destroy)
        app.mainloop()
        ok = instalador.RUNTIME.is_dir() and ativacao.RUNTIME.is_dir() and instalador.DB.exists() and tray.get("ok")
        open(LOG, "a", encoding="utf-8").write(f"\ntray icon: {tray.get('ok')} (pystray from {pystray.__file__})")
        open(LOG, "a", encoding="utf-8").write(
            f"\nruntime: {instalador.RUNTIME} ({instalador.RUNTIME.is_dir()}), {ativacao.RUNTIME} "
            f"({ativacao.RUNTIME.is_dir()}); db {instalador.DB.exists()}\n"
            + ("SELFTEST OK: window opened and closed; modules imported\n" if ok else "SELFTEST FAILED: paths\n"))
    else:
        runpy.run_path(str(BASE / "slots/tools/instalador_gui.py"), run_name="__main__")
