# RVAs da versao Steam (RED-Win64-Shipping.exe)

Build analisada: `RED-Win64-Shipping.exe`, 184.261.120 bytes, modificado em 2026-04-21,
sha256 com prefixo `fc8c87fd2f99e25d`. O `RED-Win64-Shipping-eac-nop-loaded.exe`
tem o mesmo codigo nos pontos testados (assinaturas dos plugins batem nos dois),
mas os RVAs abaixo foram medidos no `RED-Win64-Shipping.exe` e precisam ser
reconferidos no `-eac-nop-loaded` antes de usar (ver `tools/re/check_sites.py`).

Equivalencias com o port do Xbox (`reference/DBFZ-ExtrasCustomSlots-XboxPC/HOW-IT-WORKS.md`).

## Tabela ID <-> codigo

| O que | Xbox | Steam | Bytes Steam |
|---|---|---|---|
| tabela `{i32 id, pad, wchar_t*}` x48 | `0x30AFBF0` | `0x2C512E0` | 0x00 GKS .. 0x2E DGF, 0x2F DMY |
| IdToCode | `0x57EE00` | `0x4FC290` | |
| `lea rsi,[tabela]` | `0x57EE26` | `0x4FC29D` | `48 8d 35 3c 50 75 02` |
| `cmp ecx,0x30` | `0x57EE3A` | `0x4FC2BA` | `83 f9 30` |
| `lea r15,[tabela+8]` | `0x57EF31` | `0x4FC3A2` | `4c 8d 3d 3f 4f 75 02` |
| `cmp r14d,0x30` | `0x57EFFD` | `0x4FC45F` | `41 83 fe 30` |
| `lea rcx,[tabela]` | `0x57F019` | `0x4FC475` | `48 8d 0d 64 4e 75 02` |

## Mascara do cursor -> ID

| O que | Xbox | Steam |
|---|---|---|
| tabela m45 (0x2D entradas) | `0x41E7510` | `0x3850B50` |
| tabela m38 (0x26 entradas) | `0x41E75B8` | `0x3850C00` |
| `cmp dl,0x2d / jb` + `lea rcx,[m45]` | `0x455CAE` / `0x455CBC` | `0x3DFBAE` / `0x3DFBBC` |
| `cmp dl,0x26 / jb` + `lea rcx,[m38]` | `0x455C1E` / `0x455C2C` | `0x3DFB1E` / `0x3DFB2C` |
| `cmp dl,0x2d / jb` + `movzx eax,[rax+r14+m45]` | `0x454B97` / `0x454BA6` | `0x3DE647` / `0x3DE656` |
| `cmp dl,0x26 / jb` + `movzx eax,[rax+r14+m38]` | `0x454857` / `0x454866` | `0x3DE307` / `0x3DE316` |

## Checagens "personagem real"

| Site | Xbox | Steam | Bytes | ok -> | bad -> |
|---|---|---|---|---|---|
| IsCharaValid | `0x587830` | `0x507700` | `40 57 48 83 ec 20 8b f9 83 f9 2f 75 08` | `0x50770D` (id==DMY) | `0x507715` |
| hover 1 | `0x453F3F` | `0x3DD8F5` | `83 ff 2f 0f 8d f1 00 00 00` | `0x3DD8FE` | `0x3DD9EF` |
| hover 2 | `0x453F80` | `0x3DD93E` | `83 ff 2f 7d 12` | `0x3DD943` | `0x3DD955` |
| hover 3 | `0x4541DF` | `0x3DDB85` | `83 ff 2f 0f 8d f1 00 00 00` | `0x3DDB8E` | `0x3DDC7F` |
| hover 4 | `0x454220` | `0x3DDBCE` | `83 ff 2f 7d 12` | `0x3DDBD3` | `0x3DDBE5` |
| stored id | `0x74F5A0` | `0x6C1D30` | `48 8b d9 3c 30 72 19` | `0x6C1D50` | `0x6C1D37` |
| stored +0x2a4 | `0x74C4A3` | `0x6BEAE2` | `80 bf a4 02 00 00 2f` `48 8b 8f 80 02 00 00` `72 19` (mov intercalado!) | `0x6BEB0B` | `0x6BEAF2` |
| team count -4 | `0x5D4810` | `0x553550` | `83 78 fc 2e 7f 02` (base **rax**, nao rdx) | `0x553556` | `0x553558` |
| team count 0 | `0x5D4818` | `0x553558` | `83 38 2e 7f 02` | `0x55355D` | `0x55355F` |
| team count +4 | `0x5D481F` | `0x55355F` | `83 78 04 2e 7f 02` | `0x553565` | `0x553567` |
| setup edx 2f | `0x5D5436` | `0x5540F6` | `83 fa 2f 0f 8d 37 01 00 00` | `0x5540FF` | `0x554236` |
| setup edx 2e | `0x5D5605` | `0x55427A` | `83 fa 2e 7f 65` | `0x55427F` | `0x5542E4` |
| setup r13d | `0x5CFF1B` | `0x54E95E` | `41 83 fd 2f 0f 83 ff 02 00 00` | `0x54E968` | `0x54EC67` |
| fill jb | `0x5A9783` | `0x52AB1D` | `83 f8 30 72 17` | `0x52AB39` | `0x52AB22` |
| fill jae | `0x5A97AE` | `0x52AB3E` | `83 f8 30 73 3b` | `0x52AB43` | `0x52AB7E` |

## Engine / interface

| O que | Xbox | Steam | Nota |
|---|---|---|---|
| StaticFindObject | `0xC87930` | `0xBB30A0` | (cls, outer, name, exact) |
| StaticLoadObject | — | `0xBB4270` | (cls, outer, name, filename, flags, sandbox, bAllowReconciliation); substitui o LoadObject(FString) do Xbox |
| UTexture2D::StaticClass | `0x267A880` | `0x24BFC70` | |
| montador `CS_CharacterImage_%s` | `0x4A21D0` | `0x433CA0` | |
| retrato grande, call find 1 | `0x453A7C` | `0x3DD456` | `e8 45 5c 7d 00` |
| retrato grande, call find 2 | `0x453CEC` | `0x3DD6B6` | `e8 e5 59 7d 00` |
| barra de ajuda (guide) | `0x5C98CE` | `0x54823F` | `f3 0f 58 35 e5 05 73 02` = addss xmm6,[764.0]; resume +8 |
| barra de ajuda (announce) | `0x5CA236` | `0x548E1E` | `f3 44 0f 58 05 05 fa 72 02` = addss xmm8,[764.0]; resume +9 |
| singleton do anuncio | `0x46FA450` | `0x3D25740` | getter `0x53AD60`; setter `0x5411A0` grava +0x08=2, +0x24 chave, +0x60=1 — **layout de "visivel" a confirmar em jogo** |
| GUObjectArray | `0x4274390` | **a medir** | pegar do `UE4SS.log` no 1o teste |
| FString | 24 bytes | 24 bytes | `num` em +0x10 (igual ao Xbox) |

## Nao portados (so diagnostico no Xbox)

`0x5D4804` (log de IDs do time), `0x4A69D0` (LoadObject com caminho vazio),
`0x58E830/0x58E850` (log dos setters). Opcionais.
