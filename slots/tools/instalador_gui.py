"""
instalador_gui.py - DBFZ Slots window (uses the same functions as instalador.py).

One button for the user: PLAY. The window finds the game (Steam libraries) and Unverum's
Dragon Ball FighterZ mods folder by itself, lists the character mods (tick / drag to reorder /
double-click to rename) and, on Play, applies only when something changed, starts the game with
the mod and hides in the tray until the game closes (then the mod is taken out again).
"""
import ctypes
import json
import os
import queue
import re
import sys
import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import instalador as I      # noqa: E402
import ativacao as A        # noqa: E402

CONF = Path(os.environ.get("APPDATA", str(Path.home()))) / "DBFZSlots" / "installer.json"
README = HERE.parent.parent / "README.txt"
if not README.exists():
    README = HERE.parent / "pacote" / "README.txt"

# ---- texts (English / Portuguese, from the Windows language) ----------------------------------
try:
    PT = (ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF) == 0x16
except Exception:
    PT = False
TXT = {
    "title": ("DBFZ Slots", "DBFZ Slots"),
    "notice": ("Modded characters as NEW slots (4th row). Offline only: the mod is only active while you play "
               "from here; Steam always starts the normal game.",
               "Personagens de mods em slots NOVOS (4ª fileira). Somente offline: o mod só fica ativo enquanto "
               "você joga por aqui; a Steam sempre abre o jogo normal."),
    "game": ("Game", "Jogo"), "mods": ("Mods", "Mods"), "exe": ("Offline exe", "Exe offline"),
    "state": ("Mod", "Mod"),
    "change": ("Change...", "Trocar..."), "open": ("Open folder", "Abrir pasta"),
    "fix": ("How to fix", "Como resolver"), "restore": ("Restore normal game", "Restaurar jogo normal"),
    "game_nf": ("not found: choose the DRAGON BALL FighterZ folder", "não encontrado: escolha a pasta do DRAGON BALL FighterZ"),
    "mods_unv": ("{p}  (Unverum)", "{p}  (Unverum)"),
    "mods_nf": ("Unverum mods folder not found: choose your mods folder",
                "pasta de mods do Unverum não encontrada: escolha a sua pasta de mods"),
    "exe_ok": ("{n}", "{n}"),
    "exe_nf": ("not found: apply Unverum to the game first (it creates the offline exe)",
               "não encontrado: aplique o Unverum no jogo primeiro (ele cria o exe offline)"),
    "off": ("off: Steam starts the normal game", "desligado: a Steam abre o jogo normal"),
    "left": ("files left from a crash: click Restore before playing online",
             "arquivos sobraram de uma queda: clique em Restaurar antes de jogar online"),
    "on": ("ON: the game is running with the mod", "LIGADO: o jogo está rodando com o mod"),
    "chars": ("Characters on the 4th row: {n}/{m} selected", "Personagens na 4ª fileira: {n}/{m} selecionados"),
    "hint_list": ("tick to use · drag to reorder · double-click to rename",
                  "marque para usar · arraste para reordenar · clique duplo para renomear"),
    "refresh": ("Refresh", "Atualizar"),
    "src_unv": ("installed by Unverum: {n}", "instalado pelo Unverum: {n}"),
    "col_name": ("Character", "Personagem"), "col_base": ("Based on", "Baseado em"), "col_src": ("Mod", "Mod"),
    "play": ("PLAY", "JOGAR"),
    "details": ("Details", "Detalhes"), "copy_log": ("Copy log", "Copiar log"),
    "scanning": ("Looking for character mods...", "Procurando mods de personagem..."),
    "ready": ("Ready: click PLAY.", "Pronto: clique em JOGAR."),
    "pending": ("Ready: PLAY will apply your changes first (a few minutes the first time).",
                "Pronto: JOGAR vai aplicar suas mudanças antes (alguns minutos na primeira vez)."),
    "nochars": ("No character mods found. Install some in Unverum (or choose another mods folder).",
                "Nenhum mod de personagem encontrado. Instale alguns no Unverum (ou escolha outra pasta de mods)."),
    "applying": ("Applying: {t}", "Aplicando: {t}"),
    "building": ("building {c}", "montando {c}"),
    "running": ("Playing with the mod. The window comes back when the game closes.",
                "Jogando com o mod. A janela volta quando o jogo fechar."),
    "closed": ("Game closed: the mod is off again (Steam starts the normal game).",
               "Jogo fechado: o mod foi desligado (a Steam abre o jogo normal)."),
    "restored": ("Restored: Steam starts the normal game. Your mod comes back with PLAY.",
                 "Restaurado: a Steam abre o jogo normal. O mod volta com JOGAR."),
    "copied": ("Log copied: paste it in your message.", "Log copiado: cole na sua mensagem."),
    "max": ("The 4th row has {m} slots: untick another character first.",
            "A 4ª fileira tem {m} slots: desmarque outro personagem antes."),
    "select_one": ("Tick at least one character.", "Marque pelo menos um personagem."),
    "err": ("Something went wrong", "Algo deu errado"),
    "tray": ("DBFZ Slots - mod on (game running)", "DBFZ Slots - mod ligado (jogo rodando)"),
    "show": ("Show window", "Mostrar janela"),
    "busy_close": ("The game is running with the mod: the window stays in the tray and turns the mod off when "
                   "the game closes.", "O jogo está rodando com o mod: a janela fica na bandeja e desliga o mod "
                   "quando o jogo fechar."),
    "edit_name": ("Full name:", "Nome completo:"), "edit_short": ("Short name (VS screen, HUD):", "Nome curto (tela VS, HUD):"),
    "edit_code": ("3-letter code (A-Z, not used by the game):", "Código de 3 letras (A-Z, não usado pelo jogo):"),
    "bad_code": ("{c}: invalid, used by the game or repeated", "{c}: inválido, usado pelo jogo ou repetido"),
    "m_edit": ("Rename...", "Renomear..."), "m_up": ("Move up", "Mover para cima"), "m_down": ("Move down", "Mover para baixo"),
    "fix_exe": ("Open Unverum, point it to your DRAGON BALL FighterZ folder and apply your mods once: it creates "
                "RED\\Binaries\\Win64\\RED-Win64-Shipping-eac-nop-loaded.exe. Then click Refresh here.",
                "Abra o Unverum, aponte para a pasta do DRAGON BALL FighterZ e aplique seus mods uma vez: ele cria "
                "RED\\Binaries\\Win64\\RED-Win64-Shipping-eac-nop-loaded.exe. Depois clique em Atualizar aqui."),
    "fix_compat": ("Your game version changed something the plugin needs. Nothing was installed. Click 'Copy log' "
                   "and send it to the author.", "A versão do jogo mudou algo que o plugin precisa. Nada foi "
                   "instalado. Clique em 'Copiar log' e envie ao autor."),
    "fix_running": ("Close the game (and Steam's version of it) and try again.",
                    "Feche o jogo (inclusive o da Steam) e tente de novo."),
    "fix_generic": ("Click 'Copy log' and send it to the author.", "Clique em 'Copiar log' e envie ao autor."),
}


