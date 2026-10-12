"""Integration tests for 64-bit IEEE-754 double precision power (POW_F64)."""

import math
import tempfile
from pathlib import Path
from typing import Any

import pytest

from fpu_asm.assembler import Assembler
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.hardware.rom import Rom
from fpu_emu.tests.test_helpers import bits_to_f64, f64_to_bits, user_pop64, user_push64

POW_F64_SOURCE = """
.include "fpu_emu/asm/pop_two_64.asm"
.include "fpu_emu/asm/align_f64.asm"
.include "fpu_emu/asm/normalize_f64.asm"
.include "fpu_emu/asm/add_f64.asm"
.include "fpu_emu/asm/sub_f64.asm"
.include "fpu_emu/asm/mul_f64.asm"
.include "fpu_emu/asm/div_f64.asm"
.include "fpu_emu/asm/log2_f64.asm"
.include "fpu_emu/asm/exp2_f64.asm"
.include "fpu_emu/asm/pow_f64.asm"
"""


@pytest.fixture(scope="module")
def pow_f64_program() -> tuple[list[Any], int, Any]:
    """Assembles the POW_F64 microcode routine once for all tests in this module."""
    asm = Assembler()
    assembled = asm.assemble(POW_F64_SOURCE)
    instructions = [instr for _, instr in assembled]
    entry = asm.symbols["USER_POW_F64"]
    tmp_dir = tempfile.TemporaryDirectory()
    return instructions, entry, tmp_dir


@pytest.fixture
def fpga(pow_f64_program: tuple[list[Any], int, Any]) -> FpgaModel:
    """Creates a fresh FPGA model with an empty ROM."""
    _, _, tmp_dir = pow_f64_program
    rom = Rom(size=1024, rom_path=Path(tmp_dir.name) / "dummy.rom")
    return FpgaModel(rom=rom)


def run_pow_f64(
    fpga: FpgaModel,
    instructions: list[Any],
    entry: int,
    base: float,
    exp: float,
) -> tuple[float | None, int]:
    """Pushes base and exp (Forth: base exp -- base^exp) and executes USER_POW_F64."""
    user_push64(fpga, f64_to_bits(base))
    user_push64(fpga, f64_to_bits(exp))
    fpga.reg_file.upc.write(entry)
    fpga.dispatcher._run(instructions)
    st = fpga.reg_file.status.read_int()
    if fpga.reg_file.sp.read_int() >= 2:
        res = bits_to_f64(user_pop64(fpga))
        return res, st
    return None, st


@pytest.mark.parametrize(
    "base,exp,expected,desc",
    [
        # Identity powers: y^0 == 1.0
        (2.0, 0.0, 1.0, "2^0 = 1.0"),
        (10.0, 0.0, 1.0, "10^0 = 1.0"),
        (0.5, 0.0, 1.0, "0.5^0 = 1.0"),
        (1.0, 0.0, 1.0, "1^0 = 1.0"),
        (0.0, 0.0, 1.0, "0^0 = 1.0"),
        # Base 1.0: 1^x == 1.0
        (1.0, 1.0, 1.0, "1^1 = 1.0"),
        (1.0, 2.0, 1.0, "1^2 = 1.0"),
        (1.0, -2.0, 1.0, "1^-2 = 1.0"),
        (1.0, 0.5, 1.0, "1^0.5 = 1.0"),
        (1.0, 100.0, 1.0, "1^100 = 1.0"),
        # Base 0.0 with positive exponent: 0^x == 0.0
        (0.0, 1.0, 0.0, "0^1 = 0.0"),
        (0.0, 2.0, 0.0, "0^2 = 0.0"),
        (0.0, 0.5, 0.0, "0^0.5 = 0.0"),
        # Integer powers of 2
        (2.0, 1.0, 2.0, "2^1 = 2.0"),
        (2.0, 2.0, 4.0, "2^2 = 4.0"),
        (2.0, 3.0, 8.0, "2^3 = 8.0"),
        (2.0, 4.0, 16.0, "2^4 = 16.0"),
        (2.0, 8.0, 256.0, "2^8 = 256.0"),
        (2.0, -1.0, 0.5, "2^-1 = 0.5"),
        (2.0, -2.0, 0.25, "2^-2 = 0.25"),
        (2.0, -3.0, 0.125, "2^-3 = 0.125"),
        # Integer powers of other integers
        (3.0, 2.0, 9.0, "3^2 = 9.0"),
        (3.0, 3.0, 27.0, "3^3 = 27.0"),
        (10.0, 2.0, 100.0, "10^2 = 100.0"),
        (10.0, -2.0, 0.01, "10^-2 = 0.01"),
        (5.0, 3.0, 125.0, "5^3 = 125.0"),
        # Fractional powers (roots)
        (4.0, 0.5, 2.0, "4^0.5 = 2.0"),
        (9.0, 0.5, 3.0, "9^0.5 = 3.0"),
        (16.0, 0.25, 2.0, "16^0.25 = 2.0"),
        (2.0, 0.5, math.sqrt(2.0), "2^0.5 = sqrt(2)"),
        (8.0, 1.0 / 3.0, 2.0, "8^(1/3) = 2.0"),
        (27.0, 1.0 / 3.0, 3.0, "27^(1/3) = 3.0"),
        # General floating-point powers
        (1.5, 2.5, 1.5**2.5, "1.5^2.5"),
        (2.7, 1.8, 2.7**1.8, "2.7^1.8"),
        (0.5, 0.5, 0.5**0.5, "0.5^0.5"),
        (0.25, -1.5, 0.25**-1.5, "0.25^-1.5 = 8.0"),
    ],
)
def test_pow_f64_normals(
    fpga: FpgaModel,
    pow_f64_program: tuple[list[Any], int, Any],
    base: float,
    exp: float,
    expected: float,
    desc: str,
) -> None:
    """Verifies that POW_F64 computes base^exp with high precision."""
    instructions, entry, _ = pow_f64_program
    result, st = run_pow_f64(fpga, instructions, entry, base, exp)
    assert result is not None
    assert not bool(st & (1 << StatusFlag.ERR.value)), f"Unexpected ERR flag for {desc}"

    res_bits = f64_to_bits(result)
    expected_bits = f64_to_bits(expected)

    diff = abs(res_bits - expected_bits)
    assert diff <= 512, (
        f"{desc}: got {result} (0x{res_bits:016x}), "
        f"expected {expected} (0x{expected_bits:016x}), "
        f"diff = {diff} ULP"
    )


