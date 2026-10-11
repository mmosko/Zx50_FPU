"""Integration tests for UserOpcode.MUL_F64 executed via the microcode dispatcher."""

import math
import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import bits_to_f64, f64_to_bits, user_pop64, user_push64
from fpu_emu.user_opcodes import UserOpcode


@pytest.mark.parametrize(
    "a,b,expected,desc",
    [
        # Identity
        (1.0, 1.0, 1.0, "1.0 * 1.0"),
        (1.0, 2.0, 2.0, "1.0 * 2.0"),
        (2.0, 1.0, 2.0, "2.0 * 1.0"),
        (1.0, -5.0, -5.0, "1.0 * -5.0"),
        (-5.0, 1.0, -5.0, "-5.0 * 1.0"),
        # Simple positive multiplications
        (2.0, 3.0, 6.0, "2.0 * 3.0"),
        (1.5, 2.5, 3.75, "1.5 * 2.5"),
        (4.0, 0.25, 1.0, "4.0 * 0.25"),
        (0.5, 0.5, 0.25, "0.5 * 0.5"),
        (100.0, 0.01, 1.0, "100.0 * 0.01"),
        # High precision multiplications
        (
            3.141592653589793,
            2.718281828459045,
            3.141592653589793 * 2.718281828459045,
            "pi * e",
        ),
        (
            12.345678901234,
            98.765432109876,
            12.345678901234 * 98.765432109876,
            "High-precision mul",
        ),
        # Sign handling
        (5.0, -2.0, -10.0, "5.0 * -2.0"),
        (-5.0, 2.0, -10.0, "-5.0 * 2.0"),
        (-5.0, -2.0, 10.0, "-5.0 * -2.0"),
        (-1.5, -2.5, 3.75, "-1.5 * -2.5"),
        # Large and small numbers
        (1e10, 1e20, 1e30, "1e10 * 1e20"),
        (1e-10, 1e-20, 1e-30, "1e-10 * 1e-20"),
        (1.23456789e-50, 9.87654321e100, 1.23456789e-50 * 9.87654321e100, "Wide range"),
        # Zero operand handling
        (0.0, 5.0, 0.0, "0.0 * 5.0"),
        (5.0, 0.0, 0.0, "5.0 * 0.0"),
        (0.0, 0.0, 0.0, "0.0 * 0.0"),
        (-5.0, 0.0, -0.0, "-5.0 * 0.0 -> -0.0"),
        (0.0, -5.0, -0.0, "0.0 * -5.0 -> -0.0"),
        (-0.0, -0.0, 0.0, "-0.0 * -0.0 -> +0.0"),
    ],
)
def test_user_opcode_mul_f64(
    fpga: FpgaModel, a: float, b: float, expected: float, desc: str
) -> None:
    """Tests executing UserOpcode.MUL_F64 via dispatcher."""
    user_push64(fpga, f64_to_bits(a))
    user_push64(fpga, f64_to_bits(b))
    assert fpga.reg_file.sp.read_int() == 4

    # Execute MUL_F64
    fpga.dispatcher.execute(UserOpcode.MUL_F64)

    # After MUL_F64, stack pointer should be 2
    assert fpga.reg_file.sp.read_int() == 2
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)

    # Pop result from stack
    res_bits = user_pop64(fpga)
    res_float = bits_to_f64(res_bits)
    assert fpga.reg_file.sp.read_int() == 0

    if expected == 0.0:
        assert res_float == 0.0, f"Failed {desc}: got {res_float}, expected 0.0"
        # Check sign of zero if expected is -0.0
        if math.copysign(1.0, expected) < 0:
            assert math.copysign(1.0, res_float) < 0, (
                f"Failed {desc}: expected negative zero"
            )
            assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)
        else:
            assert math.copysign(1.0, res_float) > 0, (
                f"Failed {desc}: expected positive zero"
            )
            assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)
        assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    else:
        assert pytest.approx(res_float, rel=1e-12) == expected, (
            f"Failed {desc}: got {res_float}, expected {expected}"
        )
        assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
        if expected < 0:
            assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)
        else:
            assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)


def test_mul_f64_overflow(fpga: FpgaModel) -> None:
    """Tests that MUL_F64 with overflowing exponents sets OVERFLOW and returns infinity."""
    user_push64(fpga, f64_to_bits(1e200))
    user_push64(fpga, f64_to_bits(1e200))
    fpga.dispatcher.execute(UserOpcode.MUL_F64)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)
    res = bits_to_f64(user_pop64(fpga))
    assert math.isinf(res) and res > 0


def test_mul_f64_underflow(fpga: FpgaModel) -> None:
    """Tests that MUL_F64 with underflowing exponents sets UNDERFLOW and returns zero."""
    user_push64(fpga, f64_to_bits(1e-200))
    user_push64(fpga, f64_to_bits(1e-200))
    fpga.dispatcher.execute(UserOpcode.MUL_F64)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    res = bits_to_f64(user_pop64(fpga))
    assert res == 0.0


def test_mul_f64_stack_underflow(fpga: FpgaModel) -> None:
    """Tests that MUL_F64 with empty stack asserts ERR (not UNDERFLOW)."""
    fpga.dispatcher.execute(UserOpcode.MUL_F64)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)


def test_mul_f64_stack_single_operand(fpga: FpgaModel) -> None:
    """Tests that MUL_F64 with only one operand on stack asserts ERR (not UNDERFLOW)."""
    user_push64(fpga, f64_to_bits(1.0))
    fpga.dispatcher.execute(UserOpcode.MUL_F64)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
