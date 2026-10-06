// dbfzslots.dll - slots extras de personagem para DRAGON BALL FighterZ (Steam, offline).
//
// Port para a versao Steam do DBFZ-ExtrasCustomSlots-XboxPC (MrPopulutus, MIT), que por sua
// vez se inspirou no Custom Character Slots de WistfulHopes. Ver CREDITS.md.
//
// Personagens extras recebem IDs a partir de MAX+1 (MAX = sentinela "nenhum" do jogo), para
// que DMY e MAX mantenham o significado. Nada e escrito no exe em disco: tudo em memoria,
// e so depois de conferir os bytes de TODOS os pontos do perfil da build.
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <wchar.h>
#include "profiles.h"

#define MAX_EXTRAS 15                 // extras de chara_mods.txt (4a fileira)
#define MAX_SLOTS (MAX_EXTRAS + 1)    // + personagens restaurados
#define VERSION "0.1.0"

// ---- estado lido pelas caves (caves.S) -------------------------------------------
__declspec(dllexport) uint64_t g_t[T_COUNT];          // exportados para o teste offline
__declspec(dllexport) uint32_t g_extra_end;
uint32_t g_dmy, g_max, g_first_extra;
const uint8_t *ui_announce;
const float ui_original_base = 764.0f;
float ui_top_shift = 620.0f;

static uint8_t *g_base;
static const Profile *g_prof;
static FILE *g_log;
static int g_done;
static wchar_t g_mod_dir[MAX_PATH];    // pasta de configuracao (chara_mods.txt, icons.txt, slots.ini)
static int g_restore = 1;
static int g_extra_icons;              // icones da 4a fileira criados pelo modulo Lua
__declspec(dllexport) uint32_t g_rand_alias = 0xFFFF;   // indice do random no exe (45+K)
__declspec(dllexport) uint32_t g_bp_random = 45;        // indice do random no blueprint
__declspec(dllexport) int g_n_icons;
__declspec(dllexport) uint8_t g_alias[256];      // id -> indice nos arrays de apresentacao (retrato)
int64_t g_po_disp[4];                     // deslocamentos dos arrays de enquadramento (dos bytes do exe)
static int g_grid_shift, g_area_logs, g_profile_file_only;
static void setup_user_data(const wchar_t *ini);   // [ui] grid_shift; logs da area do cursor
static int g_extra_base[MAX_SLOTS];              // id do personagem-base de cada extra (-1 = nenhum)    // icones de personagem na grade (o random e este indice)
static wchar_t g_codes[MAX_SLOTS][8];
__declspec(dllexport) int g_extra_regions[MAX_SLOTS];   // regiao da mascara de cada extra
static int g_nextras, g_nfromfile;
static uint32_t g_guobjectarray_rva;   // de slots.ini (medido no UE4SS.log)

// ---- log ------------------------------------------------------------------------
static void logf_(const char *fmt, ...) {
    if (!g_log) return;
    SYSTEMTIME t; GetLocalTime(&t);
    fprintf(g_log, "[%02d:%02d:%02d.%03d] ", t.wHour, t.wMinute, t.wSecond, t.wMilliseconds);
    va_list ap; va_start(ap, fmt); vfprintf(g_log, fmt, ap); va_end(ap);
    fputc('\n', g_log); fflush(g_log);
}

static uint8_t *R(uint32_t rva) { return g_base + rva; }

static int hexbytes(const char *hex, uint8_t *out) {
    int n = 0;
    for (; hex[0] && hex[1]; hex += 2) { unsigned v; sscanf(hex, "%2x", &v); out[n++] = (uint8_t)v; }
    return n;
}

static int site_ok(const Site *s, int verbose) {
    uint8_t want[32]; int n = hexbytes(s->hex, want);
    if (memcmp(R(s->rva), want, n) == 0) return 1;
    if (verbose) {
        char have[80] = {0};
        for (int i = 0; i < n && i < 32; i++) sprintf(have + 2 * i, "%02x", R(s->rva)[i]);
        logf_("  point +0x%x: expected %s, found %s", s->rva, s->hex, have);
    }
    return 0;
}

static int site_len(const Site *s) { return (int)strlen(s->hex) / 2; }

// Todos os sites de um perfil, para conferencia antes de escrever qualquer byte.
static int profile_matches(const Profile *p, int verbose) {
    const Site *all[] = {
        &p->idtocode_lea, &p->idtocode_cmp, &p->codetoid_lea, &p->codetoid_cmp, &p->codetoid_lea2,
        &p->m_main_cmp, &p->m_main_lea, &p->m_alt_cmp, &p->m_alt_lea,
        &p->m_main_cmp7, &p->m_main_idx, &p->m_alt_cmp7, &p->m_alt_idx,
        &p->isvalid, &p->hover1, &p->hover2, &p->hover3, &p->hover4, &p->stored, &p->s2a4,
        &p->cnt1, &p->cnt2, &p->cnt3, &p->setup_dmy, &p->setup_real, &p->setup_u,
        &p->fill1, &p->fill2, &p->portrait1, &p->portrait2, &p->ui_guide, &p->ui_announce,
    };
    int bad = 0;
    for (unsigned i = 0; i < sizeof all / sizeof *all; i++) bad += !site_ok(all[i], verbose);
    for (const IconOp *op = p->icon_ops; op && op->s.rva; op++) bad += !site_ok(&op->s, verbose);
    const Site *br[] = {&p->br_disp, &p->br_sel, &p->br_img, &p->br_play, &p->br_stop, &p->br_pos};
    for (unsigned i = 0; i < 6; i++) if (br[i]->rva) bad += !site_ok(br[i], verbose);
    const Site *po[] = {&p->po_a1, &p->po_a2, &p->po_b1, &p->po_b2};
    for (unsigned i = 0; i < 4; i++) if (po[i]->rva) bad += !site_ok(po[i], verbose);
    const Site *vs[] = {&p->vs1, &p->vs2, &p->vs3};
    for (unsigned i = 0; i < 3; i++) if (vs[i]->rva) bad += !site_ok(vs[i], verbose);
    if (p->vsofs.rva) bad += !site_ok(&p->vsofs, verbose);
    if (p->area.rva) bad += !site_ok(&p->area, verbose);
    // a tabela de personagens precisa comecar em GKS e terminar em DMY
    const uint8_t *tab = R(p->chara_table);
    const wchar_t *first = *(const wchar_t *const *)(tab + 8);
    const wchar_t *last = *(const wchar_t *const *)(tab + 16 * (p->table_entries - 1) + 8);
    if (IsBadReadPtr(first, 8) || IsBadReadPtr(last, 8) || wcscmp(first, L"GKS") || wcscmp(last, L"DMY")) {
        if (verbose) logf_("  character table at +0x%x does not match", p->chara_table);
        bad++;
    }
    return bad == 0;
}

