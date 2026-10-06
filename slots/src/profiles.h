// Perfis de build: RVAs e bytes esperados de cada ponto de patch.
// Medidos com tools/re (ver slots/STEAM-RVAS.md). O perfil so e usado se TODOS os
// bytes esperados baterem com o exe em memoria.
#pragma once
#include <stdint.h>

// Indices de g_t[] (destinos absolutos usados pelas caves em caves.S).
enum {
    T_ISVALID_DMY, T_ISVALID_GO,
    T_HOVER1_OK, T_HOVER1_BAD, T_HOVER2_OK, T_HOVER2_BAD,
    T_HOVER3_OK, T_HOVER3_BAD, T_HOVER4_OK, T_HOVER4_BAD,
    T_STORED_OK, T_STORED_BAD, T_2A4_OK, T_2A4_BAD,
    T_CNT1_OK, T_CNT1_BAD, T_CNT2_OK, T_CNT2_BAD, T_CNT3_OK, T_CNT3_BAD,
    T_SETUP_DMY_OK, T_SETUP_DMY_BAD, T_SETUP_REAL_OK, T_SETUP_REAL_BAD,
    T_SETUP_U_OK, T_SETUP_U_BAD,
    T_FILL1_OK, T_FILL1_BAD, T_FILL2_OK, T_FILL2_BAD,
    T_UI_GUIDE_RESUME, T_UI_ANNOUNCE_RESUME,
    T_BR_DISP, T_BR_SEL, T_BR_IMG, T_BR_PLAY, T_BR_STOP, T_BR_POS,   // retorno das pontes (+5)
    T_PO_A1, T_PO_A2, T_PO_B1, T_PO_B2,                             // retorno do enquadramento do retrato
    T_VS1_OK, T_VS1_SKIP, T_VS2_OK, T_VS2_SKIP, T_VS3_OK, T_VS3_SKIP, // HUD de batalha: CharaIconImage1P_1.. (xoffset/yoffset)
    T_VSOFS,                                                         // tela de VS: GetOffsetXY (+7)
    T_COUNT
};

typedef struct { uint32_t rva; const char *hex; } Site;

// Camada de icones: o exe antigo pensa em 44 icones de personagem com o random no indice 44;
// o blueprint atual tem 45 (o 44 e o Goku SSJ4 Daima) e o random no 45.
enum IconOpKind {
    ICON_COUNT_IMM8,    // cmp reg, N  (contagem de icones)          -> imm8 em +off = n_icons
    ICON_RANDOM_IMM8,   // cmp reg, N  (indice do random)            -> imm8 em +off = random
    ICON_RANDOM_IMM32,  // mov reg, N  (indice do random)            -> imm32 em +off = random
    ICON_TABLE_ABS32,   // movzx r,[rax+base+disp32] (icone->id)     -> disp32 em +off = tabela - base
    ICON_TABLE_RIP,     // lea r,[rip+disp32] (icone->id)            -> disp32 em +off, instrucao de len bytes
    MASK_BOUND_IMM8,    // cmp cl, N   (limite da tabela mascara->id) -> imm8 em +off = limite
    MASK_TABLE_ABS32,   // movzx r,[rax+base+disp32] (mascara->id)   -> disp32 em +off = tabela - base
};
typedef struct { Site s; uint8_t kind, off, len; } IconOp;