def test_pow_f64_negative_base_domain_error(
    fpga: FpgaModel, pow_f64_program: tuple[list[Any], int, Any]
) -> None:
    """Tests that negative base raises domain error (ERR=1)."""
    instructions, entry, _ = pow_f64_program
    result, st = run_pow_f64(fpga, instructions, entry, -2.0, 3.0)
    assert bool(st & (1 << StatusFlag.ERR.value))


def test_pow_f64_zero_negative_exp(
    fpga: FpgaModel, pow_f64_program: tuple[list[Any], int, Any]
) -> None:
    """Tests that 0^negative returns +inf and sets ERR=1, OVERFLOW=1."""
    instructions, entry, _ = pow_f64_program
    result, st = run_pow_f64(fpga, instructions, entry, 0.0, -2.0)
    assert result is not None
    assert math.isinf(result) and result > 0
    assert bool(st & (1 << StatusFlag.ERR.value))
    assert bool(st & (1 << StatusFlag.OVERFLOW.value))


def test_pow_f64_overflow(
    fpga: FpgaModel, pow_f64_program: tuple[list[Any], int, Any]
) -> None:
    """Tests that powers exceeding double limits overflow to +inf."""
    instructions, entry, _ = pow_f64_program
    result, st = run_pow_f64(fpga, instructions, entry, 2.0, 1024.0)
    assert result is not None
    assert math.isinf(result) and result > 0
    assert bool(st & (1 << StatusFlag.OVERFLOW.value))


def test_pow_f64_underflow(
    fpga: FpgaModel, pow_f64_program: tuple[list[Any], int, Any]
) -> None:
    """Tests that tiny powers underflow to +0.0."""
    instructions, entry, _ = pow_f64_program
    result, st = run_pow_f64(fpga, instructions, entry, 2.0, -1075.0)
    assert result is not None
    assert result == 0.0
    assert bool(st & (1 << StatusFlag.UNDERFLOW.value))


@pytest.mark.parametrize("depth", [0, 1, 2, 3])
def test_pow_f64_stack_underflow(
    fpga: FpgaModel, pow_f64_program: tuple[list[Any], int, Any], depth: int
) -> None:
    """Tests that executing POW_F64 with fewer than 4 stack words halts with ERR=1."""
    instructions, entry, _ = pow_f64_program
    for _ in range(depth):
        user_push64(fpga, 0)
    fpga.reg_file.sp.write(depth)

    fpga.reg_file.upc.write(entry)
    fpga.dispatcher._run(instructions)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
