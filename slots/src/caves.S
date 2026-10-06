// Caves alcancadas a partir do jogo por stubs proximos (ver hook() em slots.c).
// Baseado em caves.S do DBFZ-ExtrasCustomSlots-XboxPC (MrPopulutus, MIT), generalizado:
// as constantes do roster vem de variaveis (g_dmy, g_max, ...) em vez de imediatos,
// para o mesmo codigo servir a builds com 47 ou 48 personagens.
//
// "real" = personagem jogavel: id < DMY (como o jogo checava) ou id extra.
// Cada cave termina em jmp qword ptr [g_t + 8*i] (destinos absolutos no jogo).
    .intel_syntax noprefix
    .text

// IsCharaValid(ecx=id): extras -> true; senao, o prologo original.
    .globl cave_isvalid
cave_isvalid:
    cmp ecx, dword ptr [rip + g_first_extra]
    jb 1f
    cmp ecx, dword ptr [rip + g_extra_end]
    jae 1f
    mov al, 1
    ret
1:  push rdi
    sub rsp, 0x20
    mov edi, ecx
    cmp ecx, dword ptr [rip + g_dmy]
    jne 2f
    jmp qword ptr [rip + g_t + 8*0]
2:  jmp qword ptr [rip + g_t + 8*1]

// Checagem com sinal "reg < DMY ou extra" (originais: cmp reg,DMY/jge bad e cmp reg,DMY-1/jg bad).
.macro REAL_S reg, ok, bad
    cmp \reg, dword ptr [rip + g_dmy]
    jl 8f
    cmp \reg, dword ptr [rip + g_first_extra]
    jl 9f
    cmp \reg, dword ptr [rip + g_extra_end]
    jge 9f
8:  jmp qword ptr [rip + g_t + 8*\ok]
9:  jmp qword ptr [rip + g_t + 8*\bad]
.endm

// Variante sem sinal (original: cmp reg,DMY / jae bad).
.macro REAL_U reg, ok, bad
    cmp \reg, dword ptr [rip + g_dmy]
    jb 8f
    cmp \reg, dword ptr [rip + g_first_extra]
    jb 9f
    cmp \reg, dword ptr [rip + g_extra_end]
    jae 9f
8:  jmp qword ptr [rip + g_t + 8*\ok]
9:  jmp qword ptr [rip + g_t + 8*\bad]
.endm

// Hover/confirmar na tela de selecao (cmp edi,DMY / jge bad).
    .globl cave_hover1
cave_hover1: REAL_S edi, 2, 3
    .globl cave_hover2
cave_hover2: REAL_S edi, 4, 5
    .globl cave_hover3
cave_hover3: REAL_S edi, 6, 7
    .globl cave_hover4
cave_hover4: REAL_S edi, 8, 9

// ID guardado: mov rbx,rcx / cmp al,MAX / jb ok.
    .globl cave_stored
cave_stored:
    mov rbx, rcx
    push rax
    movzx eax, al
    cmp eax, dword ptr [rip + g_max]
    jb 7f
    cmp eax, dword ptr [rip + g_first_extra]
    jb 6f
    cmp eax, dword ptr [rip + g_extra_end]
    jae 6f
7:  pop rax
    jmp qword ptr [rip + g_t + 8*10]
6:  pop rax
    jmp qword ptr [rip + g_t + 8*11]

// cmp byte [rdi+0x2a4],DMY / mov rcx,[rdi+0x280] / jb ok
// (nesta build o compilador intercalou o mov entre o cmp e o jb).
    .globl cave_2a4
cave_2a4:
    push rax
    movzx eax, byte ptr [rdi + 0x2a4]
    mov rcx, qword ptr [rdi + 0x280]
    cmp eax, dword ptr [rip + g_dmy]
    jb 7f
    cmp eax, dword ptr [rip + g_first_extra]
    jb 6f
    cmp eax, dword ptr [rip + g_extra_end]
    jae 6f
7:  pop rax
    jmp qword ptr [rip + g_t + 8*12]
6:  pop rax
    jmp qword ptr [rip + g_t + 8*13]

