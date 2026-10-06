"""
instalador_gui.py - DBFZ Slots installer window (uses the same functions as instalador.py).

Simple mode: game folder (a COPY of the game with Unverum applied) + mods folder + "Apply".
Advanced (hidden by default): offline exe, AES key, and the character list (order on the 4th
row, names, codes) before installing.
"""
import json
import os
import queue
import sys
import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import instalador as I      # noqa: E402

CONF = Path(os.environ.get("APPDATA", str(Path.home()))) / "DBFZSlots" / "installer.json"
NOTICE = ("Adds modded characters as NEW slots (4th row). OFFLINE play only. This installer does not include "
          "or create a game executable and does not disable the anti-cheat: it uses the offline exe you already "
          "have. Mods are converted on your PC from the files you downloaded (credit goes to each mod's author).")


class Output:
    """stdout/stderr -> queue -> text box (the installer functions use print)."""
    def __init__(self, q):
        self.q = q

    def write(self, s):
        self.q.put(s)

    def flush(self):
        pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DBFZ Slots - installer")
        self.geometry("900x620")
        self.minsize(760, 520)
        try:
            self._icon = tk.PhotoImage(file=str(HERE.parent / "icone.png"))
            self.iconphoto(True, self._icon)
        except tk.TclError:
            pass
        self.q = queue.Queue()
        self.ctx = None
        self.ctx_key = None
        self.busy = False
        cfg = self.load()
        self.vars = {k: tk.StringVar(value=cfg.get(k, "")) for k in ("game", "mods", "exe", "key")}
        self.adv = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Choose the game folder and the mods folder, then click Apply.")
        self.build()
        self.vars["game"].trace_add("write", lambda *a: self.hint())
        self.hint()
        sys.stdout = sys.stderr = Output(self.q)
        self.after(100, self.pump)

    # ---- remembered settings -------------------------------------------------------------------
    def load(self):
        try:
            return json.loads(CONF.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save(self):
        CONF.parent.mkdir(parents=True, exist_ok=True)
        CONF.write_text(json.dumps({k: v.get() for k, v in self.vars.items()}, indent=1), encoding="utf-8")

    # ---- layout --------------------------------------------------------------------------------
    def build(self):
        pad = {"padx": 10, "pady": 4}
        ttk.Label(self, text=NOTICE, wraplength=860, foreground="#8a4b00").pack(fill="x", **pad)

        main = ttk.Frame(self)
        main.pack(fill="x", **pad)
        for r, (label, key) in enumerate((("Game folder (your COPY of the game, with Unverum applied)", "game"),
                                          ("Folder with the character mods (.zip / .rar / mod folders)", "mods"))):
            ttk.Label(main, text=label).grid(row=r, column=0, sticky="w")
            ttk.Entry(main, textvariable=self.vars[key], width=64).grid(row=r, column=1, sticky="we", padx=6)
            ttk.Button(main, text="Browse...", command=lambda k=key: self.pick(k, "dir")).grid(row=r, column=2)
        main.columnconfigure(1, weight=1)
        self.hint_lbl = ttk.Label(self, text="", foreground="#555")
        self.hint_lbl.pack(fill="x", padx=10)

        bar = ttk.Frame(self)
        bar.pack(fill="x", **pad)
        style = ttk.Style(self)
        style.configure("Apply.TButton", font=("Segoe UI", 11, "bold"), padding=(18, 6))
        self.b_apply = ttk.Button(bar, text="Apply", style="Apply.TButton", command=self.apply)
        self.b_apply.pack(side="left")
        ttk.Label(bar, textvariable=self.status).pack(side="left", padx=10)
        ttk.Checkbutton(bar, text="Advanced", variable=self.adv, command=self.toggle).pack(side="right")

        # avancado (escondido)
        self.adv_frame = ttk.Frame(self)
        form = ttk.Frame(self.adv_frame)
        form.pack(fill="x")
        rows = [("Offline exe (empty = find *eac-nop*.exe)", "exe", "exe"),
                ("AES key (empty = the one included)", "key", "key")]
        for r, (label, key, kind) in enumerate(rows):
            ttk.Label(form, text=label).grid(row=r, column=0, sticky="w")
            ttk.Entry(form, textvariable=self.vars[key], width=60).grid(row=r, column=1, sticky="we", padx=6)
            ttk.Button(form, text="...", width=3, command=lambda k=key, t=kind: self.pick(k, t)).grid(row=r, column=2)
        form.columnconfigure(1, weight=1)
        lb = ttk.Frame(self.adv_frame)
        lb.pack(fill="x", pady=4)
        self.b_an = ttk.Button(lb, text="Analyze only (list the characters)", command=self.analyze)
        self.b_an.pack(side="left")
        ttk.Label(lb, text="  then adjust the list and click Apply").pack(side="left")
        mid = ttk.Frame(self.adv_frame)
        mid.pack(fill="both", expand=True)
        cols = ("#", "code", "name", "short name", "replaces", "recipe", "file")
        self.tree = ttk.Treeview(mid, columns=cols, show="headings", height=7)
        for c, w in zip(cols, (36, 56, 210, 130, 70, 76, 230)):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self.edit())
        side = ttk.Frame(mid)
        side.pack(side="left", fill="y", padx=4)
        for t, f in (("Move up", lambda: self.move(-1)), ("Move down", lambda: self.move(1)),
                     ("Edit...", self.edit), ("Remove", self.remove)):
            ttk.Button(side, text=t, command=f).pack(fill="x", pady=2)

        self.log = tk.Text(self, height=12, wrap="word", font=("Consolas", 9))
        self.log.pack(fill="both", expand=True, **pad)

    def toggle(self):
        if self.adv.get():
            self.adv_frame.pack(fill="x", padx=10, pady=4, before=self.log)
        else:
            self.adv_frame.pack_forget()

    def hint(self):
        g = self.vars["game"].get().strip()
        if g and I.eh_steam(g):
            self.hint_lbl.config(text="This is the Steam folder: make a copy of the game, apply Unverum to the "
                                      "copy and choose the copy here.", foreground="#b00020")
        else:
            self.hint_lbl.config(text="Tip: copy the game folder, apply Unverum to the copy, then choose the copy here.",
                                 foreground="#555")

    def pick(self, key, kind):
        if kind == "dir":
            v = filedialog.askdirectory()
        elif kind == "exe":
            v = filedialog.askopenfilename(filetypes=[("exe", "*.exe")])
        else:
            v = filedialog.askopenfilename(filetypes=[("text", "*.txt"), ("all files", "*.*")])
        if v:
            self.vars[key].set(v)

    def pump(self):
        try:
            while True:
                self.log.insert("end", self.q.get_nowait())
                self.log.see("end")
        except queue.Empty:
            pass
        self.after(100, self.pump)

    # ---- character list ------------------------------------------------------------------------
    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for i, e in enumerate(self.ctx["extras"], 1):
            n = e["nomes"]["en"]
            self.tree.insert("", "end", iid=str(i - 1), values=(i, e["codigo"], n[0], n[1], e["base"], e["receita"], e["origem"]))

    def sel(self):
        s = self.tree.selection()
        return int(s[0]) if s else None

    def move(self, d):
        i = self.sel()
        if i is None or not self.ctx:
            return
        j = i + d
        ex = self.ctx["extras"]
        if 0 <= j < len(ex):
            ex[i], ex[j] = ex[j], ex[i]
            self.refresh()
            self.tree.selection_set(str(j))

    def remove(self):
        i = self.sel()
        if i is not None and self.ctx:
            del self.ctx["extras"][i]
            self.refresh()

    def edit(self):
        i = self.sel()
        if i is None or not self.ctx:
            return
        e = self.ctx["extras"][i]
        code = simpledialog.askstring("Code", "3-letter code (A-Z, not used by the game):", initialvalue=e["codigo"], parent=self)
        if code is None:
            return
        code = code.strip().upper()
        import detectar_mod as D
        others = {x["codigo"] for k, x in enumerate(self.ctx["extras"]) if k != i}
        if len(code) != 3 or not code.isalpha() or code in D.GAME_CODES or code in others:
            messagebox.showerror("Code", f"{code}: invalid, used by the game or repeated")
            return
        name = simpledialog.askstring("Name", "Full name:", initialvalue=e["nomes"]["en"][0], parent=self)
        short = simpledialog.askstring("Short name", "Short name (VS screen, HUD):", initialvalue=e["nomes"]["en"][1], parent=self)
        e["codigo"] = code
        if name:
            e["nomes"]["en"][0] = name.strip()
        if short:
            e["nomes"]["en"][1] = short.strip()
        self.refresh()

    # ---- actions -------------------------------------------------------------------------------
    def values(self):
        return {k: x.get().strip() for k, x in self.vars.items()}

    def run_bg(self, fn, done, msg):
        if self.busy:
            return
        self.busy = True
        self.status.set(msg)
        self.b_apply.config(state="disabled")
        self.b_an.config(state="disabled")

        def work():
            try:
                r = fn()
                self.after(0, lambda: self.finish(done, r, None))
            except (I.Erro, SystemExit) as ex:
                self.after(0, lambda: self.finish(done, None, str(ex).strip()))
            except Exception:
                tb = traceback.format_exc()
                print(tb)
                self.after(0, lambda: self.finish(done, None, tb.strip().splitlines()[-1]))
        threading.Thread(target=work, daemon=True).start()

    def finish(self, done, r, err):
        self.busy = False
        self.b_apply.config(state="normal")
        self.b_an.config(state="normal")
        done(r, err)

    def ready(self, v):
        if not v["game"] or not v["mods"]:
            messagebox.showwarning("Missing information", "Choose the game folder and the mods folder.")
            return False
        self.save()
        self.log.delete("1.0", "end")
        return True

    def analyze(self):
        v = self.values()
        if not self.ready(v):
            return

        def done(ctx, err):
            if err:
                self.status.set("Could not continue.")
                messagebox.showerror("Could not continue", err)
                return
            self.ctx, self.ctx_key = ctx, (v["game"], v["mods"], v["exe"], v["key"])
            self.refresh()
            self.status.set(f"{len(ctx['extras'])} characters found. Adjust the list if you want, then click Apply.")
            if ctx["avisos"]:
                messagebox.showwarning("Warnings", "\n".join(ctx["avisos"]))
        self.run_bg(lambda: I.analisar(v["game"], v["mods"], v["exe"] or None, v["key"] or None,
                                       simular=True), done, "Analyzing...")

    def apply(self):
        v = self.values()
        if not self.ready(v):
            return
        key = (v["game"], v["mods"], v["exe"], v["key"])
        edited = self.ctx if self.ctx and self.ctx_key == key else None

        def work():
            ctx = edited or I.analisar(v["game"], v["mods"], v["exe"] or None, v["key"] or None,
                                       simular=False)
            I.instalar_tudo(ctx)
            return ctx

        def done(ctx, err):
            if err:
                self.status.set("Installation failed.")
                messagebox.showerror("Installation failed", err)
                return
            self.ctx = None
            self.status.set(f"Done: {len(ctx['extras'])} characters installed.")
            extra = "\n\nWarnings:\n" + "\n".join(ctx["avisos"]) if ctx["avisos"] else ""
            messagebox.showinfo("Done", f"{len(ctx['extras'])} characters installed in:\n{ctx['jogo']}\n\n"
                                        f"Start the game with {ctx['exe'].name} (in RED\\Binaries\\Win64).{extra}")
        self.run_bg(work, done, "Installing... this can take several minutes.")


if __name__ == "__main__":
    App().mainloop()
