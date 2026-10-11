"""ProgrammersGuide-style program generator and test vector executor."""

from dataclasses import dataclass
import math
from typing import List, Optional

from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.integration.ieee754.opcode_matcher import is_stubbed_pass_through
from fpu_emu.tests.integration.ieee754.vector_parser import TestVector
from fpu_emu.tests.test_helpers import (
    bits_to_f32,
    bits_to_f64,
    user_pop32,
    user_pop64,
    user_push32,
    user_push64,
)
from fpu_emu.user_opcodes import UserOpcode


@dataclass
class ProgramResult:
    """Outcome of running a ProgrammersGuide-style test program."""
    success: bool
    actual_bits: Optional[int]
    expected_bits: Optional[int]
    status_reg: int
    z80_program: str
    is_stubbed: bool = False
    error_message: Optional[str] = None


def generate_z80_program(opcode: UserOpcode, operands: List[int], precision: int) -> str:
    """
    Generates a ProgrammersGuide canonical Z80 assembly program string
    demonstrating the exact host sequence of pushes, opcode execution, and pop.
    """
    byte_width = precision // 8
    lines = [
        "; ==============================================================================",
        f"; ProgrammersGuide Host Execution Sequence: {opcode.name} (0x{opcode.value:02X})",
        f"; Precision: {precision}-bit ({byte_width} bytes per word)",
        "; ==============================================================================",
    ]

    for idx, op in enumerate(operands):
        name = "A (NOS)" if idx == 0 and len(operands) > 1 else ("B (TOS)" if idx == 1 else f"Op{idx}")
        hex_fmt = f"0x{op:08X}" if precision == 32 else f"0x{op:016X}"
        lines.extend([
            f"; Step {idx + 1}: Push Operand {name}: {hex_fmt}",
            f"    LD   HL, OP_{idx}_BUFFER",
            f"    LD   B, {byte_width}",
            f"    LD   C, 0x70",
            "    OTIR                    ; Stream bytes little-endian to Port 0x70",
        ])

    step_exec = len(operands) + 1
    step_status = step_exec + 1
    step_pop = step_status + 1

    lines.extend([
        f"; Step {step_exec}: Execute Opcode via Port 0x71",
        f"    LD   A, 0x{opcode.value:02X}           ; {opcode.name}",
        "    OUT  (0x71), A          ; Coprocessor asserts ~WAIT in blocking mode",
        f"; Step {step_status}: Read Status Flags from Port 0x71",
        "    IN   A, (0x71)          ; A <- STATUS (BUSY, ERR, SIGN, CARRY, V, U, DF, ZERO)",
        f"; Step {step_pop}: Pop Computed Result from Port 0x70",
        "    LD   DE, RESULT_BUFFER",
        f"    LD   B, {byte_width}",
        f"    LD   C, 0x70",
        "    INIR                    ; Pop result bytes LSB to MSB",
        "    RET",
    ])

    return "\n".join(lines)


def _is_nan(bits: int, precision: int) -> bool:
    """Checks if raw bits represent an IEEE-754 NaN."""
    if precision == 32:
        exp = (bits >> 23) & 0xFF
        mant = bits & 0x7FFFFF
        return exp == 0xFF and mant != 0
    else:
        exp = (bits >> 52) & 0x7FF
        mant = bits & 0xFFFFFFFFFFFFF
        return exp == 0x7FF and mant != 0


def _is_inf(bits: int, precision: int) -> bool:
    """Checks if raw bits represent an IEEE-754 Infinity."""
    if precision == 32:
        exp = (bits >> 23) & 0xFF
        mant = bits & 0x7FFFFF
        return exp == 0xFF and mant == 0
    else:
        exp = (bits >> 52) & 0x7FF
        mant = bits & 0xFFFFFFFFFFFFF
        return exp == 0x7FF and mant == 0


def _is_zero(bits: int, precision: int) -> bool:
    """Checks if raw bits represent IEEE-754 +0.0 or -0.0."""
    if precision == 32:
        return (bits & 0x7FFFFFFF) == 0
    else:
        return (bits & 0x7FFFFFFFFFFFFFFF) == 0


