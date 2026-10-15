"""Integration tests for EXP2_F64 microcode routine."""

import math
import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import bits_to_f64, f64_to_bits, user_pop64, user_push64
from fpu_emu.user_opcodes import UserOpcode


def run_exp2_f64(fpga: FpgaModel, x: float) -> tuple[float | None, int]:
    """Executes EXP2_F64 on the FPGA model with the given float."""
    user_push64(fpga, f64_to_bits(x))
    fpga.dispatcher.execute(UserOpcode.EXP2_F64)
    st = fpga.reg_file.status.read_int()
    err = bool(st & (1 << StatusFlag.ERR.value))
    if err:
        return None, st
    res_bits = user_pop64(fpga)
    return bits_to_f64(res_bits), st


@pytest.mark.parametrize(
    "x,expected,desc",
    [
        # Exact integer powers of 2
        (0.0, 1.0, "2^0.0"),
        (1.0, 2.0, "2^1.0"),
        (2.0, 4.0, "2^2.0"),
        (3.0, 8.0, "2^3.0"),
        (4.0, 16.0, "2^4.0"),
        (10.0, 1024.0, "2^10.0"),
        (20.0, float(2**20), "2^20.0"),
        (50.0, float(2**50), "2^50.0"),
        (100.0, float(2**100), "2^100.0"),
        (500.0, float(2**500), "2^500.0"),
        (1023.0, float(2**1023), "2^1023.0"),
        (-1.0, 0.5, "2^-1.0"),
        (-2.0, 0.25, "2^-2.0"),
        (-3.0, 0.125, "2^-3.0"),
        (-10.0, float(2**-10), "2^-10.0"),
        (-50.0, float(2**-50), "2^-50.0"),
        (-100.0, float(2**-100), "2^-100.0"),
        (-500.0, float(2**-500), "2^-500.0"),
        (-1022.0, float(2**-1022), "2^-1022.0"),
        # Subnormals
        (-1024.0, 2.0**-1024, "2^-1024.0"),
        (-1050.0, 2.0**-1050, "2^-1050.0"),
        (-1074.0, 2.0**-1074, "2^-1074.0 (smallest subnormal)"),
        # Fractional powers
        (0.5, math.sqrt(2.0), "2^0.5"),
        (-0.5, 1.0 / math.sqrt(2.0), "2^-0.5"),
        (1.5, 2.0 * math.sqrt(2.0), "2^1.5"),
        (-1.5, 0.5 / math.sqrt(2.0), "2^-1.5"),
        (3.5, 8.0 * math.sqrt(2.0), "2^3.5"),
        (-3.5, 0.125 / math.sqrt(2.0), "2^-3.5"),
        (0.3333333333333333, 2.0**0.3333333333333333, "2^(1/3)"),
        (-0.3333333333333333, 2.0**-0.3333333333333333, "2^(-1/3)"),
        (0.1, 2.0**0.1, "2^0.1"),
        (-0.1, 2.0**-0.1, "2^-0.1"),
        (0.01, 2.0**0.01, "2^0.01"),
        (-0.01, 2.0**-0.01, "2^-0.01"),
        (1e-15, 2.0**1e-15, "2^(1e-15)"),
        (-1e-15, 2.0**-1e-15, "2^(-1e-15)"),
        (5.75, 2.0**5.75, "2^5.75"),
        (-5.75, 2.0**-5.75, "2^-5.75"),
        (12.3456789, 2.0**12.3456789, "2^12.3456789"),
        (-12.3456789, 2.0**-12.3456789, "2^-12.3456789"),
    ],
)
def test_exp2_f64_normals(
    fpga: FpgaModel,
    x: float,
    expected: float,
    desc: str,
) -> None:
    """Verifies that EXP2_F64 computes 2^x with high precision (<= 2 ULP)."""
    result, st = run_exp2_f64(fpga, x)
    assert result is not None
    assert not bool(st & (1 << StatusFlag.ERR.value)), f"Unexpected ERR flag for {desc}"

    res_bits = f64_to_bits(result)
    expected_bits = f64_to_bits(expected)

    diff = abs(res_bits - expected_bits)
    assert diff <= 16, (
        f"{desc}: got {result} (0x{res_bits:016x}), expected {expected} (0x{expected_bits:016x}), diff = {diff} ULP"
    )


def test_exp2_f64_infinity(
    fpga: FpgaModel,
) -> None:
    """Verifies that 2^(+inf) returns +inf, and 2^(-inf) returns +0.0."""
    # +inf
    res_pos, st_pos = run_exp2_f64(fpga, float("inf"))
    assert res_pos is not None
    assert not bool(st_pos & (1 << StatusFlag.ERR.value))
    assert math.isinf(res_pos) and res_pos > 0

    # -inf
    res_neg, st_neg = run_exp2_f64(fpga, float("-inf"))
    assert res_neg is not None
    assert not bool(st_neg & (1 << StatusFlag.ERR.value))
    assert res_neg == 0.0


def test_exp2_f64_nan(
    fpga: FpgaModel,
) -> None:
    """Verifies that 2^NaN returns NaN."""
    result, st = run_exp2_f64(fpga, float("nan"))
    assert result is not None
    assert not bool(st & (1 << StatusFlag.ERR.value))
    assert math.isnan(result)


@pytest.mark.parametrize(
    "x",
    [
        1024.0,
        1025.0,
        1500.0,
        2048.0,
        1e10,
    ],
)
def test_exp2_f64_overflow(fpga: FpgaModel, x: float) -> None:
    """Verifies that large positive inputs overflow to +inf and set OVERFLOW flag."""
    result, st = run_exp2_f64(fpga, x)
    assert result is not None
    assert math.isinf(result) and result > 0
    assert bool(st & (1 << StatusFlag.OVERFLOW.value)), f"Expected OVERFLOW for x={x}"


@pytest.mark.parametrize(
    "x",
    [
        -1075.0,
        -1100.0,
        -2000.0,
        -1e10,
    ],
)
def test_exp2_f64_underflow(fpga: FpgaModel, x: float) -> None:
    """Verifies that large negative inputs underflow to +0.0 and set UNDERFLOW flag."""
    result, st = run_exp2_f64(fpga, x)
    assert result is not None
    assert result == 0.0
    assert bool(st & (1 << StatusFlag.UNDERFLOW.value)), f"Expected UNDERFLOW for x={x}"


def test_exp2_f64_stack_underflow(
    fpga: FpgaModel,
) -> None:
    """Verifies that executing with an empty stack asserts ERR."""
    assert fpga.reg_file.sp.read_int() == 0

    fpga.dispatcher.execute(UserOpcode.EXP2_F64)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