// ---- escrita em memoria -----------------------------------------------------------
static void write_bytes(uint8_t *dst, const void *src, size_t n) {
    DWORD old; VirtualProtect(dst, n, PAGE_EXECUTE_READWRITE, &old);
    memcpy(dst, src, n);
    VirtualProtect(dst, n, old, &old);
    FlushInstructionCache(GetCurrentProcess(), dst, n);
}
static void put8(uint32_t rva, uint8_t v) { write_bytes(R(rva), &v, 1); }
static void put32(uint32_t rva, int32_t v) { write_bytes(R(rva), &v, 4); }

static uint8_t *g_near_cur, *g_near_end;
static int near_alloc_init(void) {
    IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(g_base + ((IMAGE_DOS_HEADER *)g_base)->e_lfanew);
    uintptr_t start = ((uintptr_t)g_base + nt->OptionalHeader.SizeOfImage + 0x10000) & ~(uintptr_t)0xFFFF;
    for (uintptr_t a = start; a < (uintptr_t)g_base + 0x70000000u; a += 0x10000) {
        void *p = VirtualAlloc((void *)a, 0x10000, MEM_RESERVE | MEM_COMMIT, PAGE_EXECUTE_READWRITE);
        if (p) { g_near_cur = p; g_near_end = (uint8_t *)p + 0x10000; return 1; }
    }
    return 0;
}
static void *near_take(size_t n) {
    uint8_t *p = g_near_cur; g_near_cur += (n + 15) & ~(size_t)15;
    return g_near_cur <= g_near_end ? p : NULL;
}

// operando RIP-relativo da instrucao em rva (tamanho len, disp em +doff) -> abs
static void retarget_rip(uint32_t rva, int doff, int len, void *abs) {
    put32(rva + doff, (int32_t)((uint8_t *)abs - (R(rva) + len)));
}

// jmp/call de 5 bytes em rva (resto de n bytes com nop) para 'target' via stub proximo
static void hook(uint32_t rva, int n, void *target, int is_call) {
    uint8_t *stub = near_take(16);
    uint8_t s[14] = {0xFF, 0x25, 0, 0, 0, 0};
    uint64_t a = (uint64_t)target; memcpy(s + 6, &a, 8);
    memcpy(stub, s, 14);
    uint8_t j[16]; memset(j, 0x90, sizeof j);
    j[0] = is_call ? 0xE8 : 0xE9;
    int32_t rel = (int32_t)(stub - (R(rva) + 5)); memcpy(j + 1, &rel, 4);
    write_bytes(R(rva), j, n);
}
static void hook_site(const Site *s, void *cave) { hook(s->rva, site_len(s), cave, 0); }

extern void cave_isvalid(void), cave_hover1(void), cave_hover2(void), cave_hover3(void), cave_hover4(void);
extern void cave_stored(void), cave_2a4(void), cave_cnt1(void), cave_cnt2(void), cave_cnt3(void);
extern void cave_setup_dmy(void), cave_setup_real(void), cave_setup_u_r14(void), cave_setup_u_r13(void);
extern void cave_fill1(void), cave_fill2(void), ui_guide_cave(void), ui_announce_cave(void);
extern void vs1_cave(void), vs2_cave(void), vs3_cave(void), vsofs_cave(void);
extern void po_a1_cave(void), po_a2_cave(void), po_b1_cave(void), po_b2_cave(void);
extern void br_disp_cave(void), br_sel_cave(void), br_img_cave(void), br_play_cave(void), br_stop_cave(void), br_pos_cave(void);

// ---- configuracao -----------------------------------------------------------------
static void mod_path(wchar_t *out, const wchar_t *file) {
    wcscpy(out, g_mod_dir); wcscat(out, L"\\"); wcscat(out, file);
}

static int valid_code(const char *p, size_t n) {
    if (n != 3) return 0;
    for (size_t i = 0; i < n; i++) if (!((p[i] >= 'A' && p[i] <= 'Z') || (p[i] >= '0' && p[i] <= '9'))) return 0;
    return 1;
}

