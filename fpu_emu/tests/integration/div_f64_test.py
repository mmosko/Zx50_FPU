"""Integration tests for UserOpcode.DIV_F64 executed via the microcode dispatcher."""

import math
import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import bits_to_f64, f64_to_bits, user_pop64, user_push64
from fpu_emu.user_opcodes import UserOpcode


@pytest.mark.parametrize(
    "a,b,expected,desc",
    [
        # Normal division: a >= b (mantissa ratio >= 1.0)
        (6.0, 2.0, 3.0, "6.0 / 2.0"),
        (1.5, 1.0, 1.5, "1.5 / 1.0"),
        (10.0, 2.0, 5.0, "10.0 / 2.0"),
        (20.0, 4.0, 5.0, "20.0 / 4.0"),
        (100.0, 10.0, 10.0, "100.0 / 10.0"),
        (35.0, 7.0, 5.0, "35.0 / 7.0"),
        (2.25, 1.5, 1.5, "2.25 / 1.5"),
        (61.7, 5.0, 12.34, "61.7 / 5.0"),
        (0.5, 0.5, 1.0, "0.5 / 0.5"),
        # Normal division: a < b (mantissa ratio < 1.0)
        (1.0, 4.0, 0.25, "1.0 / 4.0"),
        (1.5, 2.0, 0.75, "1.5 / 2.0"),
        (1.0, 2.0, 0.5, "1.0 / 2.0"),
        (1.875, 2.5, 0.75, "1.875 / 2.5"),
        (1.0, 3.0, 1.0 / 3.0, "1.0 / 3.0"),
        (2.0, 3.0, 2.0 / 3.0, "2.0 / 3.0"),
        (1.0, 7.0, 1.0 / 7.0, "1.0 / 7.0"),
        # High-precision division
        (
            3.141592653589793,
            2.718281828459045,
            3.141592653589793 / 2.718281828459045,
            "pi / e",
        ),
        (
            2.718281828459045,
            3.141592653589793,
            2.718281828459045 / 3.141592653589793,
            "e / pi",
        ),
        (
            12.345678901234,
            98.765432109876,
            12.345678901234 / 98.765432109876,
            "High-precision div",
        ),
        # Sign handling
        (12.0, 3.0, 4.0, "12.0 / 3.0"),
        (12.0, -3.0, -4.0, "12.0 / -3.0"),
        (-12.0, 3.0, -4.0, "-12.0 / 3.0"),
        (-12.0, -3.0, 4.0, "-12.0 / -3.0"),
        (-0.25, -0.5, 0.5, "-0.25 / -0.5"),
        (-1.0, 4.0, -0.25, "-1.0 / 4.0"),
        # Identity / negation
        (42.0, 1.0, 42.0, "42.0 / 1.0"),
        (42.0, -1.0, -42.0, "42.0 / -1.0"),
        (-42.0, 1.0, -42.0, "-42.0 / 1.0"),
        (-42.0, -1.0, 42.0, "-42.0 / -1.0"),
        # Zero dividend handling (0.0 / b = 0.0)
        (0.0, 5.0, 0.0, "0.0 / 5.0"),
        (-0.0, 5.0, -0.0, "-0.0 / 5.0"),
        (0.0, -5.0, -0.0, "0.0 / -5.0"),
        (-0.0, -5.0, 0.0, "-0.0 / -5.0"),
        # Dynamic range
        (1e50, 1e20, 1e30, "1e50 / 1e20"),
        (1e-50, 1e-20, 1e-30, "1e-50 / 1e-20"),
        (1.0, 1e25, 1e-25, "1.0 / 1e25"),
        (1.0, 1e-25, 1e25, "1.0 / 1e-25"),
    ],
)
def test_user_opcode_div_f64(
    fpga: FpgaModel, a: float, b: float, expected: float, desc: str
) -> None:
    """Tests executing UserOpcode.DIV_F64 via dispatcher: computes (a / b)."""
    user_push64(fpga, f64_to_bits(a))
    user_push64(fpga, f64_to_bits(b))

    fpga.dispatcher.execute(UserOpcode.DIV_F64)

    assert fpga.reg_file.sp.read_int() == 2
    res_bits = user_pop64(fpga)
    res_float = bits_to_f64(res_bits)

    if expected == 0.0:
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


@pytest.mark.parametrize(
    "a,b,desc",
    [
        (5.0, 0.0, "5.0 / 0.0"),
        (-5.0, 0.0, "-5.0 / 0.0"),
        (0.0, 0.0, "0.0 / 0.0"),
        (1.0, -0.0, "1.0 / -0.0"),
    ],
)
def test_div_f64_divide_by_zero(fpga: FpgaModel, a: float, b: float, desc: str) -> None:
    """Tests that dividing by zero asserts ERR and aborts push."""
    user_push64(fpga, f64_to_bits(a))
    user_push64(fpga, f64_to_bits(b))
    fpga.dispatcher.execute(UserOpcode.DIV_F64)

    # Operands popped, nothing pushed -> SP == 0
    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR), f"Expected ERR for {desc}"


def test_div_f64_overflow(fpga: FpgaModel) -> None:
    """Tests that dividing large float by tiny float produces infinity and sets OVERFLOW."""
    user_push64(fpga, f64_to_bits(1e200))
    user_push64(fpga, f64_to_bits(1e-200))
    fpga.dispatcher.execute(UserOpcode.DIV_F64)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)
    res_bits = user_pop64(fpga)
    res_float = bits_to_f64(res_bits)
    assert math.isinf(res_float)


def test_div_f64_underflow(fpga: FpgaModel) -> None:
    """Tests that dividing tiny float by large float asserts UNDERFLOW flag and produces zero."""
    user_push64(fpga, f64_to_bits(1e-200))
    user_push64(fpga, f64_to_bits(1e200))
    fpga.dispatcher.execute(UserOpcode.DIV_F64)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
    res_bits = user_pop64(fpga)
    res_float = bits_to_f64(res_bits)
    assert res_float == 0.0


def test_div_f64_stack_underflow(fpga: FpgaModel) -> None:
    """Tests that DIV_F64 with empty stack asserts ERR (not UNDERFLOW)."""
    fpga.dispatcher.execute(UserOpcode.DIV_F64)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)


def test_div_f64_stack_single_operand(fpga: FpgaModel) -> None:
    """Tests that DIV_F64 with only one operand on stack asserts ERR (not UNDERFLOW)."""
    user_push64(fpga, f64_to_bits(1.0))
    fpga.dispatcher.execute(UserOpcode.DIV_F64)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
