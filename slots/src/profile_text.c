// Perfil em texto (perfil.txt): o mesmo Profile dos perfis compilados, uma linha por campo.
// Gerado por slots/tools/gerar_perfil.py para builds que nao tem perfil compilado. O plugin so
// usa o perfil se TODOS os bytes esperados baterem (profile_matches), igual aos compilados.
//
//   ; comentario
//   name = texto
//   table_entries = 47                      (inteiros: decimal ou 0x...)
//   site idtocode_lea = 0x4FC35D 488d35bc487502
//   t ISVALID_DMY = 0x50781D
//   vs_t = 0x61BFBB 0x61BFE5 0x61BFEE 0x61C01E 0x61C027 0x61C057
//   icon_op = 0x3DC266 83ff2c COUNT_IMM8 2 3
// Incluido em slots.c (mesma unidade de compilacao).
#include <stddef.h>
#include <stdlib.h>

enum { F_INT, F_U32, F_STR, F_SITE };
static const struct { const char *key; int type; size_t off; } PROFILE_FIELDS[] = {
#define FI(n) {#n, F_INT, offsetof(Profile, n)}
#define FU(n) {#n, F_U32, offsetof(Profile, n)}
#define FS(n) {#n, F_STR, offsetof(Profile, n)}
#define FT(n) {#n, F_SITE, offsetof(Profile, n)}
    FS(name), FI(table_entries), FI(mask_main), FI(mask_alt), FI(mask_extra_first),
    FS(restore_code), FI(restore_region), FU(chara_table),
    FT(idtocode_lea), FT(idtocode_cmp), FT(codetoid_lea), FT(codetoid_cmp), FT(codetoid_lea2),
    FU(mask_main_tab), FU(mask_alt_tab),
    FT(m_main_cmp), FT(m_main_lea), FT(m_alt_cmp), FT(m_alt_lea),
    FT(m_main_cmp7), FT(m_main_idx), FT(m_alt_cmp7), FT(m_alt_idx),
    FT(isvalid), FT(hover1), FT(hover2), FT(hover3), FT(hover4), FT(stored), FT(s2a4),
    FT(cnt1), FT(cnt2), FT(cnt3), FT(setup_dmy), FT(setup_real), FT(setup_u), FT(fill1), FT(fill2),
    FU(static_find), FU(static_load), FU(texture_class),
    FT(portrait1), FT(portrait2), FT(ui_guide), FT(ui_announce), FU(announce_obj),
    FI(icon_base_count), FU(icon_table),
    FT(br_disp), FT(br_sel), FT(br_img), FT(br_play), FT(br_stop), FT(br_pos),
    FU(guobjectarray),
    FT(po_a1), FT(po_a2), FT(po_b1), FT(po_b2), FI(restore_present_index),
    FT(vs1), FT(vs2), FT(vs3), FT(vsofs), FT(area),
#undef FI
#undef FU
#undef FS
#undef FT
};
#define NFIELDS (int)(sizeof PROFILE_FIELDS / sizeof *PROFILE_FIELDS)

static const char *const T_NAMES[T_COUNT] = {
    "ISVALID_DMY", "ISVALID_GO",
    "HOVER1_OK", "HOVER1_BAD", "HOVER2_OK", "HOVER2_BAD",
    "HOVER3_OK", "HOVER3_BAD", "HOVER4_OK", "HOVER4_BAD",
    "STORED_OK", "STORED_BAD", "2A4_OK", "2A4_BAD",
    "CNT1_OK", "CNT1_BAD", "CNT2_OK", "CNT2_BAD", "CNT3_OK", "CNT3_BAD",
    "SETUP_DMY_OK", "SETUP_DMY_BAD", "SETUP_REAL_OK", "SETUP_REAL_BAD",
    "SETUP_U_OK", "SETUP_U_BAD",
    "FILL1_OK", "FILL1_BAD", "FILL2_OK", "FILL2_BAD",
    "UI_GUIDE_RESUME", "UI_ANNOUNCE_RESUME",
    "BR_DISP", "BR_SEL", "BR_IMG", "BR_PLAY", "BR_STOP", "BR_POS",
    "PO_A1", "PO_A2", "PO_B1", "PO_B2",
    "VS1_OK", "VS1_SKIP", "VS2_OK", "VS2_SKIP", "VS3_OK", "VS3_SKIP",
    "VSOFS",
};
static const char *const ICON_KINDS[] = {
    "COUNT_IMM8", "RANDOM_IMM8", "RANDOM_IMM32", "TABLE_ABS32", "TABLE_RIP", "MASK_BOUND_IMM8", "MASK_TABLE_ABS32",
};