typedef struct {
    const char *name;
    int table_entries;            // entradas da tabela id<->codigo (inclui DMY)
    int mask_main, mask_alt;      // tamanhos das duas tabelas mascara->id
    int mask_extra_first;         // 1a regiao da mascara usada pelos extras (4a fileira)
    // personagem que existe nos paks/mascara mas nao nesta build do exe (restaurado como extra)
    const char *restore_code; int restore_region;
    // tabela id<->codigo
    uint32_t chara_table;
    Site idtocode_lea, idtocode_cmp, codetoid_lea, codetoid_cmp, codetoid_lea2;
    // mascara
    uint32_t mask_main_tab, mask_alt_tab;
    Site m_main_cmp, m_main_lea, m_alt_cmp, m_alt_lea;      // cmp dl,N / lea rcx,[tab]
    Site m_main_cmp7, m_main_idx, m_alt_cmp7, m_alt_idx;    // cmp dl,N / movzx eax,[rax+r14+tab]
    // checagens
    Site isvalid;
    Site hover1, hover2, hover3, hover4;
    Site stored, s2a4;
    Site cnt1, cnt2, cnt3;
    Site setup_dmy, setup_real, setup_u;
    Site fill1, fill2;
    uint32_t t[T_COUNT];          // destinos ok/bad de cada site
    // engine / UI
    uint32_t static_find, static_load, texture_class;
    Site portrait1, portrait2;    // call StaticFindObject
    Site ui_guide, ui_announce;   // addss xmm,[764.0]
    uint32_t announce_obj;
    // camada de icones (vazia = build ja tem o numero certo de icones)
    int icon_base_count;          // icones de personagem que o exe conhece
    uint32_t icon_table;          // tabela icone -> id original
    const IconOp *icon_ops;
    // pontes nativo -> blueprint que recebem indice de icone da grade principal; a camada
    // traduz os indices do exe (extras contiguos, random depois deles) para os do blueprint
    // (random no 45, extras anexados em 46+).
    Site br_disp, br_sel, br_img;          // indice em edx
    Site br_play, br_stop, br_pos;         // indice em r8d
    uint32_t guobjectarray;
    // enquadramento do retrato grande: lea r8,[rcx+DISP] / lea r8,[r8+r14*8] (11 bytes), arrays
    // por personagem no widget BG; os extras usam o indice do personagem-base (apelido)
    Site po_a1, po_a2, po_b1, po_b2;
    int restore_present_index;    // indice do personagem restaurado nesses arrays (dados novos)
    // tela de VS: cmp eax,MAX / jge pula (ids >= MAX ficavam sem xoffset/yoffset)
    Site vs1, vs2, vs3;
    uint32_t vs_t[6];             // ok/pula de cada um
    // tela de VS/carregamento: REDWidgetOffsetXYSetting::GetOffsetXY le this+0x250+id*16 SEM checar
    // limite (tabela de 47/48 personagens preenchida pelo BP_VSChara_*); movzx eax,[rdx] / add rax,0x25
    Site vsofs;
    // area de movimento do cursor: REDWidgetCharaSelect_BaseSelect::SetCursorMoveArea(pos, tam)
    // grava min em this+0x250 e max em this+0x258 (funcao inteira substituida)
    Site area;
} Profile;

static const IconOp EACNOP_ICON_OPS[] = {
    // laco que liga/desliga os icones (SetDispIcon) e o random depois dele
    {{0x3DC266, "83ff2c"}, ICON_COUNT_IMM8, 2, 3},
    {{0x3DC272, "420fb69c3000fb8403"}, ICON_TABLE_ABS32, 5, 9},
    {{0x3DC33E, "ba2c000000"}, ICON_RANDOM_IMM32, 1, 5},
    // lacos que limpam o destaque (SetIconSelectFlag false) e o random
    {{0x3DDCFA, "83fb2c"}, ICON_COUNT_IMM8, 2, 3},
    {{0x3DDD2B, "83fb2c"}, ICON_COUNT_IMM8, 2, 3},
    {{0x3DDD6A, "83fb2c"}, ICON_COUNT_IMM8, 2, 3},
    {{0x3DDD7A, "ba2c000000"}, ICON_RANDOM_IMM32, 1, 5},
    // destaque pelo cursor de um lado
    {{0x3DE230, "83fb2c"}, ICON_COUNT_IMM8, 2, 3},
    {{0x3DE253, "460fb69c3000fb8403"}, ICON_TABLE_ABS32, 5, 9},
    {{0x3DE321, "ba2c000000"}, ICON_RANDOM_IMM32, 1, 5},
    // destaque por qualquer cursor (laco 0..random inclusivo)
    {{0x3DE380, "83ff2c"}, ICON_RANDOM_IMM8, 2, 3},
    {{0x3DE3A6, "83ff2c"}, ICON_RANDOM_IMM8, 2, 3},
    {{0x3DE46C, "460fb68c3800fb8403"}, ICON_TABLE_ABS32, 5, 9},
    {{0x3DE4DA, "80f92c"}, MASK_BOUND_IMM8, 2, 3},
    {{0x3DE4E9, "420fb6843840fb8403"}, MASK_TABLE_ABS32, 5, 9},
    // buscas personagem -> icone (StopCursorChoice, PlayCursorChoice, posicao do icone)
    {{0x3E48CA, "4c8d252fb24603"}, ICON_TABLE_RIP, 3, 7},
    {{0x3E4925, "4183f82c"}, ICON_COUNT_IMM8, 3, 4},
    {{0x3E55D4, "488d0d25a54603"}, ICON_TABLE_RIP, 3, 7},
    {{0x3E55E0, "83fb2c"}, ICON_COUNT_IMM8, 2, 3},
    {{0x3E9928, "41b82c000000"}, ICON_RANDOM_IMM32, 2, 6},
    {{0x3E996B, "488d158e614603"}, ICON_TABLE_RIP, 3, 7},
    {{0x3E9972, "4183f82c"}, ICON_COUNT_IMM8, 3, 4},
    {{0}, 0, 0, 0},
};

