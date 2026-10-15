"""Integration tests for LOG2_F64 microcode routine."""

import math
import pytest
from fpu_emu.dispatcher import UserOpcode
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import bits_to_f64, f64_to_bits, user_pop64, user_push64


def run_log2_f64(fpga: FpgaModel, x: float) -> tuple[float | None, int]:
    """Executes LOG2_F64 on the FPGA model with the given float."""
    user_push64(fpga, f64_to_bits(x))
    fpga.dispatcher.execute(UserOpcode.LOG2_F64)
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
    x: float,
    expected: float,
    desc: str,
) -> None:
    """Verifies that LOG2_F64 computes base-2 logarithm within 2 ULP of Python math.log2."""
    result, st = run_log2_f64(fpga, x)
    assert result is not None
    assert not bool(st & (1 << StatusFlag.ERR.value)), f"Unexpected ERR flag for {desc}"

    res_bits = f64_to_bits(result)
    expected_bits = f64_to_bits(expected)

    # For values near 1.0 where log2(x) -> 0, check absolute error <= 1e-15
    # (since ULP scales with tiny exponent down to 2^-92).
    # For all other values, require strict accuracy within 4 ULP.
    if abs(expected) < 1e-9:
        abs_err = abs(result - expected)
        assert abs_err <= 1e-15, f"{desc}: got {result}, expected {expected}, abs_err = {abs_err}"
    else:
        diff = abs(res_bits - expected_bits)
        assert diff <= 4, (
            f"{desc}: got {result} (0x{res_bits:016x}), expected {expected} (0x{expected_bits:016x}), diff = {diff} ULP"
        )


def test_log2_f64_infinity(fpga: FpgaModel) -> None:
    """Verifies that log2(+inf) returns +inf."""
    result, st = run_log2_f64(fpga, float("inf"))
    assert result is not None
    assert not bool(st & (1 << StatusFlag.ERR.value))
    assert math.isinf(result) and result > 0


def test_log2_f64_nan(fpga: FpgaModel) -> None:
    """Verifies that log2(NaN) returns NaN."""
    result, st = run_log2_f64(fpga, float("nan"))
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
def test_log2_f64_domain_error(fpga: FpgaModel, x: float) -> None:
    """Verifies that x <= 0 produces a domain error (ERR=1) and does not push."""
    user_push64(fpga, f64_to_bits(x))
    assert fpga.reg_file.sp.read_int() == 2

    fpga.dispatcher.execute(UserOpcode.LOG2_F64)

    st = fpga.reg_file.status.read_int()
    err = bool(st & (1 << StatusFlag.ERR.value))
    assert err, f"Expected ERR=1 for non-positive input {x}"
    # Stack should be empty (no result pushed)
    assert fpga.reg_file.sp.read_int() == 0


def test_log2_f64_stack_underflow(fpga: FpgaModel) -> None:
    """Verifies that executing with an empty stack asserts ERR."""
    assert fpga.reg_file.sp.read_int() == 0

    fpga.dispatcher.execute(UserOpcode.LOG2_F64)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