static int profile_save(const Profile *p, FILE *f) {
    fprintf(f, "; perfil DBFZSlots (formato 1)\n");
    for (int i = 0; i < NFIELDS; i++) {
        const void *v = (const uint8_t *)p + PROFILE_FIELDS[i].off;
        const char *k = PROFILE_FIELDS[i].key;
        switch (PROFILE_FIELDS[i].type) {
        case F_INT: fprintf(f, "%s = %d\n", k, *(const int *)v); break;
        case F_U32: fprintf(f, "%s = 0x%X\n", k, *(const uint32_t *)v); break;
        case F_STR: if (*(const char *const *)v) fprintf(f, "%s = %s\n", k, *(const char *const *)v); break;
        case F_SITE: {
            const Site *s = v;
            if (s->rva) fprintf(f, "site %s = 0x%X %s\n", k, s->rva, s->hex);
            break;
        }
        }
    }
    for (int i = 0; i < T_COUNT; i++)
        if (p->t[i]) fprintf(f, "t %s = 0x%X\n", T_NAMES[i], p->t[i]);
    if (p->vs1.rva) {
        fprintf(f, "vs_t =");
        for (int i = 0; i < 6; i++) fprintf(f, " 0x%X", p->vs_t[i]);
        fprintf(f, "\n");
    }
    for (const IconOp *op = p->icon_ops; op && op->s.rva; op++)
        fprintf(f, "icon_op = 0x%X %s %s %u %u\n", op->s.rva, op->s.hex, ICON_KINDS[op->kind], op->off, op->len);
    return 1;
}

static char *dupstr(const char *s) {
    size_t n = strlen(s) + 1;
    char *d = malloc(n);
    if (d) memcpy(d, s, n);
    return d;
}

static int valid_hex(const char *h) {
    size_t n = strlen(h);
    if (n < 2 || n > 64 || n % 2) return 0;
    for (; *h; h++) if (!((*h >= '0' && *h <= '9') || (*h >= 'a' && *h <= 'f') || (*h >= 'A' && *h <= 'F'))) return 0;
    return 1;
}

// Le um perfil em texto. Retorna 1 e preenche *p (strings e icon_ops alocados), ou 0 com o
// numero da linha com problema em *bad_line.
static int profile_load(const wchar_t *path, Profile *p, int *bad_line) {
    FILE *f = _wfopen(path, L"rb");
    *bad_line = 0;
    if (!f) return 0;
    memset(p, 0, sizeof *p);
    IconOp *ops = calloc(64, sizeof *ops);
    int nops = 0, lineno = 0, ok = 1;
    char line[512];
    while (ok && fgets(line, sizeof line, f)) {
        lineno++;
        char *s = line;
        while (*s == ' ' || *s == '\t') s++;
        s[strcspn(s, "\r\n")] = 0;
        if (!*s || *s == ';' || *s == '#') continue;
        char k1[64] = "", k2[64] = "", rest[400] = "";
        if (strncmp(s, "site ", 5) == 0 || strncmp(s, "t ", 2) == 0) {
            int is_site = s[0] == 's';
            unsigned rva; char hex[80] = "";
            if (sscanf(s, "%63s %63s = %x %79s", k1, k2, &rva, hex) < 3) { ok = 0; break; }
            if (is_site) {
                int i;
                for (i = 0; i < NFIELDS; i++)
                    if (PROFILE_FIELDS[i].type == F_SITE && strcmp(PROFILE_FIELDS[i].key, k2) == 0) break;
                if (i == NFIELDS || !valid_hex(hex)) { ok = 0; break; }
                Site *st = (Site *)((uint8_t *)p + PROFILE_FIELDS[i].off);
                st->rva = rva; st->hex = dupstr(hex);
            } else {
                int i;
                for (i = 0; i < T_COUNT; i++) if (strcmp(T_NAMES[i], k2) == 0) break;
                if (i == T_COUNT) { ok = 0; break; }
                p->t[i] = rva;
            }
            continue;
        }
        if (sscanf(s, "%63s = %399[^\n]", k1, rest) != 2) { ok = 0; break; }
        if (strcmp(k1, "vs_t") == 0) {
            if (sscanf(rest, "%x %x %x %x %x %x", &p->vs_t[0], &p->vs_t[1], &p->vs_t[2], &p->vs_t[3], &p->vs_t[4], &p->vs_t[5]) != 6) ok = 0;
            continue;
        }
        if (strcmp(k1, "icon_op") == 0) {
            unsigned rva, off, len; char hex[80], kind[32];
            if (nops >= 63 || sscanf(rest, "%x %79s %31s %u %u", &rva, hex, kind, &off, &len) != 5 || !valid_hex(hex)) { ok = 0; break; }
            int kk;
            for (kk = 0; kk < (int)(sizeof ICON_KINDS / sizeof *ICON_KINDS); kk++) if (strcmp(ICON_KINDS[kk], kind) == 0) break;
            if (kk == (int)(sizeof ICON_KINDS / sizeof *ICON_KINDS) || off >= len || len > strlen(hex) / 2) { ok = 0; break; }
            ops[nops].s.rva = rva; ops[nops].s.hex = dupstr(hex);
            ops[nops].kind = (uint8_t)kk; ops[nops].off = (uint8_t)off; ops[nops].len = (uint8_t)len;
            nops++;
            continue;
        }
        int i;
        for (i = 0; i < NFIELDS; i++) if (PROFILE_FIELDS[i].type != F_SITE && strcmp(PROFILE_FIELDS[i].key, k1) == 0) break;
        if (i == NFIELDS) { ok = 0; break; }
        void *v = (uint8_t *)p + PROFILE_FIELDS[i].off;
        if (PROFILE_FIELDS[i].type == F_STR) *(char **)v = dupstr(rest);
        else {
            char *end; unsigned long x = strtoul(rest, &end, 0);
            if (end == rest) { ok = 0; break; }
            if (PROFILE_FIELDS[i].type == F_INT) *(int *)v = (int)x; else *(uint32_t *)v = (uint32_t)x;
        }
    }
    fclose(f);
    if (!ok) { *bad_line = lineno; free(ops); return 0; }
    if (nops) p->icon_ops = ops; else free(ops);
    if (!p->name) p->name = "perfil.txt";
    // sanidade minima: o resto e conferido byte a byte por profile_matches
    if (p->table_entries < 40 || p->table_entries > 64 || !p->chara_table || !p->isvalid.rva) { *bad_line = -1; return 0; }
    return 1;
}

