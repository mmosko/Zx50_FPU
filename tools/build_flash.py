#!/usr/bin/env python3
"""
tools/build_flash.py
ZX50 FPU Flash ROM Generator & Serializer

Reads:
  - build/ucode.bin : Assembled microcode binary (EBR 0..5, 6144 bytes / 1536 words)
  - build/ucode.sym : Microcode symbol table for UserOpcode entry addresses

Defines:
  - UCODE_ROM_OFFSET = 0x0000 (Bytes 0x0000..0x17FF / Words 0..1535)
  - DATA_ROM_OFFSET  = 0x1800 (Bytes 0x1800..0x1FFF / Words 1536..2047)

Emits:
  - bin/fpu_flash.bin          : Unified 8 KB binary image (6144 B ucode + 2048 B data)
  - fpu_emu/rom/fpu_flash.bin  : Emulator copy of 8 KB binary
  - bin/fpu_code_rom.bin       : Split 6 KB Code ROM binary (6144 bytes)
  - bin/fpu_data_ram.bin       : Split 2 KB Data RAM initialization binary (2048 bytes)
  - sim/fpu_rom.hex            : Verilog $readmemh image (2048 words)
  - src/fpu_rom_map.vh         : Verilog header with offsets and jump table defines
  - fpu_emu/rom/fpu_rom_map.py: Python constants, RAM map, and USER_OPCODE_MAP
"""

import os
import struct
import sys
from typing import Dict, List, Tuple

# ROM Parameters & Base Addresses (8 KB Single Flash ROM: 2048 words x 32-bit)
FLASH_SIZE = 8192        # 8 KB active region
TOTAL_WORDS = 2048

UCODE_ROM_OFFSET = 0x0000  # Byte offset 0x0000 (Words 0..1535)
DATA_ROM_OFFSET = 0x1800   # Byte offset 0x1800 (Words 1536..2047)

UCODE_ROM_WORDS = 1536     # 6144 bytes / 4
DATA_RAM_WORDS = 512       # 2048 bytes / 4

# Data RAM Partition Word Offsets (within 512-word EBR 6)
DATA_RAM_MTH_BASE = 0x000   # Stack RAM: words 0..127 (128 words)
DATA_RAM_SCR_BASE = 0x080   # Scratchpad RAM: words 128..191 (64 words)
DATA_RAM_USR_BASE = 0x0C0   # User Storage: words 192..207 (16 words)
DATA_RAM_EXT_BASE = 0x0D0   # RAM Headroom: words 208..255 (48 words)
CONST_OFFSET = 0x100        # Math Constants Base: words 256..319 (64 words)

UCODE_BIN_FILE = "build/ucode.bin"
UCODE_SYM_FILE = "build/ucode.sym"

HEADER_FILE = "src/fpu_rom_map.vh"
HEX_FILE = "sim/fpu_rom.hex"
BIN_FILE = "bin/fpu_flash.bin"
EMU_BIN_FILE = "fpu_emu/rom/fpu_flash.bin"
SPLIT_CODE_FILE = "bin/fpu_code_rom.bin"
SPLIT_DATA_FILE = "bin/fpu_data_ram.bin"
PY_ROM_MAP_FILE = "fpu_emu/rom/fpu_rom_map.py"