// Montagem da batalha: conta membros com personagem real
// (cmp dword [rax+d], DMY-1 / jg skip; nesta build a base e rax, contador em [rdx]).
.macro COUNT_SITE disp, ok, bad
    push rcx
    mov ecx, dword ptr [rax + \disp]
    cmp ecx, dword ptr [rip + g_dmy]
    jl 7f
    cmp ecx, dword ptr [rip + g_first_extra]
    jl 6f
    cmp ecx, dword ptr [rip + g_extra_end]
    jge 6f
7:  pop rcx
    jmp qword ptr [rip + g_t + 8*\ok]
6:  pop rcx
    jmp qword ptr [rip + g_t + 8*\bad]
.endm
    .globl cave_cnt1
cave_cnt1: COUNT_SITE -4, 14, 15
    .globl cave_cnt2
cave_cnt2: COUNT_SITE 0, 16, 17
    .globl cave_cnt3
cave_cnt3: COUNT_SITE 4, 18, 19

// Montagem da batalha: cmp edx,DMY/jge ; cmp edx,DMY-1/jg ; cmp r14d|r13d,DMY/jae.
    .globl cave_setup_dmy
cave_setup_dmy: REAL_S edx, 20, 21
    .globl cave_setup_real
cave_setup_real: REAL_S edx, 22, 23
    .globl cave_setup_u_r14
cave_setup_u_r14: REAL_U r14d, 24, 25
    .globl cave_setup_u_r13
cave_setup_u_r13: REAL_U r13d, 24, 25

// Preenchimento do setup: ids >= MAX viravam DMY.
// fill1: cmp eax,MAX / jb set     fill2: cmp eax,MAX / jae dmy
.macro BELOW_MAX_U reg, ok, bad
    cmp \reg, dword ptr [rip + g_max]
    jb 8f
    cmp \reg, dword ptr [rip + g_first_extra]
    jb 9f
    cmp \reg, dword ptr [rip + g_extra_end]
    jae 9f
8:  jmp qword ptr [rip + g_t + 8*\ok]
9:  jmp qword ptr [rip + g_t + 8*\bad]
.endm
    .globl cave_fill1
cave_fill1: BELOW_MAX_U eax, 26, 27
    .globl cave_fill2
cave_fill2: BELOW_MAX_U eax, 28, 29

// ---- barra de ajuda (portado de selector_ui.S do port Xbox) -----------------------
// Substitui "addss reg,[764.0]". Sobe a barra so enquanto o anuncio esta visivel
// (+0 == 1) e a chave ASCII em +0x24 comeca com CHARASELECT_ ou COLORSELECT_.
.macro UI_ADJUST reg, resume
    addss \reg, dword ptr [rip + ui_original_base]
    pushfq
    push rax
    mov rax, qword ptr [rip + ui_announce]
    test rax, rax
    jz 9f
    cmp dword ptr [rax], 1
    jne 9f
    cmp dword ptr [rax + 0x24], 0x52414843 // CHAR
    jne 2f
    cmp dword ptr [rax + 0x28], 0x4c455341 // ASEL
    jne 9f
    jmp 3f
2:  cmp dword ptr [rax + 0x24], 0x4f4c4f43 // COLO
    jne 9f
    cmp dword ptr [rax + 0x28], 0x4c455352 // RSEL
    jne 9f
3:  cmp dword ptr [rax + 0x2c], 0x5f544345 // ECT_
    jne 9f
    subss \reg, dword ptr [rip + ui_top_shift]
9:  pop rax
    popfq
    jmp qword ptr [rip + g_t + 8*\resume]
.endm
    .globl ui_guide_cave
ui_guide_cave: UI_ADJUST xmm6, 30
    .globl ui_announce_cave
ui_announce_cave: UI_ADJUST xmm8, 31

// ---- pontes nativo -> blueprint da grade (camada de icones) -----------------------
// Indices do exe: personagens 0..44, extras 45..R-1, random R (= g_rand_alias).
// Indices do blueprint: personagens 0..44, random 45 (g_bp_random), extras 46..R.
.macro XLATE reg
    cmp \reg, dword ptr [rip + g_rand_alias]
    jne 1f
    mov \reg, dword ptr [rip + g_bp_random]
    jmp 3f
