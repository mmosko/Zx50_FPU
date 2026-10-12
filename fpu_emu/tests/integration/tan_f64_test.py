"""Integration tests for 64-bit IEEE-754 double precision tangent (TAN_F64)."""

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

TRIG_F64_SOURCE = """
.include "fpu_emu/asm/pop_two_64.asm"
.include "fpu_emu/asm/align_f64.asm"
.include "fpu_emu/asm/normalize_f64.asm"
.include "fpu_emu/asm/add_f64.asm"
.include "fpu_emu/asm/sub_f64.asm"
.include "fpu_emu/asm/mul_f64.asm"
.include "fpu_emu/asm/div_f64.asm"
.include "fpu_emu/asm/trig_f64.asm"
"""


@pytest.fixture(scope="module")
def tan_f64_program() -> tuple[list[Any], int, Any]:
    """Assembles the TAN_F64 microcode routine once for all tests in this module."""
    asm = Assembler()
    assembled = asm.assemble(TRIG_F64_SOURCE)
    instructions = [instr for _, instr in assembled]
    entry = asm.symbols["USER_TAN_F64"]
    tmp_dir = tempfile.TemporaryDirectory()
    return instructions, entry, tmp_dir


@pytest.fixture
def fpga(tan_f64_program: tuple[list[Any], int, Any]) -> FpgaModel:
    """Creates a fresh FPGA model with an empty ROM."""
    _, _, tmp_dir = tan_f64_program
    rom = Rom(size=1024, rom_path=Path(tmp_dir.name) / "dummy.rom")
    return FpgaModel(rom=rom)


def run_tan_f64(
    fpga: FpgaModel,
    instructions: list[Any],
    entry: int,
    theta: float,
) -> tuple[float | None, int]:
    """Pushes theta and executes USER_TAN_F64."""
    user_push64(fpga, f64_to_bits(theta))
    fpga.reg_file.upc.write(entry)
    fpga.dispatcher._run(instructions)

    status = fpga.reg_file.status.read_int()
    sp = fpga.reg_file.sp.read_int()
    if sp >= 2:
        raw_res = user_pop64(fpga)
        return bits_to_f64(raw_res), status
    return None, status


@pytest.mark.parametrize(
    "theta",
    [
        0.0,
        -0.0,
        1e-10,
        -1e-10,
        1e-15,
        -1e-15,
        0.01,
        -0.01,
        0.1,
        -0.1,
        0.5,
        -0.5,
        math.pi / 6,
        -math.pi / 6,
        math.pi / 4,
        -math.pi / 4,
        math.pi / 3,
        -math.pi / 3,
        1.0,
        -1.0,
        2.0,
        -2.0,
        math.pi,
        -math.pi,
        3.0,
        -3.0,
        4.0,
        -4.0,
        5.0,
        -5.0,
        2.0 * math.pi,
        10.0,
        -10.0,
        25.0,
        -50.0,
    ],
)
def test_tan_f64_normals(
    fpga: FpgaModel,
    tan_f64_program: tuple[list[Any], int, Any],
    theta: float,
):
    """Verifies tan(theta) against math.tan to within 1 ULP (~1e-15 relative precision)."""
    instructions, entry, _ = tan_f64_program
    act, status = run_tan_f64(fpga, instructions, entry, theta)

    assert act is not None
    exp = math.tan(theta)
    diff = abs(act - exp)
    tol = max(1e-15, 1e-15 * abs(exp))
    assert diff <= tol
    assert (status & (1 << StatusFlag.ERR.value)) == 0


def test_tan_f64_zero_preserves_sign(
    fpga: FpgaModel,
    tan_f64_program: tuple[list[Any], int, Any],
):
    """Verifies tan(+0.0) = +0.0 and tan(-0.0) = -0.0."""
    instructions, entry, _ = tan_f64_program

    act_pos, _ = run_tan_f64(fpga, instructions, entry, 0.0)
    assert act_pos is not None
    assert act_pos == 0.0
    assert math.copysign(1.0, act_pos) == 1.0

    act_neg, _ = run_tan_f64(fpga, instructions, entry, -0.0)
    assert act_neg is not None
    assert act_neg == 0.0
    assert math.copysign(1.0, act_neg) == -1.0


def test_tan_f64_infinity_domain_error(
    fpga: FpgaModel,
    tan_f64_program: tuple[list[Any], int, Any],
):
    """Verifies tan(+/-Inf) sets ERR=1 and returns Quiet NaN."""
    instructions, entry, _ = tan_f64_program

    for inf_val in [float("inf"), float("-inf")]:
        act, status = run_tan_f64(fpga, instructions, entry, inf_val)
        assert (status & (1 << StatusFlag.ERR.value)) != 0
        assert act is not None
        assert math.isnan(act)


def test_tan_f64_nan_propagation(
    fpga: FpgaModel,
    tan_f64_program: tuple[list[Any], int, Any],
):
    """Verifies tan(NaN) returns NaN without error."""
    instructions, entry, _ = tan_f64_program

    act, status = run_tan_f64(fpga, instructions, entry, float("nan"))
    assert (status & (1 << StatusFlag.ERR.value)) == 0
    assert act is not None
    assert math.isnan(act)


def test_tan_f64_stack_underflow(
    fpga: FpgaModel,
    tan_f64_program: tuple[list[Any], int, Any],
):
    """Verifies stack underflow (< 8 bytes) sets ERR=1 and does not execute."""
    instructions, entry, _ = tan_f64_program
    # Push only 1 word (4 bytes < 8 bytes required)
    fpga.reg_file.sp.write(1)
    fpga.reg_file.upc.write(entry)
    fpga.dispatcher._run(instructions)

    status = fpga.reg_file.status.read_int()
    assert (status & (1 << StatusFlag.ERR.value)) != 0
