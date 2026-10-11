"""Integration tests for UserOpcode.CONV_F32_I32."""

import math
import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import f32_to_bits, user_pop32, user_push32
from fpu_emu.user_opcodes import UserOpcode

MASK_32 = 0xFFFFFFFF


@pytest.mark.parametrize(
    "float_val,expected_int,is_ovf,desc",
    [
        # Exact integers
        (0.0, 0, False, "0.0 -> 0"),
        (-0.0, 0, False, "-0.0 -> 0"),
        (1.0, 1, False, "1.0 -> 1"),
        (-1.0, -1, False, "-1.0 -> -1"),
        (2.0, 2, False, "2.0 -> 2"),
        (-2.0, -2, False, "-2.0 -> -2"),
        (42.0, 42, False, "42.0 -> 42"),
        (-42.0, -42, False, "-42.0 -> -42"),
        (1000.0, 1000, False, "1000.0 -> 1000"),
        (-1000.0, -1000, False, "-1000.0 -> -1000"),
        (65535.0, 65535, False, "65535.0 -> 65535"),
        (-65535.0, -65535, False, "-65535.0 -> -65535"),
        (16777216.0, 16777216, False, "2^24 -> 16777216"),
        (-16777216.0, -16777216, False, "-2^24 -> -16777216"),
        (2147483520.0, 2147483520, False, "near max positive -> 2147483520"),
        # Truncation towards zero (fractional magnitude < 1.0)
        (0.5, 0, False, "0.5 -> 0"),
        (-0.5, 0, False, "-0.5 -> 0"),
        (0.1, 0, False, "0.1 -> 0"),
        (-0.1, 0, False, "-0.1 -> 0"),
        (0.999, 0, False, "0.999 -> 0"),
        (-0.999, 0, False, "-0.999 -> 0"),
        # Truncation towards zero (fractional magnitude > 1.0)
        (1.1, 1, False, "1.1 -> 1"),
        (1.9, 1, False, "1.9 -> 1"),
        (-1.1, -1, False, "-1.1 -> -1"),
        (-1.9, -1, False, "-1.9 -> -1"),
        (42.75, 42, False, "42.75 -> 42"),
        (-42.75, -42, False, "-42.75 -> -42"),
        (123456.875, 123456, False, "123456.875 -> 123456"),
        (-123456.875, -123456, False, "-123456.875 -> -123456"),
        # Exact minimum representable 32-bit signed integer (-2^31)
        (-2147483648.0, -2147483648, False, "-2^31 -> -2147483648 (no overflow)"),
        # Positive Overflow (clamped to 0x7FFFFFFF)
        (2147483648.0, 0x7FFFFFFF, True, "+2^31 -> positive overflow"),
        (3000000000.0, 0x7FFFFFFF, True, "3e9 -> positive overflow"),
        (1e20, 0x7FFFFFFF, True, "1e20 -> positive overflow"),
        (float("inf"), 0x7FFFFFFF, True, "+inf -> positive overflow"),
        (float("nan"), 0x7FFFFFFF, True, "+nan -> positive overflow"),
        # Negative Overflow (clamped to 0x80000000)
        (-2147483904.0, -2147483648, True, "-2147483904 -> negative overflow"),
        (-3000000000.0, -2147483648, True, "-3e9 -> negative overflow"),
        (-1e20, -2147483648, True, "-1e20 -> negative overflow"),
        (float("-inf"), -2147483648, True, "-inf -> negative overflow"),
    ],
)
def test_user_opcode_conv_f32_i32(
    fpga: FpgaModel, float_val: float, expected_int: int, is_ovf: bool, desc: str
) -> None:
    """Tests CONV_F32_I32 converting IEEE-754 single float to signed 32-bit int."""
    if math.isnan(float_val):
        f_bits = 0x7FC00000  # canonical single NaN
    else:
        f_bits = f32_to_bits(float_val)

    user_push32(fpga, f_bits)
    assert fpga.reg_file.sp.read_int() == 1

    fpga.dispatcher.execute(UserOpcode.CONV_F32_I32)

    # In-place conversion (delta SP = 0)
    assert fpga.reg_file.sp.read_int() == 1

    expected_u32 = expected_int & MASK_32
    is_zero = expected_u32 == 0
    is_neg = bool(expected_u32 & 0x80000000)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW) == is_ovf
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) == is_ovf
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO) == is_zero
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN) == is_neg
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.CARRY)

    res = user_pop32(fpga)
    assert res == expected_u32, f"Failed {desc}: got 0x{res:08X}, expected 0x{expected_u32:08X}"
    assert fpga.reg_file.sp.read_int() == 0


def test_user_opcode_conv_f32_i32_negative_nan(fpga: FpgaModel) -> None:
    """Tests negative NaN clamping to 0x80000000 with OVERFLOW=1, ERR=1."""
    neg_nan_bits = 0xFFC00000
    user_push32(fpga, neg_nan_bits)
    fpga.dispatcher.execute(UserOpcode.CONV_F32_I32)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)

    res = user_pop32(fpga)
    assert res == 0x80000000


def test_user_opcode_conv_f32_i32_underflow(fpga: FpgaModel) -> None:
    """Tests CONV_F32_I32 on empty stack traps with ERR=1 and preserves SP=0."""
    assert fpga.reg_file.sp.read_int() == 0
    fpga.dispatcher.execute(UserOpcode.CONV_F32_I32)
    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)


def test_user_opcode_conv_f32_i32_stack_preservation(fpga: FpgaModel) -> None:
    """Tests that CONV_F32_I32 leaves underlying stack elements intact."""
    user_push32(fpga, 0xDEADBEEF)
    user_push32(fpga, f32_to_bits(42.5))
    assert fpga.reg_file.sp.read_int() == 2

    fpga.dispatcher.execute(UserOpcode.CONV_F32_I32)
    assert fpga.reg_file.sp.read_int() == 2

    # Top element is 42
    assert user_pop32(fpga) == 42
    # Bottom element is preserved
    assert user_pop32(fpga) == 0xDEADBEEF
    assert fpga.reg_file.sp.read_int() == 0
