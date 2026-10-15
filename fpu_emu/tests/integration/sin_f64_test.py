"""Integration tests for 64-bit IEEE-754 double precision sine (SIN_F64)."""

import math

import pytest

from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import bits_to_f64, f64_to_bits, user_pop64, user_push64
from fpu_emu.user_opcodes import UserOpcode


def run_sin_f64(
    fpga: FpgaModel,
    theta: float,
) -> tuple[float | None, int]:
    """Pushes theta and executes USER_SIN_F64."""
    user_push64(fpga, f64_to_bits(theta))
    fpga.dispatcher.execute(UserOpcode.SIN_F64)

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
        math.pi / 2,
        -math.pi / 2,
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
        1.5 * math.pi,
        2.0 * math.pi,
        10.0,
        -10.0,
        25.0,
        -50.0,
    ],
)
def test_sin_f64_normals(
    fpga: FpgaModel,
    theta: float,
):
    """Verifies sin(theta) against math.sin to within 1 ULP (~1e-15)."""
    act, status = run_sin_f64(fpga, theta)

    assert act is not None
    exp = math.sin(theta)
    assert abs(act - exp) < 1e-15
    assert (status & (1 << StatusFlag.ERR.value)) == 0


def test_sin_f64_zero_preserves_sign(
    fpga: FpgaModel,
):
    """Verifies sin(+0.0) = +0.0 and sin(-0.0) = -0.0."""
    act_pos, _ = run_sin_f64(fpga, 0.0)
    assert act_pos is not None
    assert act_pos == 0.0
    assert math.copysign(1.0, act_pos) == 1.0

    act_neg, _ = run_sin_f64(fpga, -0.0)
    assert act_neg is not None
    assert act_neg == 0.0
    assert math.copysign(1.0, act_neg) == -1.0


def test_sin_f64_infinity_domain_error(
    fpga: FpgaModel,
):
    """Verifies sin(+/-Inf) sets ERR=1 and returns Quiet NaN."""
    for inf_val in [float("inf"), float("-inf")]:
        act, status = run_sin_f64(fpga, inf_val)
        assert (status & (1 << StatusFlag.ERR.value)) != 0
        assert act is not None
        assert math.isnan(act)


def test_sin_f64_nan_propagation(
    fpga: FpgaModel,
):
    """Verifies sin(NaN) returns NaN without error."""
    act, status = run_sin_f64(fpga, float("nan"))
    assert (status & (1 << StatusFlag.ERR.value)) == 0
    assert act is not None
    assert math.isnan(act)


def test_sin_f64_stack_underflow(
    fpga: FpgaModel,
):
    """Verifies stack underflow (< 8 bytes) sets ERR=1 and does not execute."""
    # Push only 1 word (4 bytes < 8 bytes required)
    fpga.reg_file.sp.write(1)
    fpga.dispatcher.execute(UserOpcode.SIN_F64)

    status = fpga.reg_file.status.read_int()
    assert (status & (1 << StatusFlag.ERR.value)) != 0