static void load_codes(void) {
    wchar_t path[MAX_PATH]; mod_path(path, L"chara_mods.txt");
    FILE *f = _wfopen(path, L"rb");
    if (!f) { logf_("chara_mods.txt not found in %ls", path); return; }
    char line[128]; int lineno = 0;
    while (fgets(line, sizeof line, f)) {
        lineno++;
        char *p = line; while (*p == ' ' || *p == '\t' || (uint8_t)*p == 0xEF || (uint8_t)*p == 0xBB || (uint8_t)*p == 0xBF) p++;
        if (*p == ';' || *p == '#' || *p == '\r' || *p == '\n' || !*p) continue;
        size_t n = strcspn(p, "\r\n \t;#");
        if (!valid_code(p, n)) { logf_("chara_mods.txt line %d ignored: '%.*s' (use 3 uppercase letters/digits)", lineno, (int)n, p); continue; }
        int dup = 0;
        for (int i = 0; i < g_nextras; i++) if (g_codes[i][0] == p[0] && g_codes[i][1] == p[1] && g_codes[i][2] == p[2]) dup = 1;
        const uint8_t *tab = R(g_prof->chara_table);
        for (int i = 0; i < g_prof->table_entries; i++) {
            const wchar_t *c = *(const wchar_t *const *)(tab + 16 * i + 8);
            if (c[0] == p[0] && c[1] == p[1] && c[2] == p[2]) dup = 2;
        }
        if (dup) { logf_("chara_mods.txt line %d ignored: %.3s %s", lineno, p, dup == 1 ? "repeated" : "is already a game character"); continue; }
        if (g_nfromfile >= MAX_EXTRAS) { logf_("chara_mods.txt: limit of %d extras reached, line %d ignored", MAX_EXTRAS, lineno); continue; }
        for (int i = 0; i < 3; i++) g_codes[g_nextras][i] = (wchar_t)p[i];
        g_codes[g_nextras][3] = 0;
        g_extra_regions[g_nextras] = g_prof->mask_extra_first + g_nfromfile;
        // 2o token opcional: personagem-base (enquadramento do retrato, arte feita para ele)
        g_extra_base[g_nextras] = -1;
        char *q = p + n; while (*q == ' ' || *q == '\t') q++;
        size_t bn = strcspn(q, "\r\n \t;#");
        if (bn == 3) {
            const uint8_t *tb = R(g_prof->chara_table);
            for (int i = 0; i < g_prof->table_entries - 1; i++) {
                const wchar_t *c = *(const wchar_t *const *)(tb + 16 * i + 8);
                if (c[0] == q[0] && c[1] == q[1] && c[2] == q[2]) g_extra_base[g_nextras] = i;
            }
            if (g_extra_base[g_nextras] < 0) logf_("chara_mods.txt line %d: base '%.3s' is not a game character", lineno, q);
        }
        logf_("extra 0x%02x = %ls (mask %d, 4th row, base %s)", g_first_extra + g_nextras, g_codes[g_nextras],
              g_extra_regions[g_nextras], g_extra_base[g_nextras] >= 0 ? "ok" : "none: GKS framing");
        g_nextras++; g_nfromfile++;
    }
    fclose(f);
}

static void load_ini(void) {
    wchar_t ini[MAX_PATH]; mod_path(ini, L"slots.ini");
    int shift = GetPrivateProfileIntW(L"ui", L"bar_shift", 620, ini);
    g_grid_shift = (int)GetPrivateProfileIntW(L"ui", L"grid_shift", 0, ini);
    setup_user_data(ini);
    if (g_grid_shift < 0 || g_grid_shift > 300) g_grid_shift = 0;
    if (shift < 0) shift = 0;
    if (shift > 700) shift = 700;
    ui_top_shift = (float)shift;
    wchar_t buf[32];
    GetPrivateProfileStringW(L"engine", L"guobjectarray_rva", L"0", buf, 32, ini);
    g_guobjectarray_rva = (uint32_t)wcstoul(buf, NULL, 0);
    g_restore = GetPrivateProfileIntW(L"roster", L"restore_missing", 1, ini);
    g_extra_icons = GetPrivateProfileIntW(L"ui", L"extra_icons", -1, ini);   // -1 = um por extra
    if (g_extra_icons > MAX_EXTRAS) g_extra_icons = MAX_EXTRAS;
    logf_("slots.ini: bar_shift=%d guobjectarray_rva=0x%x restore_missing=%d", shift, g_guobjectarray_rva, g_restore);
}

// ---- engine -----------------------------------------------------------------------
typedef void *(*find_fn)(void *cls, void *outer, const wchar_t *name, uint8_t exact);
typedef void *(*load_fn)(void *cls, void *outer, const wchar_t *name, const wchar_t *filename,
                         uint32_t flags, void *sandbox, uint8_t allow_reconcile);
typedef void *(*class_fn)(void);

static void *tex_class(void) { return ((class_fn)R(g_prof->texture_class))(); }
static void *find_obj(void *cls, const wchar_t *path) {
    return ((find_fn)R(g_prof->static_find))(cls, (void *)-1, path, 0);
}
static void *load_obj(void *cls, const wchar_t *path) {
    if (!path || !*path) return NULL;   // caminho vazio aborta a engine
    return ((load_fn)R(g_prof->static_load))(cls, NULL, path, NULL, 0, NULL, 1);
}

// RootSet: impede o GC de liberar texturas que a interface vai reutilizar.
struct UObjectItem { void *object; volatile LONG flags; int32_t cluster, serial; };
static int add_to_root(void *obj) {
    if (!g_guobjectarray_rva || !obj) return 0;
    uint8_t *arr = R(g_guobjectarray_rva);
    struct UObjectItem *items = *(struct UObjectItem **)(arr + 0x10);
    int32_t max = *(int32_t *)(arr + 0x18), num = *(int32_t *)(arr + 0x1c);
    int32_t idx = *(int32_t *)((uint8_t *)obj + 0x0c);
    if (!items || num <= 0 || num > max || idx < 0 || idx >= num) return 0;
    if (items[idx].object != obj) return 0;   // layout nao confere: nao mexe
    InterlockedOr(&items[idx].flags, 1 << 30);
    return 1;
}

