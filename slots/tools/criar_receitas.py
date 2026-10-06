"""
criar_receitas.py - Gera slots/receitas.json (catalogo de receitas testadas) a partir do manifesto.

Uso: python criar_receitas.py        (le slots/extras.json e as fontes em downloads/)

Cada receita e indexada pelo MD5 do ARQUIVO ORIGINAL baixado (zip/rar), entao quem baixar
exatamente o mesmo arquivo recebe a receita testada: codigo, nomes nos idiomas, pastas
mantidas/realocadas, ajustes descobertos na pratica (preload_fix, keep_refs) e textos extras.
Caminhos viram relativos ao arquivo (pak dentro do zip) para servirem em qualquer PC.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent

# arquivo original (como baixado) de cada extra, pagina e autores; so os testados no jogo
ORIGENS = {
    "GHB": ("downloads/mods/beastgohanmoveset_74f64.zip", "https://gamebanana.com/mods/594699", "RCBurrito"),
    "GKG": ("downloads/mods/ssggoku_moveset_.zip", "https://gamebanana.com/mods/395251", "RCBurrito"),
    "VSF": ("downloads/mods/vegetass4_moveset_.zip", "https://gamebanana.com/mods/525644", "RCBurrito"),
    "RDN": ("downloads/mods/raditzmoveset_dc065.zip", "https://gamebanana.com/mods/440356", "RCBurrito"),
    "CCL": ("downloads/mods/captaincell_model.zip", "https://gamebanana.com/mods/439037", "Shoyoumomo"),
    "GKT": ("downloads/mods/ssj3_goku_dragon_fist.zip", "https://gamebanana.com/mods/444309", "BigManJPD"),
    "OSH": ("downloads/mods/mod_85469.zip", "https://gamebanana.com/mods/451264", "BigManJPD"),
    "VTS": ("downloads/mods/udbfzsupervegito_v104.zip", "https://gamebanana.com/mods/431940", "Sureidu"),
    "GRN": ("downloads/mods/granolah_v2.zip", "https://gamebanana.com/mods/461713", "BigManJPD"),
    "SKN": ("downloads/mods/sukuna_moveset11_eng_jap_1722b.zip", "https://gamebanana.com/mods/581695", "BigManJPD"),
    "GSF": ("downloads/mods/SSJ4 Goku 1.0.7.rar", "https://www.patreon.com/posts/super-saiyan-4-112573246", ""),
}
# pasta onde o arquivo foi extraido aqui, quando nao e o nome do arquivo
XDIR = {"GSF": "ssj4goku"}
# arquivos complementares (outro zip do mesmo mod) -> codigo
COMPLEMENTOS = {"downloads/mods/capcell_moveset.zip": "CCL"}


def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def inner(path):
    """caminho dentro do arquivo: downloads/mods/x/<pasta>/<resto> -> <resto>"""
    parts = Path(path).as_posix().split("/")
    return "/".join(parts[4:]) if parts[:3] == ["downloads", "mods", "x"] else Path(path).name


# mods instalados pelo Unverum (sem zip: o Unverum extrai e apaga). Indexados pelo MD5 do PAK, que e o
# mesmo na pasta do Unverum, no ~mods de uma copia e solto. Textos: o text.json da pasta do Unverum.
UNV = Path(r"F:/downloads/Jogos/Mods/Unverum/Mods/Dragon Ball FighterZ")
ORIGENS_PAK = {
    "SBG": (UNV / "Sol Badguy (Moveset)/SolBadguy", "SolBadguy.pak", "https://gamebanana.com/mods/655977", "RCBurrito", "SBG", {}),
    "YUG": (UNV / "Yami Yugi - Character Moveset Mod/Yugi Muto - Character Moveset Mod/Yugi Muto Character Moveset Mod",
            "YugiMutoCharacterMoveset.pak", "https://gamebanana.com/mods/641650", "Kongmeng", "YUG", {}),
    # o mod tem a pasta Chara/DIO: o codigo do slot nao pode ser DIO
    "DIO": (UNV / "DIO - Character Moveset Mod/DIO Character Moveset Mod", "DIOCharacterMoveset.pak",
            "https://gamebanana.com/mods/564409", "Kongmeng", "DIB",
            {"keep": ["DIO", "WLD"], "extra_files": ["Config/Windows/WindowsEngine.ini"]}),
}


def receitas_de_pak(cfg, cat):
    import sys
    sys.path.insert(0, str(HERE))
    from detectar_mod import text_pairs_json
    for ref, (pasta, pak, url, autor, code, extra) in ORIGENS_PAK.items():
        e = cfg[ref]
        b = e.get("construir", {})
        r = {"codigo": code, "base": e["base"], "nomes": e["nomes"], "pagina": url, "autor": autor, "paks": [pak]}
        for k in ("keep", "move", "preload_fix", "keep_refs"):
            if b.get(k):
                r[k] = b[k]
        r.update(extra)
        tj = pasta / "text.json"
        if tj.exists():
            r["textos_extra"] = [{"header": k, "text": v} for k, v in text_pairs_json(tj).items()]
        cat["receitas"][md5(pasta / pak)] = r
        print(f"{code}: {pak} ({len(r.get('textos_extra', []))} textos)")


def main():
    cfg = json.load(open(ROOT / "slots/extras.json", encoding="utf-8"))
    cat = {"_comentario": "Receitas testadas no jogo, indexadas pelo MD5 do arquivo original baixado. "
                          "paks/textos sao caminhos DENTRO do arquivo. Gerado por slots/tools/criar_receitas.py.",
           "receitas": {}}
    for code, (arq, url, autor) in ORIGENS.items():
        e = cfg[code]
        b = e.get("construir", {})
        r = {"codigo": code, "base": e["base"], "nomes": e["nomes"], "pagina": url, "autor": autor,
             # so os paks de dentro do proprio arquivo; os de um complemento entram depois deles
             "paks": [inner(p) for p in b.get("paks", []) if Path(p).as_posix().split("/")[3:4] == [XDIR.get(code, Path(arq).stem)]]}
        for k in ("keep", "move", "preload_fix", "keep_refs"):
            if b.get(k):
                r[k] = b[k]
        texts = []
        for t in e.get("textos", []):
            if t.startswith("slots/textos/"):
                r["textos_extra"] = json.load(open(ROOT / t, encoding="utf-8"))["Entries"]
            else:
                texts.append(inner(t))
        if texts:
            r["textos"] = texts
        assert r["paks"], f"{code}: nenhum pak dentro de {arq}"
        cat["receitas"][md5(ROOT / arq)] = r
        print(f"{code}: {Path(arq).name}")
    receitas_de_pak(cfg, cat)
    for arq, code in COMPLEMENTOS.items():
        cat["receitas"][md5(ROOT / arq)] = {"complemento_de": code, "arquivo": Path(arq).name}
    out = ROOT / "slots/receitas.json"
    out.write_text(json.dumps(cat, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{out}: {len(cat['receitas'])} entradas")


if __name__ == "__main__":
    main()
