// Trampolim de teste (baseado em tests/callsite.S do port Xbox, MIT).
// uint32_t call_site(void *site, uint64_t rdi, uint64_t rax, uint64_t rdx, uint64_t r13r14)
// Windows x64: rcx=site rdx=rdi r8=rax r9=rdx [rsp+0x28]=r13 e r14
    .intel_syntax noprefix
    .text
    .globl call_site
call_site:
    push rbx
    push rdi
    push r13
    push r14
    push r12
    sub rsp, 0x20
    mov r12, rcx
    mov rdi, rdx
    mov rax, r8
    mov rdx, r9
    mov r13, qword ptr [rsp + 0x20 + 0x28 + 0x28]
    mov r14, r13
    call r12
    add rsp, 0x20
    pop r12
    pop r14
    pop r13
    pop rdi
    pop rbx
    ret
// destinos falsos: o "jmp [g_t+i]" da cave cai aqui, que retorna ao call_site
    .globl t_ok
t_ok: mov eax, 1
    ret
    .globl t_bad
t_bad: mov eax, 2
    ret

// uint32_t call_bridge(void *entry, uint32_t edx, uint32_t r8d): entra na ponte com os
// registros dados; o "jmp [g_t]" da cave cai em t_ret_edx/t_ret_r8d, que devolvem o valor.
    .globl call_bridge
call_bridge:
    mov rax, rcx
    jmp rax
    .globl t_ret_edx
t_ret_edx: mov eax, edx
    ret
    .globl t_ret_r8d
t_ret_r8d: mov eax, r8d
    ret
    .globl t_ret_r8_64
t_ret_r8_64: mov rax, r8
    ret
    .globl t_ret_rax
t_ret_rax: ret
    .globl t_skip
t_skip: mov eax, 0xffff
    ret