// ---- retratos grandes ---------------------------------------------------------------
static wchar_t g_portraits[MAX_SLOTS][100];
static volatile long g_select_hits, g_select_reported;
static int g_portrait_logs, g_preloads;

// ---- saves separados ------------------------------------------------------------------
// O jogo guarda saves/config em %LOCALAPPDATA%\DBFighterZ\Saved, a mesma pasta do jogo da
// Steam. Com [user] separate_saves=1 esta copia passa a usar <jogo>\UserData\DBFighterZ\Saved:
// SHGetKnownFolderPath(FOLDERID_LocalAppData) responde a pasta propria. No shell32 a funcao e
// um "jmp [rip+X]": troca-se so o ponteiro X (dados), so neste processo.
typedef HRESULT (WINAPI *known_fn)(const GUID *, DWORD, HANDLE, PWSTR *);
static known_fn g_known_orig;
static wchar_t g_user_data[MAX_PATH];
static const GUID LOCAL_APPDATA_ID = {0xF1B32785, 0x6FBA, 0x4FCF, {0x9D, 0x55, 0x7B, 0x8E, 0x7F, 0x15, 0x70, 0x91}};
static HRESULT WINAPI known_hook(const GUID *id, DWORD flags, HANDLE tok, PWSTR *out) {
    if (g_user_data[0] && out && id && memcmp(id, &LOCAL_APPDATA_ID, sizeof(GUID)) == 0) {
        static void *(WINAPI *alloc)(SIZE_T);
        if (!alloc) alloc = (void *(WINAPI *)(SIZE_T))(void *)GetProcAddress(LoadLibraryW(L"ole32.dll"), "CoTaskMemAlloc");
        size_t n = (wcslen(g_user_data) + 1) * sizeof(wchar_t);
        PWSTR p = alloc ? (PWSTR)alloc(n) : NULL;
        if (p) { memcpy(p, g_user_data, n); *out = p; return S_OK; }
    }
    return g_known_orig(id, flags, tok, out);
}
static void setup_user_data(const wchar_t *ini) {
    if (!GetPrivateProfileIntW(L"user", L"separate_saves", 0, ini)) return;
    wchar_t rel[MAX_PATH], tmp[MAX_PATH];
    GetPrivateProfileStringW(L"user", L"folder", L"..\\..\\..\\..\\..\\UserData", rel, MAX_PATH, ini);
    if (rel[0] && rel[1] == L':') wcscpy(tmp, rel);
    else { wcscpy(tmp, g_mod_dir); wcscat(tmp, L"\\"); wcscat(tmp, rel); }
    if (!GetFullPathNameW(tmp, MAX_PATH, g_user_data, NULL)) { g_user_data[0] = 0; return; }
    CreateDirectoryW(g_user_data, NULL);
    uint8_t *f = (uint8_t *)(void *)GetProcAddress(LoadLibraryW(L"shell32.dll"), "SHGetKnownFolderPath");
    if (!f || f[0] != 0x48 || f[1] != 0xFF || f[2] != 0x25) {
        logf_("separate saves: SHGetKnownFolderPath has an unexpected format; disabled");
        g_user_data[0] = 0; return;
    }
    known_fn *slot = (known_fn *)(f + 7 + *(int32_t *)(f + 3));
    DWORD old;
    if (!VirtualProtect(slot, sizeof *slot, PAGE_READWRITE, &old)) { g_user_data[0] = 0; return; }
    g_known_orig = *slot;
    *slot = known_hook;
    VirtualProtect(slot, sizeof *slot, old, &old);
    logf_("separate saves: LOCALAPPDATA -> %ls (saves in DBFighterZ\\Saved)", g_user_data);
}

// Area de movimento do cursor (substitui SetCursorMoveArea): na selecao de personagens a
// grade sobe grid_shift px (1280x720), entao a area sobe junto, senao o cursor nao alcanca o
// Random. Unidade da area descoberta pelo tamanho (720p, 1080p ou canvas 2160).
void area_set(uint8_t *self, const float *pos, const float *size) {
    float x0 = pos[0], y0 = pos[1], x1 = x0 + size[0], y1 = y0 + size[1], d = 0;
    int is_main = 0;
    if (g_grid_shift) {
        // sem cache: a classe e recarregada (outro endereco) quando a tela e recriada
        void *main_cls = find_obj(NULL, L"/Game/UI/CharaSelect_S3/BP_CharaSelect_Main.BP_CharaSelect_Main_C");
        is_main = main_cls && *(void **)(self + 0x10) == main_cls;
        if (is_main) d = (float)g_grid_shift * (y1 <= 720.5f ? 1.0f : y1 <= 1080.5f ? 1.5f : 3.0f);
    }
    float *a = (float *)(self + 0x250);
    a[0] = x0; a[1] = y0 - d; a[2] = x1; a[3] = y1 - d;
    if (g_area_logs++ < 40)
        logf_("cursor area %p (%s): (%.1f, %.1f)-(%.1f, %.1f) -> y %.1f..%.1f", (void *)self,
              is_main ? "character select" : "other", x0, y0, x1, y1, y0 - d, y1 - d);
}

