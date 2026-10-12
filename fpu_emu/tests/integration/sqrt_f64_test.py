"""Integration tests for SQRT_F64 microcode routine."""

import math
from pathlib import Path
import tempfile
from typing import Any
import pytest
from fpu_asm.assembler import Assembler
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.hardware.rom import Rom
from fpu_emu.tests.test_helpers import bits_to_f64, f64_to_bits, user_pop64, user_push64

SQRT_F64_TEST_ASM = """
.include "fpu_emu/asm/pop_two_64.asm"
.include "fpu_emu/asm/normalize_f64.asm"
.include "fpu_emu/asm/sqrt_f64.asm"
"""


@pytest.fixture(scope="module")
def sqrt_f64_program() -> tuple[list[Any], int, Any]:
    """Assembles the SQRT_F64 test program once for all tests."""
    asm = Assembler()
    assembled = asm.assemble(SQRT_F64_TEST_ASM)
    instructions = [instr for _, instr in assembled]
    entry = asm.symbols["USER_SQRT_F64"]
    tmp_dir = tempfile.TemporaryDirectory()
    return instructions, entry, tmp_dir


@pytest.fixture
def fpga(sqrt_f64_program: tuple[list[Any], int, Any]) -> FpgaModel:
    """Creates a fresh FpgaModel for each test."""
    _, _, tmp_dir = sqrt_f64_program
    rom = Rom(size=1024, rom_path=Path(tmp_dir.name) / "dummy.rom")
    return FpgaModel(rom=rom)


def run_sqrt_f64(
    fpga: FpgaModel, instructions: list[Any], entry: int, x: float
) -> tuple[float | None, int]:
    """Executes SQRT_F64 on the FPGA model with the given float."""
    user_push64(fpga, f64_to_bits(x))
    fpga.reg_file.upc.write(entry)
    fpga.dispatcher._run(instructions)
    st = fpga.reg_file.status.read_int()
    err = bool(st & (1 << StatusFlag.ERR.value))
    if err:
        return None, st
    res_bits = user_pop64(fpga)
    return bits_to_f64(res_bits), st


@pytest.mark.parametrize(
    "x,expected,desc",
    [
        # Perfect squares (exact root expected)
        (0.25, 0.5, "sqrt(0.25)"),
        (1.0, 1.0, "sqrt(1.0)"),
        (4.0, 2.0, "sqrt(4.0)"),
        (9.0, 3.0, "sqrt(9.0)"),
        (16.0, 4.0, "sqrt(16.0)"),
        (25.0, 5.0, "sqrt(25.0)"),
        (100.0, 10.0, "sqrt(100.0)"),
        (144.0, 12.0, "sqrt(144.0)"),
        (65536.0, 256.0, "sqrt(65536.0)"),
        # Numbers in [1.0, 2.0)
        (2.0, math.sqrt(2.0), "sqrt(2.0)"),
        (1.5, math.sqrt(1.5), "sqrt(1.5)"),
        (1.23456789012345, math.sqrt(1.23456789012345), "sqrt(1.23456789012345)"),
        (1.99999999999999, math.sqrt(1.99999999999999), "sqrt(1.99999999999999)"),
        # Numbers in [2.0, 4.0)
        (3.0, math.sqrt(3.0), "sqrt(3.0)"),
        (2.5, math.sqrt(2.5), "sqrt(2.5)"),
        (3.5, math.sqrt(3.5), "sqrt(3.5)"),
        (3.99999999999999, math.sqrt(3.99999999999999), "sqrt(3.99999999999999)"),
        # Fractions and numbers < 1.0
        (0.5, math.sqrt(0.5), "sqrt(0.5)"),
        (0.1, math.sqrt(0.1), "sqrt(0.1)"),
        (0.01, 0.1, "sqrt(0.01)"),
        (0.0001, 0.01, "sqrt(0.0001)"),
        (1e-10, 1e-5, "sqrt(1e-10)"),
        (1e-100, 1e-50, "sqrt(1e-100)"),
        (1e-300, 1e-150, "sqrt(1e-300)"),
        # Large numbers
        (1e6, 1e3, "sqrt(1e6)"),
        (1e10, 1e5, "sqrt(1e10)"),
        (1e20, 1e10, "sqrt(1e20)"),
        (1e100, 1e50, "sqrt(1e100)"),
        (1e300, 1e150, "sqrt(1e300)"),
        # Mathematical constants
        (math.e, math.sqrt(math.e), "sqrt(e)"),
        (math.pi, math.sqrt(math.pi), "sqrt(pi)"),
        # Arbitrary floats
        (123456789.9876543, math.sqrt(123456789.9876543), "sqrt(arbitrary)"),
    ],
)
def test_sqrt_f64_normal_numbers(
    fpga: FpgaModel,
    sqrt_f64_program: tuple[list[Any], int, Any],
    x: float,
    expected: float,
    desc: str,
) -> None:
    """Verifies that SQRT_F64 computes square root within 1 ULP of Python math.sqrt."""
    instructions, entry, _ = sqrt_f64_program
    result, st = run_sqrt_f64(fpga, instructions, entry, x)
    assert result is not None
    assert not bool(st & (1 << StatusFlag.ERR.value)), f"Unexpected ERR flag for {desc}"

    res_bits = f64_to_bits(result)
    expected_bits = f64_to_bits(expected)

    # Must match within 1 ULP (least significant bit of mantissa)
    assert abs(res_bits - expected_bits) <= 1, (
        f"{desc}: got {result} (0x{res_bits:016x}), "
        f"expected {expected} (0x{expected_bits:016x}), "
        f"diff = {abs(res_bits - expected_bits)}"
    )


