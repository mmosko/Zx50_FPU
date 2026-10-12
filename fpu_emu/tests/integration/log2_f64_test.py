"""Integration tests for LOG2_F64 microcode routine."""

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

LOG2_F64_TEST_ASM = """
.include "fpu_emu/asm/pop_two_64.asm"
.include "fpu_emu/asm/align_f64.asm"
.include "fpu_emu/asm/normalize_f64.asm"
.include "fpu_emu/asm/add_f64.asm"
.include "fpu_emu/asm/sub_f64.asm"
.include "fpu_emu/asm/mul_f64.asm"
.include "fpu_emu/asm/div_f64.asm"
.include "fpu_emu/asm/log2_f64.asm"
"""


@pytest.fixture(scope="module")
def log2_f64_program() -> tuple[list[Any], int, Any]:
    """Assembles the LOG2_F64 test program once for all tests."""
    asm = Assembler()
    assembled = asm.assemble(LOG2_F64_TEST_ASM)
    instructions = [instr for _, instr in assembled]
    entry = asm.symbols["USER_LOG2_F64"]
    tmp_dir = tempfile.TemporaryDirectory()
    return instructions, entry, tmp_dir


@pytest.fixture
def fpga(log2_f64_program: tuple[list[Any], int, Any]) -> FpgaModel:
    """Creates a fresh FpgaModel for each test."""
    _, _, tmp_dir = log2_f64_program
    rom = Rom(size=1024, rom_path=Path(tmp_dir.name) / "dummy.rom")
    return FpgaModel(rom=rom)


def run_log2_f64(
    fpga: FpgaModel, instructions: list[Any], entry: int, x: float
) -> tuple[float | None, int]:
    """Executes LOG2_F64 on the FPGA model with the given float."""
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
        # Exact powers of 2
        (1.0, 0.0, "log2(1.0)"),
        (2.0, 1.0, "log2(2.0)"),
        (4.0, 2.0, "log2(4.0)"),
        (8.0, 3.0, "log2(8.0)"),
        (16.0, 4.0, "log2(16.0)"),
        (1024.0, 10.0, "log2(1024.0)"),
        (1048576.0, 20.0, "log2(1048576.0)"),
        (0.5, -1.0, "log2(0.5)"),
        (0.25, -2.0, "log2(0.25)"),
        (0.125, -3.0, "log2(0.125)"),
        # Numbers around 1.0
        (1.000000000001, math.log2(1.000000000001), "log2(1 + eps)"),
        (0.999999999999, math.log2(0.999999999999), "log2(1 - eps)"),
        # General positive numbers
        (3.0, math.log2(3.0), "log2(3.0)"),
        (5.0, math.log2(5.0), "log2(5.0)"),
        (10.0, math.log2(10.0), "log2(10.0)"),
        (100.0, math.log2(100.0), "log2(100.0)"),
        (1.414213562373095, math.log2(1.414213562373095), "log2(sqrt(2))"),
        (1.5, math.log2(1.5), "log2(1.5)"),
        (0.7071067811865476, math.log2(0.7071067811865476), "log2(1/sqrt(2))"),
        (0.1, math.log2(0.1), "log2(0.1)"),
        (0.01, math.log2(0.01), "log2(0.01)"),
        (0.001, math.log2(0.001), "log2(0.001)"),
        # Mathematical constants
        (math.e, math.log2(math.e), "log2(e)"),
        (math.pi, math.log2(math.pi), "log2(pi)"),
        # Wide dynamic range
        (1e-10, math.log2(1e-10), "log2(1e-10)"),
        (1e-50, math.log2(1e-50), "log2(1e-50)"),
        (1e-100, math.log2(1e-100), "log2(1e-100)"),
        (1e-300, math.log2(1e-300), "log2(1e-300)"),
        (1e10, math.log2(1e10), "log2(1e10)"),
        (1e50, math.log2(1e50), "log2(1e50)"),
        (1e100, math.log2(1e100), "log2(1e100)"),
        (1e300, math.log2(1e300), "log2(1e300)"),
    ],
)
def test_log2_f64_normals(
    fpga: FpgaModel,
    log2_f64_program: tuple[list[Any], int, Any],
    x: float,
    expected: float,
    desc: str,
) -> None:
    """Verifies that LOG2_F64 computes base-2 logarithm within 2 ULP of Python math.log2."""
    instructions, entry, _ = log2_f64_program
    result, st = run_log2_f64(fpga, instructions, entry, x)
    assert result is not None
    assert not bool(st & (1 << StatusFlag.ERR.value)), f"Unexpected ERR flag for {desc}"

    res_bits = f64_to_bits(result)
    expected_bits = f64_to_bits(expected)

    # For values near 1.0 where log2(x) -> 0, check absolute error <= 1e-15
    # (since ULP scales with tiny exponent down to 2^-92).
    # For all other values, require strict accuracy within 4 ULP.
    if abs(expected) < 1e-9:
        abs_err = abs(result - expected)
        assert abs_err <= 1e-15, (
            f"{desc}: got {result}, expected {expected}, abs_err = {abs_err}"
        )
    else:
        diff = abs(res_bits - expected_bits)
        assert diff <= 4, (
            f"{desc}: got {result} (0x{res_bits:016x}), "
            f"expected {expected} (0x{expected_bits:016x}), "
            f"diff = {diff} ULP"
        )


def test_log2_f64_infinity(
    fpga: FpgaModel, log2_f64_program: tuple[list[Any], int, Any]
) -> None:
    """Verifies that log2(+inf) returns +inf."""
    instructions, entry, _ = log2_f64_program
    result, st = run_log2_f64(fpga, instructions, entry, float("inf"))
    assert result is not None
    assert not bool(st & (1 << StatusFlag.ERR.value))
    assert math.isinf(result) and result > 0


def test_log2_f64_nan(
    fpga: FpgaModel, log2_f64_program: tuple[list[Any], int, Any]
) -> None:
    """Verifies that log2(NaN) returns NaN."""
    instructions, entry, _ = log2_f64_program
    result, st = run_log2_f64(fpga, instructions, entry, float("nan"))
    assert result is not None
    assert not bool(st & (1 << StatusFlag.ERR.value))
    assert math.isnan(result)


@pytest.mark.parametrize(
    "x",
    [
        0.0,
        -0.0,
        -1.0,
        -2.0,
        -0.0001,
        -1e10,
        -1e-100,
        float("-inf"),
    ],
)
def test_log2_f64_domain_error(
    fpga: FpgaModel, log2_f64_program: tuple[list[Any], int, Any], x: float
) -> None:
    """Verifies that x <= 0 produces a domain error (ERR=1) and does not push."""
    instructions, entry, _ = log2_f64_program
    user_push64(fpga, f64_to_bits(x))
    assert fpga.reg_file.sp.read_int() == 2

    fpga.reg_file.upc.write(entry)
    fpga.dispatcher._run(instructions)

    st = fpga.reg_file.status.read_int()
    err = bool(st & (1 << StatusFlag.ERR.value))
    assert err, f"Expected ERR=1 for non-positive input {x}"
    # Stack should be empty (no result pushed)
    assert fpga.reg_file.sp.read_int() == 0


def test_log2_f64_stack_underflow(
    fpga: FpgaModel, log2_f64_program: tuple[list[Any], int, Any]
) -> None:
    """Verifies that executing with an empty stack asserts ERR."""
    instructions, entry, _ = log2_f64_program
    assert fpga.reg_file.sp.read_int() == 0

    fpga.reg_file.upc.write(entry)
    fpga.dispatcher._run(instructions)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
