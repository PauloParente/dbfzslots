// Teste offline: mapeia o exe do jogo (nenhum codigo do jogo e inicializado), aplica as
// patches e exercita as partes autocontidas: caves, consulta da mascara e IsCharaValid dos
// extras. Uso: offline_test.exe <exe do jogo> <pasta de configuracao com chara_mods.txt>
#include <windows.h>
#include <stdio.h>
#include <stdint.h>
#include "../src/profiles.h"

extern uint32_t call_site(void *site, uint64_t rdi, uint64_t rax, uint64_t rdx, uint64_t r13r14);
extern void t_ok(void), t_bad(void), t_ret_edx(void), t_ret_r8d(void), t_ret_r8_64(void), t_ret_rax(void), t_skip(void);
extern uint32_t call_bridge(void *entry, uint32_t edx, uint32_t r8d);
typedef int (*install_fn)(void *, const wchar_t *);
typedef uint32_t (*lookup_fn)(void *obj, int x, int y);
typedef uint8_t (*isvalid_fn)(int id);

static int fails, checks;
static void expect(const char *what, uint32_t got, uint32_t want) {
    checks++;
    if (got != want) { fails++; printf("  FALHOU %s: obtido 0x%x, esperado 0x%x\n", what, got, want); }
}

int wmain(int argc, wchar_t **argv) {
    setvbuf(stdout, NULL, _IONBF, 0);
    if (argc < 3) { printf("uso: offline_test <exe> <pasta_teste>\n"); return 1; }
    uint8_t *base = (uint8_t *)LoadLibraryExW(argv[1], NULL, DONT_RESOLVE_DLL_REFERENCES);
    if (!base) { printf("falha ao mapear o exe (%lu)\n", GetLastError()); return 1; }
    HMODULE dll = LoadLibraryW(L"dbfzslots.dll");
    if (!dll) { printf("falha ao carregar dbfzslots.dll (%lu)\n", GetLastError()); return 1; }
    // 0. formato de perfil em texto: cada perfil compilado exportado e relido tem que ser identico
    {
        typedef int (*exp_fn)(int, const wchar_t *);
        exp_fn ex = (exp_fn)GetProcAddress(dll, "dbfz_profile_export"), rt = (exp_fn)GetProcAddress(dll, "dbfz_profile_roundtrip");
        wchar_t tmp[MAX_PATH]; GetTempPathW(MAX_PATH, tmp); wcscat(tmp, L"dbfz_perfil_teste.txt");
        for (int i = 0; i < NPROFILES; i++) {
            char w[64]; sprintf(w, "perfil %d exportado", i); expect(w, ex(i, tmp), 1);
            sprintf(w, "perfil %d relido sem diferencas", i); expect(w, (uint32_t)rt(i, tmp), 0);
        }
        DeleteFileW(tmp);
        printf("perfil em texto: %d perfis ida e volta\n", NPROFILES);
    }
    int r =((install_fn)GetProcAddress(dll, "dbfzslots_install_at"))(base, argv[2]);
    printf("install -> %d (ver %ls\\ue4ss\\dbfzslots.log)\n", r, argv[2]);
    if (r != 1) return 2;

    // perfil em uso (compilado ou gerado no profile.txt)
    const Profile *p = ((const Profile *(*)(void))GetProcAddress(dll, "dbfz_active_profile"))();
    if (p && base[p->isvalid.rva] != 0xE9) p = NULL;   // hook tem que estar instalado
    if (!p) { printf("nao achei o perfil aplicado\n"); return 3; }
    uint32_t dmy = p->table_entries - 1, max = p->table_entries, first = max + 1;
    uint32_t *g_extra_end = (uint32_t *)GetProcAddress(dll, "g_extra_end");
    uint32_t nextras = *g_extra_end - first;
    printf("perfil: %s\nDMY=0x%x MAX=0x%x extras 0x%x..0x%x\n", p->name, dmy, max, first, *g_extra_end - 1);

    // 1. IsCharaValid dos extras (a cave responde sem chamar o original)
    isvalid_fn iv = (isvalid_fn)(base + p->isvalid.rva);
    for (uint32_t id = first; id < first + nextras; id++) {
        char w[64]; sprintf(w, "IsCharaValid(0x%x)", id); expect(w, iv((int)id), 1);
    }

    // 2. caves das checagens: destinos falsos ok=1 / bad=2
    uint64_t *gt = (uint64_t *)GetProcAddress(dll, "g_t");
    for (int i = T_HOVER1_OK; i <= T_FILL2_BAD; i += 2) { gt[i] = (uint64_t)t_ok; gt[i + 1] = (uint64_t)t_bad; }
    struct { const char *name; const Site *s; int kind; } S[] = {
        {"hover1", &p->hover1, 0}, {"hover2", &p->hover2, 0}, {"hover3", &p->hover3, 0}, {"hover4", &p->hover4, 0},
        {"stored", &p->stored, 1}, {"2a4", &p->s2a4, 2},
        {"cnt1", &p->cnt1, 3}, {"cnt2", &p->cnt2, 4}, {"cnt3", &p->cnt3, 5},
        {"setup_dmy", &p->setup_dmy, 6}, {"setup_real", &p->setup_real, 6}, {"setup_u", &p->setup_u, 7},
        {"fill1", &p->fill1, 8}, {"fill2", &p->fill2, 9},
    };
    uint32_t ids[] = {0, dmy - 1, dmy, max, first, first + nextras - 1, first + nextras, 0x3f};
    static int32_t team[3];
    static uint8_t obj2a4[0x300];
    for (unsigned k = 0; k < sizeof S / sizeof *S; k++) {
        uint8_t *site = base + S[k].s->rva;
        printf("%-10s", S[k].name);
        for (unsigned j = 0; j < sizeof ids / sizeof *ids; j++) {
            uint32_t id = ids[j], got;
            switch (S[k].kind) {
            case 0: got = call_site(site, id, 0, 0, 0); break;
            case 1: got = call_site(site, 0, (uint8_t)id, 0, 0); break;
            case 2: obj2a4[0x2a4] = (uint8_t)id; got = call_site(site, (uint64_t)obj2a4, 0, 0, 0); break;
            case 3: case 4: case 5: team[0] = team[1] = team[2] = (int32_t)id;
                got = call_site(site, 0, (uint64_t)&team[1], 0, 0); break;
            case 6: got = call_site(site, 0, 0, id, 0); break;
            case 7: got = call_site(site, 0, 0, 0, id); break;
            default: got = call_site(site, 0, id, 0, 0); break;
            }
            int is_extra = id >= first && id < first + nextras;
            // stored/fill1/fill2 comparam com MAX no original (DMY passa); os outros com DMY
            int vs_max = S[k].kind >= 8 || S[k].kind == 1;
            int real = (vs_max ? id < max : id < dmy) || is_extra;
            // fill2 e "jae dmy": ok = continua (real), bad = vira DMY
            uint32_t want = real ? 1 : 2;
            char w[64]; sprintf(w, "%s(0x%x)", S[k].name, id); expect(w, got, want);
            printf(" %02x:%s", id, got == 1 ? "ok" : got == 2 ? "--" : "??");
        }
        printf("\n");
    }

    // 3. consulta da mascara: pixel com valor v -> id do personagem
    static uint8_t mask[1280 * 720];
    static uint8_t info[0x200], obj[0x300];
    *(uint8_t **)(info + 0x118) = mask; *(int *)(info + 0x128) = 1280; *(int *)(info + 0x12c) = 720;
    *(uint8_t **)(obj + 0x260) = info; *(float *)(obj + 0x268) = 1.0f / 3; *(float *)(obj + 0x26c) = 1.0f / 3;
    uint32_t main_fn = p->m_main_cmp.rva == 0x3DF82E ? 0x3DF7C0 : 0x3DFB40;
    lookup_fn lk = (lookup_fn)(base + main_fn);
    const uint8_t *orig_tab = base + p->mask_main_tab;   // tabela original continua intacta
    for (int v = 0; v < 64; v++) mask[v] = (uint8_t)v;
    mask[100] = 0x80;
    for (int v = 0; v < 64; v++) {
        int *regions = (int *)GetProcAddress(dll, "g_extra_regions");
        uint32_t want = v < p->mask_main ? orig_tab[v] : max;
        for (uint32_t i = 0; i < nextras; i++) if (regions[i] == v) want = first + i;
        char w[64]; sprintf(w, "mascara %d", v); expect(w, lk(obj, v * 3, 0), want);
    }
    expect("mascara 0x80 (vazio)", lk(obj, 100 * 3, 0), 0xff);

    // 4. camada de icones: contagem, random e tabela icone->id lidos de volta do codigo
    if (p->icon_ops) {
        int n = *(int *)GetProcAddress(dll, "g_n_icons");
        uint32_t R = *(uint32_t *)GetProcAddress(dll, "g_rand_alias");
        uint32_t bpr = *(uint32_t *)GetProcAddress(dll, "g_bp_random");
        int grid = p->mask_extra_first, K = n - grid;
        printf("camada de icones: exe ve %d icones (%d extras), random %u -> blueprint %u\n", n, K, R, bpr);
        expect("random = n_icons", R, (uint32_t)n);
        expect("blueprint random", bpr, (uint32_t)grid);
        const uint8_t *orig = base + p->icon_table;
        int *regions = (int *)GetProcAddress(dll, "g_extra_regions");
        for (const IconOp *op = p->icon_ops; op->s.rva; op++) {
            uint8_t *at = base + op->s.rva + op->off;
            char w[64]; sprintf(w, "op +0x%x", op->s.rva);
            const uint8_t *tab = NULL;
            switch (op->kind) {
            case ICON_COUNT_IMM8: expect(w, *at, (uint32_t)n); break;
            case ICON_RANDOM_IMM8: expect(w, *at, R); break;
            case ICON_RANDOM_IMM32: expect(w, *(uint32_t *)at, R); break;
            case MASK_BOUND_IMM8: expect(w, *at, (uint32_t)(p->mask_extra_first + 15)); break;
            case ICON_TABLE_ABS32: tab = base + *(int32_t *)at; break;
            case ICON_TABLE_RIP: tab = base + op->s.rva + op->len + *(int32_t *)at; break;
            case MASK_TABLE_ABS32: {
                const uint8_t *mt = base + *(int32_t *)at;
                for (uint32_t i = 0; i < nextras; i++) expect(w, mt[regions[i]], first + i);
                break; }
            }
            if (tab) {
                for (int i = 0; i < p->icon_base_count; i++) expect(w, tab[i], orig[i]);
                uint32_t want44 = dmy;
                for (uint32_t i = 0; i < nextras; i++) if (regions[i] == p->icon_base_count) want44 = first + i;
                expect(w, tab[p->icon_base_count], want44);
                for (int k = 0; k < K; k++) expect(w, tab[grid + k], first + (nextras - K) + k);
            }
        }
        // pontes: indice do exe -> indice do blueprint
        gt[T_BR_DISP] = gt[T_BR_SEL] = gt[T_BR_IMG] = (uint64_t)t_ret_edx;
        gt[T_BR_PLAY] = gt[T_BR_STOP] = gt[T_BR_POS] = (uint64_t)t_ret_r8d;
        const Site *bre[] = {&p->br_disp, &p->br_sel, &p->br_img};
        const Site *brr[] = {&p->br_play, &p->br_stop, &p->br_pos};
        for (uint32_t i = 0; i <= R + 2; i++) {
            uint32_t want = i == R ? bpr : (i >= bpr && i < R ? i + 1 : i);
            for (int k = 0; k < 3; k++) {
                char w[64];
                sprintf(w, "ponte edx +0x%x(%u)", bre[k]->rva, i);
                expect(w, call_bridge(base + bre[k]->rva, i, 0), want);
                sprintf(w, "ponte r8d +0x%x(%u)", brr[k]->rva, i);
                expect(w, call_bridge(base + brr[k]->rva, 0, i), want);
            }
        }
        printf("pontes: %u->%u, %u->%u, %u->%u, %u->%u\n", 0u, 0u, bpr - 1, bpr - 1, bpr, bpr + 1, R, bpr);
    }

    // 5. enquadramento do retrato: indice = g_alias[id]
    if (p->po_a1.rva) {
        uint8_t *alias = (uint8_t *)GetProcAddress(dll, "g_alias");
        const Site *po[] = {&p->po_a1, &p->po_a2, &p->po_b1, &p->po_b2};
        uint32_t disp[4];   // deslocamento de cada array lido do proprio exe (muda com o tamanho do elenco)
        for (int k = 0; k < 4; k++) {     // bytes originais (o site ja tem o gancho): 4c 8d 81 <disp32>
            uint8_t ob[7];
            for (int j = 0; j < 7; j++) sscanf(po[k]->hex + 2 * j, "%2hhx", &ob[j]);
            disp[k] = *(const uint32_t *)(ob + 3);
        }
        for (int k = 0; k < 4; k++) gt[T_PO_A1 + k] = (uint64_t)t_ret_r8_64;
        if (p->restore_code) expect("alias restaurado (DGF)", alias[first], (uint32_t)p->restore_present_index);
        for (uint32_t id = 0; id < first + nextras; id++) {
            uint32_t want_idx = id < (uint32_t)p->table_entries - 1 ? id : alias[id];
            if (id >= first) printf("  apelido 0x%02x -> 0x%02x\n", id, alias[id]);
            for (int k = 0; k < 4; k++) {
                uint8_t *site = base + po[k]->rva;
                uint32_t got = call_site(site, 0, 0, 0, id);
                uint32_t want = (uint32_t)(uintptr_t)(site + (uintptr_t)want_idx * 8 + disp[k]);
                char w[64]; sprintf(w, "retrato +0x%x id 0x%x", po[k]->rva, id); expect(w, got, want);
            }
        }
    }

    // 6. tela de VS: ids < MAX seguem com o proprio id; extras seguem com o apelido; o resto pula
    if (p->vs1.rva) {
        uint8_t *alias = (uint8_t *)GetProcAddress(dll, "g_alias");
        const Site *vs[] = {&p->vs1, &p->vs2, &p->vs3};
        for (int k = 0; k < 3; k++) { gt[T_VS1_OK + 2 * k] = (uint64_t)t_ret_rax; gt[T_VS1_SKIP + 2 * k] = (uint64_t)t_skip; }
        uint32_t ids[] = {0, 0x10, dmy, max, first, first + 1, first + nextras - 1, first + nextras, 0x3f};
        for (int k = 0; k < 3; k++) {
            for (unsigned j = 0; j < sizeof ids / sizeof *ids; j++) {
                uint32_t id = ids[j];
                uint32_t want = id < max ? id : (id >= first && id < first + nextras ? alias[id] : 0xffff);
                char w[64]; sprintf(w, "VS +0x%x id 0x%x", vs[k]->rva, id);
                expect(w, call_site(base + vs[k]->rva, 0, id, 0, 0), want);
            }
        }
        printf("HUD: id 0x%x (restaurado) -> indice 0x%x\n", first, alias[first]);
    }

    // 7. tela de VS: GetOffsetXY -> rax = g_alias[id] + 0x25 (nunca alem da tabela)
    if (p->vsofs.rva) {
        uint8_t *alias = (uint8_t *)GetProcAddress(dll, "g_alias");
        gt[T_VSOFS] = (uint64_t)t_ret_rax;
        for (uint32_t id = 0; id < 256; id++) {
            uint8_t b = (uint8_t)id;
            uint32_t want = (id < (uint32_t)p->table_entries - 1 ? id : alias[id]) + 0x25;
            char w[64]; sprintf(w, "GetOffsetXY id 0x%x", id);
            expect(w, call_site(base + p->vsofs.rva, 0, 0, (uint64_t)(uintptr_t)&b, 0), want);
            if (alias[id] >= (uint32_t)p->table_entries) { sprintf(w, "apelido fora da tabela 0x%x", id); expect(w, 1, 0); }
        }
        printf("GetOffsetXY: DGF 0x%x -> 0x%x, extras -> personagem-base\n", first, alias[first]);
    }

    printf("\n%d checagens, %d falhas\n", checks, fails);
    return fails ? 4 : 0;
}