1:  cmp \reg, dword ptr [rip + g_bp_random]
    jb 3f
    cmp \reg, dword ptr [rip + g_rand_alias]
    jae 3f
    inc \reg
3:
.endm
    .globl br_disp_cave
br_disp_cave:
    XLATE edx
    mov byte ptr [rsp + 0x18], r8b
    jmp qword ptr [rip + g_t + 8*32]
    .globl br_sel_cave
br_sel_cave:
    XLATE edx
    mov byte ptr [rsp + 0x18], r8b
    jmp qword ptr [rip + g_t + 8*33]
    .globl br_img_cave
br_img_cave:
    XLATE edx
    mov qword ptr [rsp + 0x18], r8
    jmp qword ptr [rip + g_t + 8*34]
    .globl br_play_cave
br_play_cave:
    XLATE r8d
    mov qword ptr [rsp + 0x20], r9
    jmp qword ptr [rip + g_t + 8*35]
    .globl br_stop_cave
br_stop_cave:
    XLATE r8d
    mov dword ptr [rsp + 0x18], r8d
    jmp qword ptr [rip + g_t + 8*36]
    .globl br_pos_cave
br_pos_cave:
    XLATE r8d
    mov dword ptr [rsp + 0x18], r8d
    jmp qword ptr [rip + g_t + 8*37]

// ---- enquadramento do retrato grande (arrays por personagem no widget BG) ---------------
// original: lea r8,[rcx+DISP] / lea r8,[r8+r14*8]; aqui o indice e g_alias[r14].
// o deslocamento do array no widget (lea r8,[rcx+DISP] original) vem dos bytes do proprio
// exe (g_po_disp, preenchido na instalacao): builds com outro numero de personagens o mudam
.macro PORTRAIT_OFS idx, ret
    lea r8, [rip + g_alias]
    movzx r8d, byte ptr [r8 + r14]
    lea r8, [rcx + r8*8]
    push rax
    mov rax, qword ptr [rip + g_po_disp + 8*\idx]
    lea r8, [r8 + rax]
    pop rax
    jmp qword ptr [rip + g_t + 8*\ret]
.endm
    .globl po_a1_cave
po_a1_cave: PORTRAIT_OFS 0, 38
    .globl po_a2_cave
po_a2_cave: PORTRAIT_OFS 1, 39
    .globl po_b1_cave
po_b1_cave: PORTRAIT_OFS 2, 40
    .globl po_b2_cave
po_b2_cave: PORTRAIT_OFS 3, 41

// ---- tela de VS: deslocamento do retrato (xoffset/yoffset) ---------------------------
// original: cmp eax,MAX / jge pula. Ids validos seguem; extras (e o restaurado) usam o
// indice do personagem-base (g_alias); o resto continua pulando.
.macro VS_OFS ok, skip
    cmp eax, dword ptr [rip + g_max]
    jl 8f
    cmp eax, dword ptr [rip + g_first_extra]
    jl 9f
    cmp eax, dword ptr [rip + g_extra_end]
    jge 9f
    push rcx
    lea rcx, [rip + g_alias]
    movzx eax, byte ptr [rcx + rax]
    pop rcx
8:  jmp qword ptr [rip + g_t + 8*\ok]
9:  jmp qword ptr [rip + g_t + 8*\skip]
.endm
    .globl vs1_cave
vs1_cave: VS_OFS 42, 43
    .globl vs2_cave
vs2_cave: VS_OFS 44, 45
    .globl vs3_cave
vs3_cave: VS_OFS 46, 47

// tela de VS/carregamento: GetOffsetXY(id) -> this + (g_alias[id] + 0x25) * 16
// (era movzx eax, byte ptr [rdx] / add rax, 0x25; r9 e volatil e nao e usado pela funcao)
    .globl vsofs_cave
vsofs_cave:
    movzx eax, byte ptr [rdx]
    lea r9, [rip + g_alias]
    movzx eax, byte ptr [r9 + rax]
    add rax, 0x25
    jmp qword ptr [rip + g_t + 8*48]