# =============================================================================
# Mathematical Constants Definition (64 words: words 0..63 relative to CONST_OFFSET)
# =============================================================================
CONSTANTS_DEF: List[Tuple[str, int, int, int, str]] = [
    # (enum_name, slot, hex_val, num_bytes, description)
    # Mathematical Constants (0xA0..0xAF push opcodes)
    ("PI_F32", 0, 0x40490FDB, 4, "pi in IEEE-754 single precision"),
    ("PI_F64", 2, 0x400921FB54442D18, 8, "pi in IEEE-754 double precision"),
    ("E_F32", 4, 0x402DF854, 4, "e in IEEE-754 single precision"),
    ("E_F64", 6, 0x4005BF0A8B145769, 8, "e in IEEE-754 double precision"),
    ("LN2_F32", 8, 0x3F317218, 4, "ln(2) in IEEE-754 single precision"),
    ("LN2_F64", 10, 0x3FE62E42FEFA39EF, 8, "ln(2) in IEEE-754 double precision"),
    ("LOG2E_F32", 12, 0x3FB8AA3B, 4, "log2(e) in IEEE-754 single precision"),
    ("LOG2E_F64", 14, 0x3FF71547652B82FE, 8, "log2(e) in IEEE-754 double precision"),
    ("LOG2_10_F32", 16, 0x40549A78, 4, "log2(10) in IEEE-754 single precision"),
    ("LOG2_10_F64", 18, 0x400A934F0979A371, 8, "log2(10) in IEEE-754 double precision"),
    ("LOG10_2_F32", 20, 0x3E9A209B, 4, "log10(2) in IEEE-754 single precision"),
    ("LOG10_2_F64", 22, 0x3FD34413509F79FF, 8, "log10(2) in IEEE-754 double precision"),
    ("SQRT2_F32", 24, 0x3FB504F3, 4, "sqrt(2) in IEEE-754 single precision"),
    ("SQRT2_F64", 26, 0x3FF6A09E667F3BCD, 8, "sqrt(2) in IEEE-754 double precision"),
    ("SQRT2_F64_HI", 27, 0x3FF6A09E, 4, "high 32-bit word of sqrt(2) in IEEE-754 double precision"),
    ("INV_SQRT2_F32", 28, 0x3F3504F3, 4, "1/sqrt(2) in IEEE-754 single precision"),
    ("INV_SQRT2_F64", 30, 0x3FE6A09E667F3BCD, 8, "1/sqrt(2) in IEEE-754 double precision"),

    # IEEE-754 Special Constants
    ("ONE_F32", 32, 0x3F800000, 4, "1.0 in IEEE-754 single precision"),
    ("ONE_F64", 33, 0x3FF0000000000000, 8, "1.0 in IEEE-754 double precision"),
    ("ONE_F64_HI", 34, 0x3FF00000, 4, "high 32-bit word of 1.0 in IEEE-754 double precision"),
    ("NAN_F32", 35, 0x7FC00000, 4, "Quiet NaN in IEEE-754 single precision"),
    ("NAN_F64", 36, 0x7FF8000000000000, 8, "Quiet NaN in IEEE-754 double precision"),
    ("POS_INF_F32", 38, 0x7F800000, 4, "+Infinity in IEEE-754 single precision"),
    ("NEG_INF_F32", 39, 0xFF800000, 4, "-Infinity in IEEE-754 single precision"),
    ("POS_INF_F64", 40, 0x7FF0000000000000, 8, "+Infinity in IEEE-754 double precision"),
    ("NEG_INF_F64", 42, 0xFFF0000000000000, 8, "-Infinity in IEEE-754 double precision"),

    # Range Reduction Constants
    ("TWO_OVER_PI_F32", 44, 0x3F22F983, 4, "2/pi in IEEE-754 single precision"),
    ("TWO_OVER_PI_F64", 45, 0x3FE45F306DC9C883, 8, "2/pi in IEEE-754 double precision"),

    # Cody-Waite Split Constants
    ("CW_C1_F32", 47, 0x3FC90F80, 4, "Cody-Waite C1 in IEEE-754 single precision"),
    ("CW_C2_F32", 48, 0x37354443, 4, "Cody-Waite C2 in IEEE-754 single precision"),
    ("CW_C1_F64", 49, 0x3FF921FB54400000, 8, "Cody-Waite C1 in IEEE-754 double precision"),
    ("CW_C2_F64", 51, 0x3DD0B4611A626331, 8, "Cody-Waite C2 in IEEE-754 double precision"),
    ("CW_C3_F64", 53, 0x3BA3198A2E037073, 8, "Cody-Waite C3 in IEEE-754 double precision"),

    # Half and Scale Constants
    ("HALF_F64", 56, 0x3FE0000000000000, 8, "0.5 in IEEE-754 double precision"),
    ("HALF_F64_HI", 57, 0x3FE00000, 4, "high 32-bit word of 0.5 in IEEE-754 double precision"),

    # Natural Log of 10 Constants
    ("LN10_F32", 58, 0x40135D8E, 4, "ln(10) in IEEE-754 single precision"),
    ("LN10_F64", 60, 0x40026BB1BBB55516, 8, "ln(10) in IEEE-754 double precision"),

    # Magic Add Constant for Range Reduction (1.5 * 2^52)
    ("MAGIC_F64", 62, 0x4338000000000000, 8, "1.5 * 2^52 magic constant in IEEE-754 double precision"),
    ("MAGIC_F64_HI", 63, 0x43380000, 4, "high 32-bit word of MAGIC in IEEE-754 double precision"),
]