static const Profile PROFILES[] = {
{
    .name = "eac-nop (RED-Win64-Shipping-eac-nop-loaded.exe, 2025-12-13, 47 characters)",
    .table_entries = 47, .mask_main = 0x2C, .mask_alt = 0x26,
    // a mascara dos paks atuais tem a regiao 44 (DGF); nesta build ela fica sem personagem
    .mask_extra_first = 45,
    // Goku SSJ4 Daima: veio depois desta build; o slot dele (regiao 44) existe na grade atual
    .restore_code = "DGF", .restore_region = 44,
    .chara_table = 0x2C50C20,
    .idtocode_lea = {0x4FC35D, "488d35bc487502"}, .idtocode_cmp = {0x4FC37A, "83f92f"},
    .codetoid_lea = {0x4FC462, "4c8d3dbf477502"}, .codetoid_cmp = {0x4FC51F, "4183fe2f"},
    .codetoid_lea2 = {0x4FC535, "488d0de4467502"},
    .mask_main_tab = 0x384FB40, .mask_alt_tab = 0x384FBF0,
    .m_main_cmp = {0x3DF82E, "80fa2c7206"}, .m_main_lea = {0x3DF83C, "488d0dfd024703"},
    .m_alt_cmp = {0x3DF79E, "80fa267206"}, .m_alt_lea = {0x3DF7AC, "488d0d3d044703"},
    .m_main_cmp7 = {0x3DE2C7, "80fa2c7207"}, .m_main_idx = {0x3DE2D6, "420fb6843040fb8403"},
    .m_alt_cmp7 = {0x3DDF87, "80fa267207"}, .m_alt_idx = {0x3DDF96, "420fb68430f0fb8403"},
    .isvalid = {0x507810, "40574883ec208bf983f92e7508"},
    .hover1 = {0x3DD575, "83ff2e0f8df1000000"}, .hover2 = {0x3DD5BE, "83ff2e7d12"},
    .hover3 = {0x3DD805, "83ff2e0f8df1000000"}, .hover4 = {0x3DD84E, "83ff2e7d12"},
    .stored = {0x6C1B50, "488bd93c2f7219"},
    .s2a4 = {0x6BE902, "80bfa40200002e488b8f800200007219"},
    .cnt1 = {0x5537A0, "8378fc2d7f02"}, .cnt2 = {0x5537A8, "83382d7f02"}, .cnt3 = {0x5537AF, "8378042d7f02"},
    .setup_dmy = {0x554346, "83fa2e0f8d37010000"}, .setup_real = {0x5544CA, "83fa2d7f65"},
    .setup_u = {0x54EC7D, "4183fe2e0f839c010000"},
    .fill1 = {0x52ACAD, "83f82f7217"}, .fill2 = {0x52ACCE, "83f82f733b"},
    .t = {
        [T_ISVALID_DMY] = 0x50781D, [T_ISVALID_GO] = 0x507825,
        [T_HOVER1_OK] = 0x3DD57E, [T_HOVER1_BAD] = 0x3DD66F,
        [T_HOVER2_OK] = 0x3DD5C3, [T_HOVER2_BAD] = 0x3DD5D5,
        [T_HOVER3_OK] = 0x3DD80E, [T_HOVER3_BAD] = 0x3DD8FF,
        [T_HOVER4_OK] = 0x3DD853, [T_HOVER4_BAD] = 0x3DD865,
        [T_STORED_OK] = 0x6C1B70, [T_STORED_BAD] = 0x6C1B57,
        [T_2A4_OK] = 0x6BE92B, [T_2A4_BAD] = 0x6BE912,
        [T_CNT1_OK] = 0x5537A6, [T_CNT1_BAD] = 0x5537A8,
        [T_CNT2_OK] = 0x5537AD, [T_CNT2_BAD] = 0x5537AF,
        [T_CNT3_OK] = 0x5537B5, [T_CNT3_BAD] = 0x5537B7,
        [T_SETUP_DMY_OK] = 0x55434F, [T_SETUP_DMY_BAD] = 0x554486,
        [T_SETUP_REAL_OK] = 0x5544CF, [T_SETUP_REAL_BAD] = 0x554534,
        [T_SETUP_U_OK] = 0x54EC87, [T_SETUP_U_BAD] = 0x54EE23,
        [T_FILL1_OK] = 0x52ACC9, [T_FILL1_BAD] = 0x52ACB2,
        [T_FILL2_OK] = 0x52ACD3, [T_FILL2_BAD] = 0x52AD0E,
        [T_UI_GUIDE_RESUME] = 0x548557, [T_UI_ANNOUNCE_RESUME] = 0x549137,
    },
    .static_find = 0xBB1A20, .static_load = 0xBB2BF0, .texture_class = 0x24BFA20,
    .portrait1 = {0x3DD0D6, "e845497d00"}, .portrait2 = {0x3DD336, "e8e5467d00"},
    .ui_guide = {0x54854F, "f30f583555ea7202"}, .ui_announce = {0x54912E, "f3440f580575de7202"},
    .announce_obj = 0x3D246B0,
    .icon_base_count = 44, .icon_table = 0x384FB00, .icon_ops = EACNOP_ICON_OPS,
    .br_disp = {0x832320, "4488442418"}, .br_sel = {0x832990, "4488442418"}, .br_img = {0x832920, "4c89442418"},
    .br_play = {0x831410, "4c894c2420"}, .br_stop = {0x833540, "4489442418"}, .br_pos = {0x82F460, "4489442418"},
    .guobjectarray = 0x3F75020,
    .po_a1 = {0x3DD126, "4c8d81940300004f8d04f0"}, .po_a2 = {0x3DD138, "4c8d810c0500004f8d04f0"},
    .po_b1 = {0x3DD386, "4c8d819c0400004f8d04f0"}, .po_b2 = {0x3DD398, "4c8d81140600004f8d04f0"},
    .restore_present_index = 0x2E,
    .vs1 = {0x61BFB6, "83f82f7d2a"}, .vs2 = {0x61BFE9, "83f82f7d30"}, .vs3 = {0x61C022, "83f82f7d30"},
    .vs_t = {0x61BFBB, 0x61BFE5, 0x61BFEE, 0x61C01E, 0x61C027, 0x61C057},
    .vsofs = {0x6B7760, "0fb6024883c025"},
    .area = {0x3E5730, "f20f1002f20f118150020000"},
},
{
    .name = "shipping (RED-Win64-Shipping.exe, 2026-04-21, 48 characters; requires EAC)",
    .table_entries = 48, .mask_main = 0x2D, .mask_alt = 0x26, .mask_extra_first = 45,
    .chara_table = 0x2C512E0,
    .idtocode_lea = {0x4FC29D, "488d353c507502"}, .idtocode_cmp = {0x4FC2BA, "83f930"},
    .codetoid_lea = {0x4FC3A2, "4c8d3d3f4f7502"}, .codetoid_cmp = {0x4FC45F, "4183fe30"},
    .codetoid_lea2 = {0x4FC475, "488d0d644e7502"},
    .mask_main_tab = 0x3850B50, .mask_alt_tab = 0x3850C00,
    .m_main_cmp = {0x3DFBAE, "80fa2d7206"}, .m_main_lea = {0x3DFBBC, "488d0d8d0f4703"},
    .m_alt_cmp = {0x3DFB1E, "80fa267206"}, .m_alt_lea = {0x3DFB2C, "488d0dcd104703"},
    .m_main_cmp7 = {0x3DE647, "80fa2d7207"}, .m_main_idx = {0x3DE656, "420fb68430500b8503"},
    .m_alt_cmp7 = {0x3DE307, "80fa267207"}, .m_alt_idx = {0x3DE316, "420fb68430000c8503"},
    .isvalid = {0x507700, "40574883ec208bf983f92f7508"},
    .hover1 = {0x3DD8F5, "83ff2f0f8df1000000"}, .hover2 = {0x3DD93E, "83ff2f7d12"},
    .hover3 = {0x3DDB85, "83ff2f0f8df1000000"}, .hover4 = {0x3DDBCE, "83ff2f7d12"},
    .stored = {0x6C1D30, "488bd93c307219"},
    .s2a4 = {0x6BEAE2, "80bfa40200002f488b8f800200007219"},
    .cnt1 = {0x553550, "8378fc2e7f02"}, .cnt2 = {0x553558, "83382e7f02"}, .cnt3 = {0x55355F, "8378042e7f02"},
    .setup_dmy = {0x5540F6, "83fa2f0f8d37010000"}, .setup_real = {0x55427A, "83fa2e7f65"},
    .setup_u = {0x54E95E, "4183fd2f0f83ff020000"},
    .fill1 = {0x52AB1D, "83f8307217"}, .fill2 = {0x52AB3E, "83f830733b"},
    .t = {
        [T_ISVALID_DMY] = 0x50770D, [T_ISVALID_GO] = 0x507715,
        [T_HOVER1_OK] = 0x3DD8FE, [T_HOVER1_BAD] = 0x3DD9EF,
        [T_HOVER2_OK] = 0x3DD943, [T_HOVER2_BAD] = 0x3DD955,
        [T_HOVER3_OK] = 0x3DDB8E, [T_HOVER3_BAD] = 0x3DDC7F,
        [T_HOVER4_OK] = 0x3DDBD3, [T_HOVER4_BAD] = 0x3DDBE5,
        [T_STORED_OK] = 0x6C1D50, [T_STORED_BAD] = 0x6C1D37,
        [T_2A4_OK] = 0x6BEB0B, [T_2A4_BAD] = 0x6BEAF2,
        [T_CNT1_OK] = 0x553556, [T_CNT1_BAD] = 0x553558,
        [T_CNT2_OK] = 0x55355D, [T_CNT2_BAD] = 0x55355F,
        [T_CNT3_OK] = 0x553565, [T_CNT3_BAD] = 0x553567,
        [T_SETUP_DMY_OK] = 0x5540FF, [T_SETUP_DMY_BAD] = 0x554236,
        [T_SETUP_REAL_OK] = 0x55427F, [T_SETUP_REAL_BAD] = 0x5542E4,
        [T_SETUP_U_OK] = 0x54E968, [T_SETUP_U_BAD] = 0x54EC67,
        [T_FILL1_OK] = 0x52AB39, [T_FILL1_BAD] = 0x52AB22,
        [T_FILL2_OK] = 0x52AB43, [T_FILL2_BAD] = 0x52AB7E,
        [T_UI_GUIDE_RESUME] = 0x548247, [T_UI_ANNOUNCE_RESUME] = 0x548E27,
    },
    .static_find = 0xBB30A0, .static_load = 0xBB4270, .texture_class = 0x24BFC70,
    .portrait1 = {0x3DD456, "e8455c7d00"}, .portrait2 = {0x3DD6B6, "e8e5597d00"},
    .ui_guide = {0x54823F, "f30f5835e5057302"}, .ui_announce = {0x548E1E, "f3440f580505fa7202"},
    .announce_obj = 0x3D25740,
    .vsofs = {0x6B7940, "0fb6024883c025"},
    .area = {0x3E5AC0, "f20f1002f20f118150020000"},
},
};
#define NPROFILES (int)(sizeof PROFILES / sizeof *PROFILES)
