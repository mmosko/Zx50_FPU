"""Opcode matcher and dictionary dispatcher for IEEE-754 test vectors."""

from typing import Dict, Optional, Tuple
from fpu_emu.rom.fpu_rom_map import USER_OPCODE_MAP
from fpu_emu.tests.integration.ieee754.vector_parser import TestVector
from fpu_emu.user_opcodes import UserOpcode


# Mapping from (precision_bits, operation_symbol) to UserOpcode defined in ProgrammersGuide
VECTOR_OPCODE_MAP: Dict[Tuple[int, str], UserOpcode] = {
    # 32-bit Single-Precision
    (32, "+"): UserOpcode.ADD_F32,
    (32, "-"): UserOpcode.SUB_F32,
    (32, "*"): UserOpcode.MUL_F32,
    (32, "/"): UserOpcode.DIV_F32,
    (32, "V"): UserOpcode.SQRT_F32,
    (32, "~"): UserOpcode.CHS_F32,
    (32, "A"): UserOpcode.ABS_F32,
    (32, "b64cff"): UserOpcode.CONV_F32_F64,

    # 64-bit Double-Precision
    (64, "+"): UserOpcode.ADD_F64,
    (64, "-"): UserOpcode.SUB_F64,
    (64, "*"): UserOpcode.MUL_F64,
    (64, "/"): UserOpcode.DIV_F64,
    (64, "V"): UserOpcode.SQRT_F64,
    (64, "~"): UserOpcode.CHS_F64,
    (64, "A"): UserOpcode.ABS_F64,
    (64, "b32cff"): UserOpcode.CONV_F64_F32,
}

# Operations that are currently stubbed as pass-through (if any)
STUBBED_OPCODES: set[UserOpcode] = set()


def is_stubbed_pass_through(opcode: UserOpcode) -> bool:
    """Returns True if the opcode is stubbed out as a pass-through."""
    return opcode in STUBBED_OPCODES


def is_opcode_implemented(opcode: UserOpcode) -> bool:
    """Checks whether the opcode is available in the microcode ROM symbol table or stubbed."""
    if is_stubbed_pass_through(opcode):
        return True
    return opcode in USER_OPCODE_MAP


def match_test_vector(vector: TestVector) -> Optional[UserOpcode]:
    """
    Determines if a test vector corresponds to an implemented ProgrammersGuide opcode.

    Returns the corresponding UserOpcode if:
    1. The precision and operation map to a ProgrammersGuide floating-point opcode.
    2. The rounding mode matches the Zx50 FPU hardware default (=0, nearest ties to even).
    3. The opcode is implemented in microcode (or stubbed as pass-through).

    Returns None if unsupported, unimplemented, or using an unsupported rounding mode.
    """
    # Zx50 FPU currently supports standard IEEE-754 round-to-nearest (=0)
    if vector.rounding_mode != "=0":
        return None

    key = (vector.precision, vector.operation_name)
    opcode = VECTOR_OPCODE_MAP.get(key)
    if opcode is None:
        return None

    if not is_opcode_implemented(opcode):
        return None

    return opcode