static void *portrait_find(void *cls, void *outer, const wchar_t *name, uint8_t exact) {
    find_fn find = (find_fn)R(g_prof->static_find);
    int portrait = name && wcsstr(name, L"/CS_CharacterImage_") != NULL;
    if (portrait) g_select_hits++;
    if (portrait && g_nextras && !find(cls, outer, g_portraits[0], exact)) {
        int ok = 0;
        for (int i = 0; i < g_nextras; i++) {
            if (!find(cls, outer, g_portraits[i], exact)) load_obj(cls, g_portraits[i]);
            ok += find(cls, outer, g_portraits[i], exact) != NULL;
        }
        if (g_preloads++ < 40) logf_("extra portraits loaded: %d/%d", ok, g_nextras);
    }
    void *r = find(cls, outer, name, exact);
    if (!r && portrait) {
        load_obj(cls, name);
        r = find(cls, outer, name, exact);
        if (g_portrait_logs++ < 60) logf_("portrait %ls: %s", name, r ? "loaded" : "NOT FOUND (CS_CharacterImage_<CODE> missing from the pak?)");
    }
    return r;
}

#include "profile_text.c"

// ---- instalacao --------------------------------------------------------------------
// Perfil para builds sem perfil compilado: <config>\profile.txt (antes perfil.txt; gerado pelo
// instalador a partir de slots/assinaturas.json).
static Profile g_file_prof;
static const Profile *file_profile(void) {
    const wchar_t *name = L"profile.txt";
    wchar_t path[MAX_PATH]; mod_path(path, name);
    if (GetFileAttributesW(path) == INVALID_FILE_ATTRIBUTES) {
        name = L"perfil.txt";
        mod_path(path, name);
        if (GetFileAttributesW(path) == INVALID_FILE_ATTRIBUTES) return NULL;
    }
    int bad;
    if (!profile_load(path, &g_file_prof, &bad)) {
        if (bad > 0) logf_("%ls: line %d is invalid; ignored", name, bad);
        else logf_("%ls: incomplete or with unexpected values; ignored", name);
        return NULL;
    }
    g_prof = &g_file_prof;
    if (profile_matches(&g_file_prof, 0)) return &g_file_prof;
    logf_("%ls (%s) does not match this exe:", name, g_file_prof.name);
    profile_matches(&g_file_prof, 1);
    g_prof = NULL;
    return NULL;
}