def T(k, **kw):
    return TXT[k][1 if PT else 0].format(**kw)


def curto(p, n=78):
    """Long path -> C:\...\last\folders (fits the row)."""
    p = str(p)
    if len(p) <= n:
        return p
    parts = Path(p).parts
    tail = ""
    for x in reversed(parts[1:]):
        if len(parts[0]) + 4 + len(x) + len(tail) + 1 > n:
            break
        tail = x + ("\\" + tail if tail else "")
    return parts[0] + "...\\" + tail


def dica(err):
    e = err.lower()
    if "offline exe" in e or "eac-nop" in e:
        return T("fix_exe")
    if "not compatible" in e:
        return T("fix_compat")
    if "running" in e:
        return T("fix_running")
    return T("fix_generic")


class Output:
    """stdout/stderr -> queue -> Details box (the installer functions use print)."""
    def __init__(self, q):
        self.q = q

    def write(self, s):
        self.q.put(s)

    def flush(self):
        pass


class App(tk.Tk):
    def __init__(self, autoplay=False, teste=False):
        super().__init__()
        self.title(T("title"))
        self.geometry("880x700")
        self.minsize(720, 520)
        try:
            self._icon = tk.PhotoImage(file=str(HERE.parent / "icone.png"))
            self.iconphoto(True, self._icon)
        except tk.TclError:
            self._icon = None
        self.q = queue.Queue()
        self.cfg = self.load()
        self.ctx = None            # result of the last scan
        self.scan_key = None
        self.busy = False
        self.playing = False
        self.autoplay = autoplay
        self.thumbs = {}
        self.tray = None
        self.prog_total = self.prog_n = 0
        self.game = tk.StringVar(value=self.cfg.get("game") or str(I.achar_jogo() or ""))
        self.mods = tk.StringVar(value=self.cfg.get("mods") or str(I.achar_mods_unverum() or ""))
        self.status = tk.StringVar()
        self.build()
        sys.stdout = sys.stderr = Output(self.q)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(100, self.pump)
        if not teste:
            self.after(200, self.scan)

    # ---- settings ------------------------------------------------------------------------------
    def load(self):
        try:
            return json.loads(CONF.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save(self):
        self.cfg["game"], self.cfg["mods"] = self.game.get().strip(), self.mods.get().strip()
        CONF.parent.mkdir(parents=True, exist_ok=True)
        CONF.write_text(json.dumps(self.cfg, indent=1, ensure_ascii=False), encoding="utf-8")

    # ---- layout --------------------------------------------------------------------------------
    def build(self):
        st = ttk.Style(self)
        st.configure("Play.TButton", font=("Segoe UI", 14, "bold"), padding=(40, 10))
        st.configure("Treeview", rowheight=40)
        st.configure("Head.TLabel", font=("Segoe UI", 10, "bold"))
        pad = {"padx": 12, "pady": 3}
        ttk.Label(self, text=T("notice"), wraplength=820, foreground="#8a4b00").pack(fill="x", **pad)

        box = ttk.Frame(self)
        box.pack(fill="x", **pad)
        self.rows = {}
        for r, k in enumerate(("game", "mods", "exe", "state")):
            mark = ttk.Label(box, width=2, font=("Segoe UI", 11, "bold"))
            mark.grid(row=r, column=0, sticky="w")
            ttk.Label(box, text=T(k) + ":", style="Head.TLabel").grid(row=r, column=1, sticky="w", padx=(0, 6))
            txt = ttk.Label(box, text="", foreground="#333")
            txt.grid(row=r, column=2, sticky="we")
            acts = ttk.Frame(box)
            acts.grid(row=r, column=3, sticky="e")
            self.rows[k] = (mark, txt, acts)
        box.columnconfigure(2, weight=1)
        ttk.Button(self.rows["game"][2], text=T("change"), command=lambda: self.pick(self.game)).pack(side="left")
        ttk.Button(self.rows["mods"][2], text=T("change"), command=lambda: self.pick(self.mods)).pack(side="left")
        ttk.Button(self.rows["mods"][2], text=T("open"), command=self.open_mods).pack(side="left", padx=(4, 0))
        self.b_fix = ttk.Button(self.rows["exe"][2], text=T("fix"), command=lambda: self.show_error(T("exe_nf"), T("fix_exe")))
        self.b_restore = ttk.Button(self.rows["state"][2], text=T("restore"), command=self.restore)

        head = ttk.Frame(self)
        head.pack(fill="x", padx=12, pady=(10, 0))
        self.chars_lbl = ttk.Label(head, text="", style="Head.TLabel")
        self.chars_lbl.pack(side="left")
        ttk.Label(head, text="   " + T("hint_list"), foreground="#777").pack(side="left")
        self.b_refresh = ttk.Button(head, text=T("refresh"), command=self.scan)
        self.b_refresh.pack(side="right")

        mid = ttk.Frame(self)
        mid.pack(fill="both", expand=True, padx=12, pady=4)
        self.tree = ttk.Treeview(mid, columns=("on", "name", "base", "src"), show="tree headings", selectmode="browse")
        self.tree.column("#0", width=52, stretch=False)
        for c, w, t in (("on", 34, ""), ("name", 250, T("col_name")), ("base", 90, T("col_base")), ("src", 300, T("col_src"))):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="center" if c == "on" else "w", stretch=c in ("name", "src"))
        sb = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.tree.bind("<ButtonPress-1>", self.on_press)
        self.tree.bind("<B1-Motion>", self.on_drag)
        self.tree.bind("<ButtonRelease-1>", self.on_release)
        self.tree.bind("<Double-1>", lambda e: self.edit())
        self.tree.bind("<Button-3>", self.on_menu)
        self.tree.bind("<space>", lambda e: self.toggle(self.tree.focus()))
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label=T("m_edit"), command=self.edit)
        self.menu.add_command(label=T("m_up"), command=lambda: self.move(-1))
        self.menu.add_command(label=T("m_down"), command=lambda: self.move(1))

        # footer packed BEFORE the list: when the window is small, the list shrinks, not the Play button
        foot = ttk.Frame(self)
        foot.pack(side="bottom", fill="x", before=mid)
        bottom = ttk.Frame(foot)
        bottom.pack(fill="x", padx=12, pady=(4, 2))
        self.b_play = ttk.Button(bottom, text="▶  " + T("play"), style="Play.TButton", command=self.play)
        self.b_play.pack(side="right")
        left = ttk.Frame(bottom)
        left.pack(side="left", fill="x", expand=True, padx=(0, 12))
        ttk.Label(left, textvariable=self.status, wraplength=520).pack(fill="x")
        self.prog = ttk.Progressbar(left, mode="determinate")
        self.prog.pack(fill="x", pady=(4, 0))

        dl = ttk.Frame(foot)
        dl.pack(fill="x", padx=12, pady=(0, 6))
        self.det_open = False
        self.b_det = ttk.Button(dl, text="▸ " + T("details"), command=self.toggle_details)
        self.b_det.pack(side="left")
        ttk.Button(dl, text=T("copy_log"), command=self.copy_log).pack(side="left", padx=6)
        self.log = tk.Text(foot, height=10, wrap="word", font=("Consolas", 9))

    def toggle_details(self):
        self.det_open = not self.det_open
        if self.det_open:
            self.log.pack(fill="both", expand=False, padx=12, pady=(2, 8))
        else:
            self.log.pack_forget()
        self.b_det.config(text=("▾ " if self.det_open else "▸ ") + T("details"))

    def set_row(self, k, ok, text):
        mark, txt, _ = self.rows[k]
        mark.config(text={True: "✔", False: "✖", None: "⚠"}[ok],
                    foreground={True: "#1a7f37", False: "#b00020", None: "#b26a00"}[ok])
        txt.config(text=text)

    # ---- status rows ---------------------------------------------------------------------------
    def update_rows(self, err=None):
        g, m = self.game.get().strip(), self.mods.get().strip()
        jogo = Path(g) if g and (Path(g) / "RED" / "Content" / "Paks").is_dir() else None
        self.set_row("game", bool(jogo), curto(g) if jogo else T("game_nf"))
        unv = I.achar_mods_unverum()
        if m and Path(m).is_dir():
            self.set_row("mods", True, T("mods_unv", p=curto(m, 66)) if unv and Path(m) == unv else curto(m))
        else:
            self.set_row("mods", False, T("mods_nf"))
        exe = None
        if jogo:
            c = [p for p in (jogo / A.WIN64).glob("*.exe") if "eac-nop" in p.name.lower()]
            exe = c[0] if len(c) == 1 else None
        self.set_row("exe", bool(exe), T("exe_ok", n=exe.name) if exe else T("exe_nf"))
        if exe:
            self.b_fix.pack_forget()
        else:
            self.b_fix.pack(side="left")
        self.b_restore.pack_forget()
        if self.playing:
            self.set_row("state", None, T("on"))
        elif jogo and self.sobras(jogo):
            self.set_row("state", None, T("left"))
            self.b_restore.pack(side="left")
        else:
            self.set_row("state", True, T("off"))

    def sobras(self, jogo):
        return A.ativo(jogo) or any((jogo / r).exists() for r in A.OURS)

    # ---- scan ----------------------------------------------------------------------------------
    def listing(self):
        """Cheap view of the mods folder + Unverum's ~mods (names, sizes, dates): if it changes, scan again."""
        out = []
        for d in (self.mods.get().strip(), str(Path(self.game.get().strip()) / "RED/Content/Paks/~mods")):
            try:
                for p in sorted(Path(d).iterdir()):
                    st = p.stat()
                    out.append((p.name, st.st_size, st.st_mtime_ns))
            except OSError:
                pass
        return (self.game.get().strip(), self.mods.get().strip(), tuple(out))

    def scan(self, then=None):
        if self.busy:
            return
        self.save()
        self.update_rows()
        g = self.game.get().strip()
        if not g:
            self.status.set(T("game_nf"))
            return
        key = self.listing()
        self.prog.config(mode="indeterminate")
        self.prog.start(12)

        def done(ctx, err):
            self.prog.stop()
            self.prog.config(mode="determinate", value=0)
            if err:
                self.ctx = None
                self.fill()
                self.update_rows()
                self.status.set(err.splitlines()[0][:200])
                if "offline exe" not in err.lower():
                    self.show_error(err, dica(err))
                return
            self.ctx, self.scan_key = ctx, key
            self.fill()
            self.load_thumbs()
            self.update_rows()
            if then:
                then()
        self.run_bg(lambda: I.analisar(g, self.mods.get().strip() or None, simular=True, checar_rodando=False),
                    done, T("scanning"))

    # ---- character list (with the user's choices) -----------------------------------------------
    def ordered(self):
        """All found characters in the user's order, with their names/codes; and the ticked ones."""
        if not self.ctx:
            return [], []
        ex = self.ctx["extras"]
        order = self.cfg.setdefault("order", [])
        off = set(self.cfg.setdefault("off", []))
        names, codes = self.cfg.setdefault("names", {}), self.cfg.setdefault("codes", {})
        for e in ex:
            if e["id"] not in order:
                order.append(e["id"])
                if len([x for x in ex if x["id"] in order and x["id"] not in off]) > I.MAX_EXTRAS:
                    off.add(e["id"])
            e.setdefault("_orig", (e["codigo"], list(e["nomes"]["en"])))
            if e["id"] in names:
                e["nomes"]["en"] = list(names[e["id"]])
        self.cfg["off"] = sorted(off)
        allx = sorted(ex, key=lambda e: order.index(e["id"]))
        used = set()
        for e in allx:                         # codes: user's choice if still free
            want = codes.get(e["id"], e["_orig"][0])
            e["codigo"] = want if want not in used else e["_orig"][0]
            used.add(e["codigo"])
        on = [e for e in allx if e["id"] not in off]
        return allx, on

    def fill(self):
        self.tree.delete(*self.tree.get_children())
        allx, on = self.ordered()
        for e in allx:
            ticked = e["id"] not in self.cfg["off"]
            img = self.thumbs.get(e["codigo"])
            self.tree.insert("", "end", iid=e["id"], image=img if img else "",
                             values=("☑" if ticked else "☐", e["nomes"]["en"][0],
                                     e["base"], T("src_unv", n=e["origem"][14:]) if e["origem"].startswith("from Unverum: ")
                                     else e["origem"]))
        self.chars_lbl.config(text=T("chars", n=len(on), m=I.MAX_EXTRAS))
        if not self.ctx:
            return
        if not allx:
            self.status.set(T("nochars"))
            return
        sel = dict(self.ctx, extras=on)
        try:
            self.status.set(T("pending") if on and I.precisa_aplicar(sel) else T("ready"))
        except Exception:
            self.status.set(T("pending"))
        if self.autoplay:
            self.autoplay = False
            self.after(300, self.play)

    def toggle(self, iid):
        if not iid:
            return
        off = set(self.cfg["off"])
        if iid in off:
            if len(self.ordered()[1]) >= I.MAX_EXTRAS:
                messagebox.showinfo(T("title"), T("max", m=I.MAX_EXTRAS))
                return
            off.discard(iid)
        else:
            off.add(iid)
        self.cfg["off"] = sorted(off)
        self.save()
        self.fill()
        self.tree.selection_set(iid)
        self.tree.focus(iid)

    def on_press(self, ev):
        self._drag = None
        iid = self.tree.identify_row(ev.y)
        if not iid:
            return
        if self.tree.identify_column(ev.x) == "#1" and not self.busy:
            self.toggle(iid)
            return "break"
        self._drag = iid

    def on_drag(self, ev):
        if not self._drag or self.busy:
            return
        tgt = self.tree.identify_row(ev.y)
        if tgt and tgt != self._drag:
            self.tree.move(self._drag, "", self.tree.index(tgt))

    def on_release(self, ev):
        if self._drag:
            new = list(self.tree.get_children())
            if new != [i for i in self.cfg.get("order", []) if i in new]:
                self.cfg["order"] = new + [i for i in self.cfg.get("order", []) if i not in new]
                self.save()
                self.fill()
                self.tree.selection_set(self._drag)
                self.tree.focus(self._drag)
        self._drag = None

    def on_menu(self, ev):
        iid = self.tree.identify_row(ev.y)
        if iid:
            self.tree.selection_set(iid)
            self.tree.focus(iid)
            self.menu.tk_popup(ev.x_root, ev.y_root)

    def move(self, d):
        iid = self.tree.focus()
        if not iid:
            return
        kids = list(self.tree.get_children())
        i = kids.index(iid)
        j = i + d
        if 0 <= j < len(kids):
            kids[i], kids[j] = kids[j], kids[i]
            self.cfg["order"] = kids + [x for x in self.cfg.get("order", []) if x not in kids]
            self.save()
            self.fill()
            self.tree.selection_set(iid)
            self.tree.focus(iid)

    def edit(self):
        iid = self.tree.focus()
        if not iid or not self.ctx or self.busy:
            return
        e = next(x for x in self.ctx["extras"] if x["id"] == iid)
        name = simpledialog.askstring(T("title"), T("edit_name"), initialvalue=e["nomes"]["en"][0], parent=self)
        if name is None:
            return
        short = simpledialog.askstring(T("title"), T("edit_short"), initialvalue=e["nomes"]["en"][1], parent=self)
        if short is None:
            return
        code = simpledialog.askstring(T("title"), T("edit_code"), initialvalue=e["codigo"], parent=self)
        if code is None:
            return
        code = code.strip().upper()
        import detectar_mod as D
        others = {x["codigo"] for x in self.ctx["extras"] if x["id"] != iid}
        if code != e["codigo"] and (len(code) != 3 or not code.isalpha() or code in D.GAME_CODES or code in others):
            messagebox.showerror(T("title"), T("bad_code", c=code))
            return
        self.cfg["names"][iid] = [name.strip() or e["nomes"]["en"][0], short.strip() or e["nomes"]["en"][1]]
        self.cfg["codes"][iid] = code
        self.save()
        self.fill()

    # ---- thumbnails (icon of characters already built) ------------------------------------------
    def load_thumbs(self):
        ctx = self.ctx

        def work():
            out = {}
            try:
                from PIL import Image, ImageDraw
            except ImportError:
                return out
            tdir = ctx["saida"] / "thumbs"
            for e in ctx["extras"]:
                c = e["codigo"]
                ui = ctx["saida"] / "chars" / f"DBFZX_{c}_UI.pak"
                png = tdir / f"{c}.png"
                try:
                    if ui.exists() and (not png.exists() or png.stat().st_mtime < ui.stat().st_mtime):
                        img = icone(ui, c)
                        if img is not None:
                            tdir.mkdir(parents=True, exist_ok=True)
                            img.save(png)
                    if png.exists():
                        out[c] = Image.open(png).convert("RGBA").resize((36, 36))
                except Exception:
                    traceback.print_exc()
                if c not in out:
                    im = Image.new("RGBA", (36, 36), (90, 90, 110, 255))
                    ImageDraw.Draw(im).text((5, 12), c, fill=(255, 255, 255, 255))
                    out[c] = im
            return out

        def done(imgs, err):
            from PIL import ImageTk
            for c, im in (imgs or {}).items():
                self.thumbs[c] = ImageTk.PhotoImage(im)
            self.fill()
        threading.Thread(target=lambda: self.after(0, lambda r=work(): done(r, None)), daemon=True).start()

    # ---- background work ------------------------------------------------------------------------
    def run_bg(self, fn, done, msg):
        if self.busy:
            return
        self.busy = True
        self.status.set(msg)
        for b in (self.b_play, self.b_refresh, self.b_restore):
            b.config(state="disabled")

        def work():
            try:
                r = fn()
                self.after(0, lambda: self.finish(done, r, None))
            except (I.Erro, SystemExit) as ex:
                print(f"\nERROR: {ex}")
                self.after(0, lambda m=str(ex).strip(): self.finish(done, None, m))
            except Exception:
                tb = traceback.format_exc()
                print(tb)
                self.after(0, lambda: self.finish(done, None, tb.strip().splitlines()[-1]))
        threading.Thread(target=work, daemon=True).start()

    def finish(self, done, r, err):
        self.busy = False
        for b in (self.b_play, self.b_refresh, self.b_restore):
            b.config(state="normal")
        done(r, err)

    def pump(self):
        try:
            while True:
                s = self.q.get_nowait()
                self.log.insert("end", s)
                self.log.see("end")
                self.progress_from(s)
        except queue.Empty:
            pass
        self.after(100, self.pump)

    def progress_from(self, s):
        if not self.prog_total:
            return
        for line in s.splitlines():
            m = re.match(r"\[([A-Z]{3})\] replaces", line)
            if m:
                self.prog_n += 1
                self.status.set(T("applying", t=T("building", c=m.group(1))))
            elif re.match(r"\[(\d)\] (.*)", line):
                self.prog_n += 1
                self.status.set(T("applying", t=re.match(r"\[(\d)\] (.*)", line).group(2)))
            elif "$ build_texts.py" in line or "installing into" in line:
                self.prog_n += 1
            self.prog.config(value=min(100, 100 * self.prog_n / self.prog_total))

    # ---- actions --------------------------------------------------------------------------------
    def pick(self, var):
        v = filedialog.askdirectory(initialdir=var.get() or None)
        if v:
            var.set(v)
            self.scan()

    def open_mods(self):
        m = self.mods.get().strip()
        if m and Path(m).is_dir():
            os.startfile(m)

    def play(self):
        if self.busy or self.playing:
            return
        if not self.ctx or self.listing() != self.scan_key:
            self.scan(then=self.play)
            return
        allx, on = self.ordered()
        if not on:
            messagebox.showinfo(T("title"), T("select_one") if allx else T("nochars"))
            return
        self.save()
        ctx = dict(self.ctx, extras=on)

        def work():
            if A.jogo_rodando():
                raise I.Erro("the game (or EasyAntiCheat) is already running. Close it first.")
            if I.precisa_aplicar(ctx):
                I.instalar_tudo(ctx)
                self.ctx["antigos"] = {"itens": [], "chars": [], "textos": []}
            A.criar_atalho(ctx["jogo"])
            return ctx

        def applied(r, err):
            self.prog_total = 0
            self.prog.config(value=0)
            if err:
                self.status.set(T("err"))
                self.show_error(err, dica(err))
                return
            self.start_game(r["jogo"])
        self.prog_total = len(on) + 7
        self.prog_n = 0
        self.run_bg(work, applied, T("applying", t="..."))

    def start_game(self, jogo):
        self.playing = True
        self.update_rows()
        self.status.set(T("running"))
        self.to_tray()

        def done(r, err):
            self.playing = False
            self.from_tray()
            self.update_rows()
            if err:
                self.status.set(T("err"))
                self.show_error(err, dica(err))
            else:
                self.status.set(T("closed"))
                self.fill()
                self.status.set(T("closed"))
        self.run_bg(lambda: A.lancar(jogo), done, T("running"))

    def restore(self):
        g = self.game.get().strip()

        def done(r, err):
            self.update_rows()
            if err:
                self.show_error(err, dica(err))
            else:
                self.status.set(T("restored"))
        self.run_bg(lambda: A.restaurar(Path(g).resolve()), done, "...")

    # ---- tray -----------------------------------------------------------------------------------
    def to_tray(self):
        try:
            import pystray
            from PIL import Image
            img = Image.open(HERE.parent / "icone.png") if (HERE.parent / "icone.png").exists() else \
                Image.new("RGBA", (64, 64), (230, 120, 20, 255))
            self.tray = pystray.Icon("dbfzslots", img, T("tray"),
                                     menu=pystray.Menu(pystray.MenuItem(T("show"), lambda: self.after(0, self.deiconify),
                                                                        default=True)))
            self.tray.run_detached()
            self.withdraw()
        except Exception:
            traceback.print_exc()
            self.tray = None
            self.iconify()

    def from_tray(self):
        if self.tray:
            try:
                self.tray.stop()
            except Exception:
                pass
            self.tray = None
        self.deiconify()
        self.lift()
        self.focus_force()

    def on_close(self):
        if self.playing:
            messagebox.showinfo(T("title"), T("busy_close"))
            if self.tray:
                self.withdraw()
            return
        if self.busy:
            return
        self.save()
        self.destroy()

    # ---- errors / log ---------------------------------------------------------------------------
    def show_error(self, err, fix):
        dlg = tk.Toplevel(self)
        dlg.title(T("err"))
        dlg.transient(self)
        dlg.resizable(False, False)
        linhas = err.strip().splitlines()
        if len(linhas) > 6:                    # the full text is in Details / Copy log
            linhas = linhas[:5] + [f"... (+{len(linhas) - 5}: {T('details')})"]
        ttk.Label(dlg, text="\n".join(linhas), wraplength=520, foreground="#b00020").pack(fill="x", padx=14, pady=(14, 6))
        ttk.Label(dlg, text=fix, wraplength=520).pack(fill="x", padx=14, pady=6)
        bb = ttk.Frame(dlg)
        bb.pack(fill="x", padx=14, pady=(6, 12))
        ttk.Button(bb, text="OK", command=dlg.destroy).pack(side="right")
        ttk.Button(bb, text=T("copy_log"), command=self.copy_log).pack(side="right", padx=6)
        if README.exists():
            ttk.Button(bb, text="README", command=lambda: os.startfile(str(README))).pack(side="left")
        dlg.grab_set()

    def copy_log(self):
        parts = ["== installer ==", self.log.get("1.0", "end").strip()[-20000:]]
        g = self.game.get().strip()
        if g:
            d = Path(g) / I.DATA_DIR / "ready" / "RED/Binaries/Win64/plugins/DBFZSlots"
            for n in ("dbfzslots.log", "dbfzslots_lua.log", "profile.txt"):
                f = d / n
                if f.exists():
                    parts += [f"== {n} ==", f.read_text(encoding="utf-8", errors="replace")[-20000:]]
        self.clipboard_clear()
        self.clipboard_append("\n".join(parts))
        self.status.set(T("copied"))


def icone(ui_pak, code):
    """CS_CIconNN of a built art pak -> PIL image (or None)."""
    from PIL import Image
    from pak import load_key
    import icon_fix as F
    from build_char import Source
    key = load_key()
    src = Source([ui_pak], key)
    for n in src.files:
        m = re.search(r"red/content/ui/charaselect_s3/" + code.lower() + r"/(cs_[cx]icon\d\d)\.uexp$", n)
        if m:
            stem = n[:-5]
            ub = src.get(stem + ".ubulk") if stem + ".ubulk" in src.files else b""
            rgba = F.read_rgba(src.get(n), ub)
            return Image.fromarray(rgba, "RGBA")
    return None


if __name__ == "__main__":
    App(autoplay="--play" in sys.argv).mainloop()
