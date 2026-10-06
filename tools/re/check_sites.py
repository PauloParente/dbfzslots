"""Confere se os bytes esperados de cada ponto de patch estao nos RVAs, em um ou mais .exe."""
import sys
from pe import PE

# (nome, rva, bytes esperados em hex) -- rip-relativos incluidos: mudam se o layout mudar
SITES = [
    ("chara_table[0].code->GKS", 0x2C512E0, "0000000000000000"),
    ("IdToCode lea rsi", 0x4FC29D, "488d353c507502"),
    ("IdToCode cmp ecx,30", 0x4FC2BA, "83f930"),
    ("CodeToId lea r15", 0x4FC3A2, "4c8d3d3f4f7502"),
    ("CodeToId cmp r14d,30", 0x4FC45F, "4183fe30"),
    ("CodeToId lea rcx", 0x4FC475, "488d0d644e7502"),
    ("mask45 cmp", 0x3DFBAE, "80fa2d7206"),
    ("mask45 lea", 0x3DFBBC, "488d0d8d0f4703"),
    ("mask38 cmp", 0x3DFB1E, "80fa267206"),
    ("mask38 lea", 0x3DFB2C, "488d0dcd104703"),
    ("mask45 cmp7", 0x3DE647, "80fa2d7207"),
    ("mask45 idx", 0x3DE656, "420fb68430500b8503"),
    ("mask38 cmp7", 0x3DE307, "80fa267207"),
    ("mask38 idx", 0x3DE316, "420fb68430000c8503"),
    ("IsCharaValid", 0x507700, "40574883ec208bf983f92f7508"),
    ("hover1", 0x3DD8F5, "83ff2f0f8df1000000"),
    ("hover2", 0x3DD93E, "83ff2f7d12"),
    ("hover3", 0x3DDB85, "83ff2f0f8df1000000"),
    ("hover4", 0x3DDBCE, "83ff2f7d12"),
    ("stored id", 0x6C1D30, "488bd93c307219"),
    ("stored 2a4", 0x6BEAE2, "80bfa40200002f488b8f800200007219"),
    ("team -4", 0x553550, "8378fc2e7f02"),
    ("team 0", 0x553558, "83382e7f02"),
    ("team +4", 0x55355F, "8378042e7f02"),
    ("setup edx2f", 0x5540F6, "83fa2f0f8d37010000"),
    ("setup edx2e", 0x55427A, "83fa2e7f65"),
    ("setup r13d", 0x54E95E, "4183fd2f0f83ff020000"),
    ("fill jb", 0x52AB1D, "83f8307217"),
    ("fill jae", 0x52AB3E, "83f830733b"),
    ("StaticFindObject", 0xBB30A0, "48895c2408"),
    ("StaticLoadObject", 0xBB4270, "40555356415441554156415748"),
    ("UTexture2D::StaticClass", 0x24BFC70, "4881ec98000000"),
    ("portrait find 1", 0x3DD456, "e8455c7d00"),
    ("portrait find 2", 0x3DD6B6, "e8e5597d00"),
    ("help guide addss", 0x54823F, "f30f5835e5057302"),
    ("help announce addss", 0x548E1E, "f3440f580505fa7202"),
    ("announce getter lea", 0x53AD89, "488d05b0a97e03"),
]

def check(path):
    p = PE(path)
    bad = 0
    for name, rva, hexb in SITES:
        want = bytes.fromhex(hexb)
        have = p.read(rva, len(want))
        if name.startswith("chara_table"):
            ptr = int.from_bytes(p.read(rva + 8, 8), "little")
            ok = p.wstr(ptr - p.image_base, 4) == "GKS"
        else:
            ok = have == want
        bad += not ok
        if not ok:
            print(f"  [DIFERENTE] {name:26} {rva:#x}: tem {have.hex() if have else None}, esperado {hexb}")
    print(f"  {len(SITES) - bad}/{len(SITES)} pontos conferem")
    return bad

if __name__ == "__main__":
    exes = sys.argv[1:] or [
        r"C:\dbfz modded\game\RED\Binaries\Win64\RED-Win64-Shipping.exe",
        r"C:\dbfz modded\game\RED\Binaries\Win64\RED-Win64-Shipping-eac-nop-loaded.exe",
    ]
    total = 0
    for e in exes:
        print(e)
        total += check(e)
    sys.exit(1 if total else 0)