static int install(void) {
    {   // teste: [engine] profile_file_only=1 ignora os perfis compilados e usa so o perfil.txt
        wchar_t ini[MAX_PATH]; mod_path(ini, L"slots.ini");
        g_profile_file_only = (int)GetPrivateProfileIntW(L"engine", L"profile_file_only", 0, ini);
    }
    for (int i = 0; i < NPROFILES && !g_profile_file_only; i++) {
        if (profile_matches(&PROFILES[i], 0)) { g_prof = &PROFILES[i]; break; }
    }
    if (!g_prof) g_prof = file_profile();
    if (!g_prof) {
        logf_("NO profile matches this exe; nothing was changed. Details per profile:");
        for (int i = 0; i < NPROFILES; i++) { logf_(" profile %s:", PROFILES[i].name); g_prof = &PROFILES[i]; profile_matches(&PROFILES[i], 1); }
        g_prof = NULL;
        return 0;
    }
    const Profile *p = g_prof;
    logf_("profile: %s", p->name);
    g_dmy = (uint32_t)p->table_entries - 1;
    g_max = (uint32_t)p->table_entries;
    g_first_extra = g_max + 1;
    g_extra_end = g_first_extra;
    logf_("game roster: %d entries, DMY=0x%x MAX=0x%x, extras from 0x%x", p->table_entries, g_dmy, g_max, g_first_extra);

    load_ini();
    if (!g_guobjectarray_rva) g_guobjectarray_rva = p->guobjectarray;
    if (g_restore && p->restore_code) {
        for (int i = 0; i < 3; i++) g_codes[g_nextras][i] = (wchar_t)p->restore_code[i];
        g_codes[g_nextras][3] = 0;
        g_extra_regions[g_nextras] = p->restore_region;
        g_extra_base[g_nextras] = p->restore_present_index;
        logf_("restored 0x%02x = %ls in its original slot (mask %d)", g_first_extra + g_nextras, g_codes[g_nextras], p->restore_region);
        g_nextras++;
    }
    load_codes();
    if (!g_nextras) { logf_("no extras in chara_mods.txt; nothing to do"); return 0; }
    g_extra_end = g_first_extra + g_nextras;
    if (!near_alloc_init()) { logf_("no memory near the exe; nothing was changed"); return 0; }

    // 1. tabela id <-> codigo ampliada
    struct CodeEntry { int32_t id; int32_t pad; const wchar_t *code; };
    int base_n = p->table_entries;
    struct CodeEntry *tab = near_take(sizeof(struct CodeEntry) * (base_n + MAX_SLOTS));
    memcpy(tab, R(p->chara_table), base_n * sizeof *tab);
    for (int i = 0; i < g_nextras; i++) {
        tab[base_n + i].id = (int32_t)(g_first_extra + i); tab[base_n + i].pad = 0; tab[base_n + i].code = g_codes[i];
    }
    uint8_t count = (uint8_t)(base_n + g_nextras);
    retarget_rip(p->idtocode_lea.rva, 3, 7, tab);
    put8(p->idtocode_cmp.rva + 2, count);
    retarget_rip(p->codetoid_lea.rva, 3, 7, (uint8_t *)tab + 8);
    put8(p->codetoid_cmp.rva + 3, count);
    retarget_rip(p->codetoid_lea2.rva, 3, 7, tab);

    // 2. mascara -> id: regioes mask_main.. da 4a linha viram os extras
    uint8_t *mm = near_take(64), *ma = near_take(64);
    memset(mm, (int)g_max, 64); memset(ma, (int)g_max, 64);
    memcpy(mm, R(p->mask_main_tab), p->mask_main);
    memcpy(ma, R(p->mask_alt_tab), p->mask_alt);
    for (int i = 0; i < g_nextras; i++) { mm[g_extra_regions[i]] = (uint8_t)(g_first_extra + i); ma[g_extra_regions[i]] = (uint8_t)(g_first_extra + i); }
    uint8_t bound = (uint8_t)(p->mask_extra_first + MAX_EXTRAS);
    put8(p->m_main_cmp.rva + 2, bound); retarget_rip(p->m_main_lea.rva, 3, 7, mm);
    put8(p->m_alt_cmp.rva + 2, bound);  retarget_rip(p->m_alt_lea.rva, 3, 7, ma);
    put8(p->m_main_cmp7.rva + 2, bound); put32(p->m_main_idx.rva + 5, (int32_t)(mm - g_base));
    put8(p->m_alt_cmp7.rva + 2, bound);  put32(p->m_alt_idx.rva + 5, (int32_t)(ma - g_base));

    // 2b. camada de icones: o blueprint atual tem mask_extra_first icones de personagem
    //     (o exe antigo conhece icon_base_count) e o random logo depois deles.
    if (p->icon_ops) {
        if (g_extra_icons < 0 || g_extra_icons > g_nfromfile) g_extra_icons = g_nfromfile;
        int grid = p->mask_extra_first;             // icones de personagem na grade dos paks (45)
        int n_icons = grid + g_extra_icons;         // vistos pelo exe: grade + extras, contiguos
        uint32_t rand_alias = (uint32_t)n_icons;    // o random fica logo depois deles
        uint8_t *it = near_take(64);
        memset(it, (int)g_dmy, 64);                 // DMY: nunca e "valido" nem esta sob o cursor
        memcpy(it, R(p->icon_table), p->icon_base_count);
        for (int i = 0; i < g_nextras; i++)
            if (g_extra_regions[i] < grid) it[g_extra_regions[i]] = (uint8_t)(g_first_extra + i);
        for (int k = 0; k < g_extra_icons; k++)
            it[grid + k] = (uint8_t)(g_first_extra + (g_nextras - g_nfromfile) + k);
        int nops = 0;
        for (const IconOp *op = p->icon_ops; op->s.rva; op++, nops++) {
            uint32_t a = op->s.rva + op->off;
            switch (op->kind) {
            case ICON_COUNT_IMM8:   put8(a, (uint8_t)n_icons); break;
            case ICON_RANDOM_IMM8:  put8(a, (uint8_t)rand_alias); break;
            case ICON_RANDOM_IMM32: put32(a, (int32_t)rand_alias); break;
            case ICON_TABLE_ABS32:  put32(a, (int32_t)(it - g_base)); break;
            case ICON_TABLE_RIP:    retarget_rip(op->s.rva, op->off, op->len, it); break;
            case MASK_BOUND_IMM8:   put8(a, bound); break;
            case MASK_TABLE_ABS32:  put32(a, (int32_t)(mm - g_base)); break;
            }
        }
        g_bp_random = (uint32_t)grid;
        g_rand_alias = rand_alias;
        if (p->br_disp.rva) {
            g_t[T_BR_DISP] = (uint64_t)R(p->br_disp.rva + 5); hook_site(&p->br_disp, br_disp_cave);
            g_t[T_BR_SEL]  = (uint64_t)R(p->br_sel.rva + 5);  hook_site(&p->br_sel, br_sel_cave);
            g_t[T_BR_IMG]  = (uint64_t)R(p->br_img.rva + 5);  hook_site(&p->br_img, br_img_cave);
            g_t[T_BR_PLAY] = (uint64_t)R(p->br_play.rva + 5); hook_site(&p->br_play, br_play_cave);
            g_t[T_BR_STOP] = (uint64_t)R(p->br_stop.rva + 5); hook_site(&p->br_stop, br_stop_cave);
            g_t[T_BR_POS]  = (uint64_t)R(p->br_pos.rva + 5);  hook_site(&p->br_pos, br_pos_cave);
        }
        g_n_icons = n_icons;
        logf_("icon layer: %d points + 6 bridges; exe sees %d icons (%d extras on the 4th row), random %d -> blueprint %d",
              nops, n_icons, g_extra_icons, rand_alias, grid);
    }

    // 3-5. checagens de "personagem real"
    for (int i = 0; i < T_BR_DISP; i++) g_t[i] = (uint64_t)R(p->t[i]);   // pontes: preenchidas na camada de icones
    hook_site(&p->isvalid, cave_isvalid);
    hook_site(&p->hover1, cave_hover1); hook_site(&p->hover2, cave_hover2);
    hook_site(&p->hover3, cave_hover3); hook_site(&p->hover4, cave_hover4);
    hook_site(&p->stored, cave_stored); hook_site(&p->s2a4, cave_2a4);
    hook_site(&p->cnt1, cave_cnt1); hook_site(&p->cnt2, cave_cnt2); hook_site(&p->cnt3, cave_cnt3);
    hook_site(&p->setup_dmy, cave_setup_dmy); hook_site(&p->setup_real, cave_setup_real);
    // o registrador do 3o ponto de setup varia por build (41 83 fe = r14d, 41 83 fd = r13d)
    hook_site(&p->setup_u, R(p->setup_u.rva)[2] == 0xFE ? (void *)cave_setup_u_r14 : (void *)cave_setup_u_r13);
    hook_site(&p->fill1, cave_fill1); hook_site(&p->fill2, cave_fill2);

    // 6. interface: barra de ajuda e retratos grandes
    ui_announce = R(p->announce_obj);
    hook_site(&p->ui_guide, ui_guide_cave);
    hook_site(&p->ui_announce, ui_announce_cave);
    for (int i = 0; i < g_nextras; i++)
        _snwprintf(g_portraits[i], 100, L"/Game/UI/CharaSelect_S3/tex/CS_CharacterImage_%ls.CS_CharacterImage_%ls", g_codes[i], g_codes[i]);
    hook(p->portrait1.rva, 5, portrait_find, 1);
    hook(p->portrait2.rva, 5, portrait_find, 1);

    // 7. enquadramento do retrato: extras usam o indice do personagem-base
    for (int i = 0; i < 256; i++) g_alias[i] = (uint8_t)(i < p->table_entries - 1 ? i : 0);
    for (int i = 0; i < g_nextras; i++)
        g_alias[g_first_extra + i] = (uint8_t)(g_extra_base[i] >= 0 ? g_extra_base[i] : 0);
    if (p->po_a1.rva) {
        const Site *pos4[] = {&p->po_a1, &p->po_a2, &p->po_b1, &p->po_b2};
        for (int k = 0; k < 4; k++) g_po_disp[k] = *(const int32_t *)R(pos4[k]->rva + 3);   // lea r8,[rcx+disp32]
        g_t[T_PO_A1] = (uint64_t)R(p->po_a1.rva + 11); hook_site(&p->po_a1, po_a1_cave);
        g_t[T_PO_A2] = (uint64_t)R(p->po_a2.rva + 11); hook_site(&p->po_a2, po_a2_cave);
        g_t[T_PO_B1] = (uint64_t)R(p->po_b1.rva + 11); hook_site(&p->po_b1, po_b1_cave);
        g_t[T_PO_B2] = (uint64_t)R(p->po_b2.rva + 11); hook_site(&p->po_b2, po_b2_cave);
        logf_("portrait framing: %d aliases (extras -> base character)", g_nextras);
    }
    if (p->vs1.rva) {
        for (int i = 0; i < 6; i++) g_t[T_VS1_OK + i] = (uint64_t)R(p->vs_t[i]);
        hook_site(&p->vs1, vs1_cave); hook_site(&p->vs2, vs2_cave); hook_site(&p->vs3, vs3_cave);
        logf_("battle HUD: icon offsets for the extras (3 points)");
    }
    if (p->area.rva) {
        extern void area_set(uint8_t *, const float *, const float *);
        hook_site(&p->area, (void *)area_set);
        logf_("cursor area: grid %d px up (character select)", g_grid_shift);
    }
    if (p->vsofs.rva) {
        g_t[T_VSOFS] = (uint64_t)R(p->vsofs.rva + 7); hook_site(&p->vsofs, vsofs_cave);
        logf_("VS/loading screen: GetOffsetXY uses the alias (extras -> base character)");
    }

    logf_("installed: %d extras (0x%x..0x%x), near memory at +0x%llx",
          g_nextras, g_first_extra, g_extra_end - 1, (unsigned long long)((uint8_t *)tab - g_base));
    return 1;
}