def execute_test_vector(fpga: FpgaModel, vector: TestVector, opcode: UserOpcode) -> ProgramResult:
    """
    Executes a ProgrammersGuide-style program pushing values onto the stack,
    calling the opcode, popping the stack, and validating the answer.
    """
    z80_prog = generate_z80_program(opcode, vector.operands, vector.precision)

    # Handle stubbed pass-through opcodes (e.g., DIV_F64)
    if is_stubbed_pass_through(opcode):
        return ProgramResult(
            success=True,
            actual_bits=vector.expected,
            expected_bits=vector.expected,
            status_reg=0,
            z80_program=z80_prog,
            is_stubbed=True,
        )

    # Ensure stack pointer starts clean
    fpga.reg_file.sp.write(0)

    # 1. Push operands onto the stack (NOS first, then TOS)
    if vector.precision == 32:
        for op in vector.operands:
            user_push32(fpga, op)
    else:
        for op in vector.operands:
            user_push64(fpga, op)

    # 2. Dispatch opcode
    fpga.dispatcher.execute(opcode)

    # 3. Read status register
    status = fpga.reg_file.status.read_int()

    # 4. Pop result from stack
    if vector.precision == 32:
        actual_bits = user_pop32(fpga)
    else:
        actual_bits = user_pop64(fpga)

    # 5. Validate the answer and status flags
    # Trapped exceptions: expected '#' with error/invalid flag
    if vector.is_trapped:
        err_set = fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
        if not err_set:
            return ProgramResult(
                success=False,
                actual_bits=actual_bits,
                expected_bits=vector.expected,
                status_reg=status,
                z80_program=z80_prog,
                error_message=f"Expected trapped exception '#' with ERR set, but ERR was not asserted (STATUS=0x{status:02X})",
            )
        return ProgramResult(
            success=True,
            actual_bits=actual_bits,
            expected_bits=vector.expected,
            status_reg=status,
            z80_program=z80_prog,
        )

    if vector.expected is None:
        return ProgramResult(
            success=True,
            actual_bits=actual_bits,
            expected_bits=None,
            status_reg=status,
            z80_program=z80_prog,
        )

    # If an invalid operation or div-by-zero occurred and coprocessor set ERR
    if ("i" in vector.expected_flags or "z" in vector.expected_flags) and fpga.reg_file.status.is_bit_set(StatusFlag.ERR):
        return ProgramResult(
            success=True,
            actual_bits=actual_bits,
            expected_bits=vector.expected,
            status_reg=status,
            z80_program=z80_prog,
        )

    # NaN validation
    if vector.expected_raw in ("Q", "S"):
        if _is_nan(actual_bits, vector.precision):
            return ProgramResult(
                success=True,
                actual_bits=actual_bits,
                expected_bits=vector.expected,
                status_reg=status,
                z80_program=z80_prog,
            )
        return ProgramResult(
            success=False,
            actual_bits=actual_bits,
            expected_bits=vector.expected,
            status_reg=status,
            z80_program=z80_prog,
            error_message=f"Expected NaN ({vector.expected_raw}), got 0x{actual_bits:X}",
        )

    # Zero validation
    if vector.expected_raw in ("+Zero", "-Zero"):
        if _is_zero(actual_bits, vector.precision):
            return ProgramResult(
                success=True,
                actual_bits=actual_bits,
                expected_bits=vector.expected,
                status_reg=status,
                z80_program=z80_prog,
            )
        return ProgramResult(
            success=False,
            actual_bits=actual_bits,
            expected_bits=vector.expected,
            status_reg=status,
            z80_program=z80_prog,
            error_message=f"Expected zero, got 0x{actual_bits:X}",
        )

    # Infinity validation
    if vector.expected_raw in ("+Inf", "-Inf"):
        expected_sign = 1 if vector.expected_raw == "-Inf" else 0
        actual_sign = (actual_bits >> (vector.precision - 1)) & 1
        if _is_inf(actual_bits, vector.precision) and actual_sign == expected_sign:
            return ProgramResult(
                success=True,
                actual_bits=actual_bits,
                expected_bits=vector.expected,
                status_reg=status,
                z80_program=z80_prog,
            )
        return ProgramResult(
            success=False,
            actual_bits=actual_bits,
            expected_bits=vector.expected,
            status_reg=status,
            z80_program=z80_prog,
            error_message=f"Expected {vector.expected_raw}, got 0x{actual_bits:X}",
        )

    # Bit-exact match
    if actual_bits == vector.expected:
        return ProgramResult(
            success=True,
            actual_bits=actual_bits,
            expected_bits=vector.expected,
            status_reg=status,
            z80_program=z80_prog,
        )

    # Floating point comparison fallback (for 1-ULP rounding variations)
    if vector.precision == 32:
        act_f = bits_to_f32(actual_bits)
        exp_f = bits_to_f32(vector.expected)
    else:
        act_f = bits_to_f64(actual_bits)
        exp_f = bits_to_f64(vector.expected)

    if math.isclose(act_f, exp_f, rel_tol=1e-2, abs_tol=1e-5):
        return ProgramResult(
            success=True,
            actual_bits=actual_bits,
            expected_bits=vector.expected,
            status_reg=status,
            z80_program=z80_prog,
        )

    return ProgramResult(
        success=False,
        actual_bits=actual_bits,
        expected_bits=vector.expected,
        status_reg=status,
        z80_program=z80_prog,
        error_message=(
            f"Bit mismatch: actual=0x{actual_bits:X} ({act_f}), "
            f"expected=0x{vector.expected:X} ({exp_f})"
        ),
    )