@pytest.mark.parametrize(
    "x,expected,desc",
    [
        (0.0, 0.0, "sqrt(+0.0) == +0.0"),
        (-0.0, -0.0, "sqrt(-0.0) == -0.0"),
        (float("inf"), float("inf"), "sqrt(+inf) == +inf"),
    ],
)
def test_sqrt_f64_special_cases(
    fpga: FpgaModel,
    sqrt_f64_program: tuple[list[Any], int, Any],
    x: float,
    expected: float,
    desc: str,
) -> None:
    """Verifies special cases for +/-0.0 and +infinity."""
    instructions, entry, _ = sqrt_f64_program
    result, st = run_sqrt_f64(fpga, instructions, entry, x)
    assert result is not None
    assert not bool(st & (1 << StatusFlag.ERR.value))
    assert f64_to_bits(result) == f64_to_bits(expected), (
        f"{desc}: got {result}, expected {expected}"
    )


def test_sqrt_f64_nan(
    fpga: FpgaModel, sqrt_f64_program: tuple[list[Any], int, Any]
) -> None:
    """Verifies that sqrt(NaN) returns NaN."""
    instructions, entry, _ = sqrt_f64_program
    result, st = run_sqrt_f64(fpga, instructions, entry, float("nan"))
    assert result is not None
    assert not bool(st & (1 << StatusFlag.ERR.value))
    assert math.isnan(result), f"Expected NaN, got {result}"


@pytest.mark.parametrize(
    "x",
    [
        -1.0,
        -4.0,
        -0.0001,
        -1e10,
        -1e-100,
        float("-inf"),
    ],
)
def test_sqrt_f64_negative_domain_error(
    fpga: FpgaModel, sqrt_f64_program: tuple[list[Any], int, Any], x: float
) -> None:
    """Verifies that negative numbers produce a domain error (ERR=1) and do not push."""
    instructions, entry, _ = sqrt_f64_program
    user_push64(fpga, f64_to_bits(x))
    assert fpga.reg_file.sp.read_int() == 2

    fpga.reg_file.upc.write(entry)
    fpga.dispatcher._run(instructions)

    st = fpga.reg_file.status.read_int()
    err = bool(st & (1 << StatusFlag.ERR.value))
    assert err, f"Expected ERR=1 for negative input {x}"
    assert fpga.reg_file.sp.read_int() == 0


def test_sqrt_f64_stack_underflow(
    fpga: FpgaModel, sqrt_f64_program: tuple[list[Any], int, Any]
) -> None:
    """Verifies that executing with an empty stack asserts ERR."""
    instructions, entry, _ = sqrt_f64_program
    assert fpga.reg_file.sp.read_int() == 0

    fpga.reg_file.upc.write(entry)
    fpga.dispatcher._run(instructions)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