// cfg_dir: pasta com chara_mods.txt, icons.txt e slots.ini; o log tambem vai para la.
// Usado pelo jogo (dbfzslots_init) e pelo teste offline.
__declspec(dllexport) int dbfzslots_install_at(void *base, const wchar_t *cfg_dir) {
    if (g_done) return g_done;
    g_base = base;
    wcscpy(g_mod_dir, cfg_dir);
    wchar_t path[MAX_PATH]; mod_path(path, L"dbfzslots.log");
    g_log = _wfopen(path, L"w");
    logf_("dbfzslots %s, exe at %p, config in %ls", VERSION, base, cfg_dir);
    g_done = install() ? 1 : -1;
    return g_done;
}

// Pasta de configuracao: <pasta da DLL>\DBFZSlots se existir, senao a pasta da DLL.
// Como plugin ASI: plugins\DBFZSlots.asi + plugins\DBFZSlots\*.txt
static void default_cfg_dir(HMODULE self, wchar_t *out) {
    GetModuleFileNameW(self, out, MAX_PATH);
    wchar_t *s = wcsrchr(out, L'\\'); if (s) *s = 0;
    wchar_t sub[MAX_PATH]; wcscpy(sub, out); wcscat(sub, L"\\DBFZSlots");
    DWORD a = GetFileAttributesW(sub);
    if (a != INVALID_FILE_ATTRIBUTES && (a & FILE_ATTRIBUTE_DIRECTORY)) wcscpy(out, sub);
}

__declspec(dllexport) int dbfzslots_init(void) {
    // o jogo passa a pular para dentro desta DLL: ela nunca pode ser descarregada
    HMODULE self;
    GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_PIN,
                       (LPCWSTR)(void *)dbfzslots_init, &self);
    wchar_t cfg[MAX_PATH]; default_cfg_dir(self, cfg);
    return dbfzslots_install_at(GetModuleHandleW(NULL), cfg);
}

// ---- exports para o Lua (lua_CFunction; o estado Lua nao e usado) ----------------------
__declspec(dllexport) int luaopen_dbfzslots(void *L) { (void)L; dbfzslots_init(); return 0; }