def load_ucode_bin(bin_path: str = UCODE_BIN_FILE) -> List[int]:
    """Reads 1536 32-bit words from microcode binary (padded with NOPs if needed)."""
    if not os.path.exists(bin_path):
        raise FileNotFoundError(f"Microcode binary not found: {bin_path}. Run fpu_asm first.")
    with open(bin_path, "rb") as f:
        data = f.read()

    num_words = len(data) // 4
    words = list(struct.unpack(f">{num_words}I", data[: num_words * 4]))
    if len(words) < UCODE_ROM_WORDS:
        # NOP instruction word: 0xE0000000
        words.extend([0xE0000000] * (UCODE_ROM_WORDS - len(words)))
    elif len(words) > UCODE_ROM_WORDS:
        raise ValueError(f"Microcode binary exceeds {UCODE_ROM_WORDS} words: {len(words)}")
    return words[:UCODE_ROM_WORDS]


def load_ucode_sym(sym_path: str = UCODE_SYM_FILE) -> Dict[str, int]:
    """Reads symbol table from assembler output (.sym)."""
    if not os.path.exists(sym_path):
        raise FileNotFoundError(f"Microcode symbol table not found: {sym_path}. Run fpu_asm first.")
    symbols: Dict[str, int] = {}
    with open(sym_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(";") or line.startswith("["):
                continue
            parts = line.split()
            if len(parts) >= 2:
                name = parts[0]
                try:
                    addr = int(parts[1], 16) if parts[1].startswith("0x") else int(parts[1])
                    symbols[name] = addr
                except ValueError:
                    pass
    return symbols


def generate_data_ram_words() -> List[int]:
    """Generates the 512 32-bit words for DATA_RAM (EBR 6).

    Words 0..255: 0 (Stack/Scratch/User/Ext RAM space)
    Words 256..319 (CONST_OFFSET = 0x100): 64 words of IEEE-754 Math Constants
    Words 320..511: 0 (Headroom)
    """
    words = [0] * DATA_RAM_WORDS
    for _, slot, hex_val, nbytes, _ in CONSTANTS_DEF:
        if nbytes == 4:
            words[CONST_OFFSET + slot] = hex_val & 0xFFFFFFFF
        elif nbytes == 8:
            words[CONST_OFFSET + slot] = hex_val & 0xFFFFFFFF
            words[CONST_OFFSET + slot + 1] = (hex_val >> 32) & 0xFFFFFFFF
    return words


def generate_flash_words(ucode_words: List[int], data_words: List[int]) -> List[int]:
    """Combines Code ROM (1536 words) and Data RAM (512 words) into 2048 words."""
    assert len(ucode_words) == UCODE_ROM_WORDS
    assert len(data_words) == DATA_RAM_WORDS
    return ucode_words + data_words


def write_verilog_header(header_path: str, symbols: Dict[str, int]) -> None:
    """Emits src/fpu_rom_map.vh with flash base offsets, RAM partition offsets, and opcode jump table."""
    os.makedirs(os.path.dirname(header_path), exist_ok=True)
    with open(header_path, "w") as f:
        f.write("/***************************************************************************************\n")
        f.write(" * FILE: src/fpu_rom_map.vh\n")
        f.write(" * DESCRIPTION: Auto-generated Flash ROM Address Map & Microcode Jump Table.\n")
        f.write(" * DO NOT EDIT MANUALLY - Generated by tools/build_flash.py\n")
        f.write(" ***************************************************************************************/\n\n")
        f.write("`ifndef FPU_ROM_MAP_VH\n`define FPU_ROM_MAP_VH\n\n")

        f.write("  // Flash Image 32-bit Word Base Offsets (8 KB total / 2048 words)\n")
        f.write(f"  `define FLASH_UCODE_ROM_BASE     13'h{UCODE_ROM_OFFSET:04X} // Bytes 0..6143 (Words 0..1535)\n")
        f.write(f"  `define FLASH_DATA_RAM_BASE      13'h{DATA_ROM_OFFSET:04X} // Bytes 6144..8191 (Words 1536..2047)\n\n")

        f.write("  // DATA_RAM Partition Word Offsets (within 512-word EBR 6)\n")
        f.write(f"  `define DATA_RAM_MTH_BASE        10'h{DATA_RAM_MTH_BASE:03X} // Stack RAM: words 0..127\n")
        f.write(f"  `define DATA_RAM_SCR_BASE        10'h{DATA_RAM_SCR_BASE:03X} // Scratchpad RAM: words 128..191\n")
        f.write(f"  `define DATA_RAM_USR_BASE        10'h{DATA_RAM_USR_BASE:03X} // User Storage: words 192..207\n")
        f.write(f"  `define DATA_RAM_EXT_BASE        10'h{DATA_RAM_EXT_BASE:03X} // Headroom: words 208..255\n")
        f.write(f"  `define DATA_RAM_CONST_BASE      10'h{CONST_OFFSET:03X} // Math Constants: words 256..319\n\n")

        f.write("  // FPU Constants Word Slot Map (relative to DATA_RAM_CONST_BASE)\n")
        for name, slot, _, _, _ in CONSTANTS_DEF:
            f.write(f"  `define CONST_SLOT_{name:<18} 6'd{slot}\n")
        f.write("\n")

        f.write("  // Microcode User Opcode Jump Table (Start PC in UCODE_ROM)\n")
        user_symbols = {k: v for k, v in symbols.items() if k.startswith("USER_")}
        for sym_name, addr in sorted(user_symbols.items()):
            op_name = sym_name[5:]  # Strip 'USER_'
            macro_name = f"USER_OP_{op_name}_PC"
            f.write(f"  `define {macro_name:<30} 11'd{addr}\n")
        f.write("\n")

        f.write("`endif // FPU_ROM_MAP_VH\n")


def write_python_rom_map(py_path: str, symbols: Dict[str, int]) -> None:
    """Emits fpu_emu/rom/fpu_rom_map.py with flash offsets, RAM partition map, and USER_OPCODE_MAP."""
    os.makedirs(os.path.dirname(py_path), exist_ok=True)

    # Import UserOpcode to validate mapping
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from fpu_emu.user_opcodes import UserOpcode

    with open(py_path, "w") as f:
        f.write('"""Auto-generated by tools/build_flash.py - DO NOT EDIT MANUALLY.\n\n')
        f.write("FPU Flash ROM Map, EBR Data RAM Partitions, and User Opcode Jump Table.\n")
        f.write('"""\n\n')
        f.write("from enum import IntEnum\n")
        f.write("from typing import Dict\n")
        f.write("from fpu_emu.user_opcodes import UserOpcode\n\n\n")

        f.write("class FpuFlashOffsets(IntEnum):\n")
        f.write('    """Flash ROM Byte Base Offsets (8 KB single flash image)."""\n')
        f.write(f"    UCODE_ROM_OFFSET = 0x{UCODE_ROM_OFFSET:04X}  # 6144 bytes / 1536 words (EBR 0..5)\n")
        f.write(f"    DATA_ROM_OFFSET = 0x{DATA_ROM_OFFSET:04X}   # 2048 bytes / 512 words (EBR 6..7)\n\n\n")

        f.write("class FpuTables(IntEnum):\n")
        f.write('    """Flash ROM Image Base Byte Addresses (backwards compatibility)."""\n')
        f.write(f"    UCODE_ROM = 0x{UCODE_ROM_OFFSET:04X}\n")
        f.write(f"    DATA_RAM = 0x{DATA_ROM_OFFSET:04X}\n\n\n")

        f.write("class FpuRamMap(IntEnum):\n")
        f.write('    """Memory partition word offsets within the 512-word Data RAM (EBR 6)."""\n')
        f.write(f"    MTH_BASE = 0x{DATA_RAM_MTH_BASE:03X}      # Stack RAM: words 0..127\n")
        f.write(f"    SCR_BASE = 0x{DATA_RAM_SCR_BASE:03X}      # Scratchpad RAM: words 128..191\n")
        f.write(f"    USR_BASE = 0x{DATA_RAM_USR_BASE:03X}      # User Storage: words 192..207\n")
        f.write(f"    EXT_BASE = 0x{DATA_RAM_EXT_BASE:03X}      # Headroom: words 208..255\n")
        f.write(f"    CONST_OFFSET = 0x{CONST_OFFSET:03X}  # Math Constants: words 256..319 (64 words)\n")
        f.write(f"    CNS_BASE = 0x{CONST_OFFSET:03X}      # Alias for CONST_OFFSET\n\n\n")

        f.write("class FpuTable(IntEnum):\n")
        f.write('    """Table identifier for LDC instruction (MicroOp.LDC)."""\n')
        f.write("    CONST = 0\n")
        f.write("    TRIG = 1\n")
        f.write("    CHEB = 2\n")
        f.write("    RECIP = 3\n")
        f.write("    SQRT = 4\n\n\n")

        f.write("class FpuConst(IntEnum):\n")
        f.write('    """FPU Constants Word Slot Map (relative to CONST_OFFSET)."""\n')
        for name, slot, _, _, desc in CONSTANTS_DEF:
            f.write(f"    {name} = {slot}  # {desc}\n")
        f.write("\n\n")

        # Map each UserOpcode to its start PC address
        f.write("USER_OPCODE_MAP: Dict[UserOpcode, int] = {\n")
        for op in UserOpcode:
            sym_name = f"USER_{op.name}"
            if sym_name in symbols:
                f.write(f"    UserOpcode.{op.name}: {symbols[sym_name]},\n")
        f.write("}\n")


def write_verilog_hex(hex_path: str, words: List[int]) -> None:
    """Writes 32-bit words in big-endian hex format (one 8-digit hex word per line)."""
    os.makedirs(os.path.dirname(hex_path), exist_ok=True)
    with open(hex_path, "w") as f:
        for w in words:
            f.write(f"{w:08X}\n")


def main() -> None:
    os.makedirs("bin", exist_ok=True)
    os.makedirs("sim", exist_ok=True)
    os.makedirs(os.path.dirname(EMU_BIN_FILE), exist_ok=True)

    # 1. Load microcode binary and symbol table
    ucode_words = load_ucode_bin(UCODE_BIN_FILE)
    symbols = load_ucode_sym(UCODE_SYM_FILE)

    # 2. Generate Data RAM image
    data_words = generate_data_ram_words()

    # 3. Combine into unified 8 KB flash image (2048 words)
    flash_words = generate_flash_words(ucode_words, data_words)

    # Pack binary images
    ucode_bin = struct.pack(f">{len(ucode_words)}I", *ucode_words)
    data_bin = struct.pack(f">{len(data_words)}I", *data_words)
    flash_bin = ucode_bin + data_bin

    # 4. Write output files
    with open(BIN_FILE, "wb") as f:
        f.write(flash_bin)

    with open(EMU_BIN_FILE, "wb") as f:
        f.write(flash_bin)

    with open(SPLIT_CODE_FILE, "wb") as f:
        f.write(ucode_bin)

    with open(SPLIT_DATA_FILE, "wb") as f:
        f.write(data_bin)

    write_verilog_hex(HEX_FILE, flash_words)
    write_verilog_header(HEADER_FILE, symbols)
    write_python_rom_map(PY_ROM_MAP_FILE, symbols)

    print(f"[*] Generated Unified Flash Image: {BIN_FILE} ({len(flash_bin)} bytes)")
    print(f"[*] Generated Emulator Copy:       {EMU_BIN_FILE} ({len(flash_bin)} bytes)")
    print(f"[*] Generated Split Code ROM:      {SPLIT_CODE_FILE} ({len(ucode_bin)} bytes)")
    print(f"[*] Generated Split Data RAM:      {SPLIT_DATA_FILE} ({len(data_bin)} bytes)")
    print(f"[*] Generated Simulation Hex:      {HEX_FILE} ({len(flash_words)} words)")
    print(f"[*] Generated Verilog Header:      {HEADER_FILE}")
    print(f"[*] Generated Python ROM Map:      {PY_ROM_MAP_FILE}")


if __name__ == "__main__":
    main()