// Exporta um perfil compilado (teste de ida e volta e base para o gerador).
__declspec(dllexport) int dbfz_profile_export(int index, const wchar_t *path) {
    if (index < 0 || index >= NPROFILES) return 0;
    FILE *f = _wfopen(path, L"wb");
    if (!f) return 0;
    profile_save(&PROFILES[index], f);
    fclose(f);
    return 1;
}

// Le um perfil em texto e compara campo a campo com um compilado (teste do formato).
// Retorna o numero de diferencas (0 = identico), ou -1 se nao conseguiu ler.
__declspec(dllexport) int dbfz_profile_roundtrip(int index, const wchar_t *path) {
    Profile q; int bad;
    if (index < 0 || index >= NPROFILES || !profile_load(path, &q, &bad)) return -1;
    const Profile *p = &PROFILES[index];
    int diff = 0;
    for (int i = 0; i < NFIELDS; i++) {
        const void *a = (const uint8_t *)p + PROFILE_FIELDS[i].off, *b = (const uint8_t *)&q + PROFILE_FIELDS[i].off;
        switch (PROFILE_FIELDS[i].type) {
        case F_INT: diff += *(const int *)a != *(const int *)b; break;
        case F_U32: diff += *(const uint32_t *)a != *(const uint32_t *)b; break;
        case F_STR: {
            const char *x = *(const char *const *)a, *y = *(const char *const *)b;
            diff += (x || y) && (!x || !y || strcmp(x, y)); break;
        }
        case F_SITE: {
            const Site *x = a, *y = b;
            diff += x->rva != y->rva || (x->rva && strcmp(x->hex, y->hex)); break;
        }
        }
    }
    diff += memcmp(p->t, q.t, sizeof p->t) != 0;
    diff += p->vs1.rva && memcmp(p->vs_t, q.vs_t, sizeof p->vs_t) != 0;
    const IconOp *x = p->icon_ops, *y = q.icon_ops;
    for (; x && x->s.rva; x++, y++) {
        if (!y || !y->s.rva || x->s.rva != y->s.rva || strcmp(x->s.hex, y->s.hex) || x->kind != y->kind || x->off != y->off || x->len != y->len) { diff++; break; }
    }
    if ((!x || !x->s.rva) && y && y->s.rva) diff++;
    return diff;
}