// Carrega os icones da 4a linha (icons.txt: "COD /Game/...Textura.Textura") e os mantem na memoria.
static int g_icon_logs;
__declspec(dllexport) int dbfz_load_icons(void *L) {
    (void)L;
    if (g_done != 1) return 0;
    wchar_t list[MAX_PATH]; mod_path(list, L"icons.txt");
    FILE *f = _wfopen(list, L"rb");
    if (!f) { logf_("icons: icons.txt not found"); return 0; }
    void *cls = tex_class();
    char line[256], code[16], apath[200];
    while (fgets(line, sizeof line, f)) {
        char *s = line; while (*s == ' ' || *s == '\t') s++;
        if (*s == ';' || *s == '#' || sscanf(s, "%15s %199s", code, apath) != 2) continue;
        wchar_t path[200]; size_t n = strlen(apath);
        for (size_t i = 0; i <= n; i++) path[i] = (wchar_t)(uint8_t)apath[i];
        void *tex = find_obj(cls, path);
        if (!tex) { load_obj(cls, path); tex = find_obj(cls, path); }
        int rooted = add_to_root(tex);
        if (g_icon_logs++ < 60) logf_("icon %s %s -> %s%s", code, apath, tex ? "ok" : "NOT FOUND", tex && !rooted ? " (no RootSet)" : "");
    }
    fclose(f);
    return 0;
}

// Pre-carrega os retratos grandes dos extras e os mantem na memoria.
static int g_preload_done;
__declspec(dllexport) int dbfz_preload(void *L) {
    (void)L;
    if (g_done != 1 || g_preload_done || !g_nextras) return 0;
    void *cls = tex_class();
    int found = 0, rooted = 0;
    for (int i = 0; i < g_nextras; i++) {
        void *obj = find_obj(cls, g_portraits[i]);
        if (!obj) { load_obj(cls, g_portraits[i]); obj = find_obj(cls, g_portraits[i]); }
        if (!obj) { logf_("preload: %ls not found", g_portraits[i]); continue; }
        found++; rooted += add_to_root(obj);
    }
    if (found) g_preload_done = 1;
    logf_("preload: %d/%d portraits, %d kept in memory", found, g_nextras, rooted);
    return 0;
}

// Retorna 1 resultado (o proprio argumento) uma vez apos nova atividade na tela de selecao.
__declspec(dllexport) int dbfz_select_seen(void *L) {
    (void)L;
    long hits = g_select_hits;
    if (hits == g_select_reported) return 0;
    g_select_reported = hits;
    return 1;
}

// Diagnostico da tela de VS (chamado pelas caves VS_OFS): valores dos arrays de deslocamento
// no indice do personagem e no do apelido. site 1 = lider, 2/3 = membros 2 e 3.
// Debug: confere o layout de UFunction usado pelo MemberVariableLayout.ini do UE4SS.
// /Script/UMG.CanvasPanel:AddChildToCanvas(Content) -> CanvasPanelSlot:
// NumParms = 2, ParmsSize = 16, ReturnValueOffset = 8.
__declspec(dllexport) int dbfz_check_layout(void *L) {
    (void)L;
    if (g_done != 1) return 0;
    const uint8_t *f = find_obj(NULL, L"/Script/UMG.CanvasPanel:AddChildToCanvas");
    if (!f) f = ((find_fn)R(g_prof->static_find))(NULL, NULL, L"/Script/UMG.CanvasPanel:AddChildToCanvas", 0);
    if (!f) { logf_("layout: AddChildToCanvas not found"); return 0; }
    static const struct { const char *name; int flags, nparms, psize, retoff; } L4[] = {
        {"UE4 padrao (TArray 16 bytes)", 136, 142, 144, 146},
        {"TArray 24 bytes (port Xbox)", 152, 158, 160, 162},
    };
    for (int i = 0; i < 2; i++) {
        uint32_t fl = *(const uint32_t *)(f + L4[i].flags);
        uint8_t np = f[L4[i].nparms];
        uint16_t ps = *(const uint16_t *)(f + L4[i].psize), ro = *(const uint16_t *)(f + L4[i].retoff);
        logf_("layout %s: FunctionFlags=0x%08x NumParms=%u ParmsSize=%u ReturnValueOffset=%u -> %s",
              L4[i].name, fl, np, ps, ro, (np == 2 && ps == 16 && ro == 8) ? "MATCHES" : "does not match");
    }
    return 0;
}

// Debug: despeja o objeto do anuncio (para conferir o layout usado pela barra de ajuda).
__declspec(dllexport) int dbfz_dump_announce(void *L) {
    (void)L;
    if (!ui_announce) return 0;
    char line[200]; int n = 0;
    for (int i = 0; i < 0x70; i++) {
        n += sprintf(line + n, "%02x", ui_announce[i]);
        if (i % 16 == 15) { logf_("announcement +%02x: %s  '%.16s'", i - 15, line, (const char *)ui_announce + i - 15); n = 0; }
    }
    return 0;
}

// Carregada como plugin .asi (Ultimate ASI Loader): instala ja na inicializacao, antes do
// jogo rodar. Carregada pelo Lua do UE4SS (.dll): instala em luaopen_dbfzslots.
BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID r) {
    (void)r;
    if (reason == DLL_PROCESS_ATTACH) {
        wchar_t me[MAX_PATH]; GetModuleFileNameW(h, me, MAX_PATH);
        size_t n = wcslen(me);
        if (n > 4 && _wcsicmp(me + n - 4, L".asi") == 0) dbfzslots_init();
    }
    return TRUE;
}
