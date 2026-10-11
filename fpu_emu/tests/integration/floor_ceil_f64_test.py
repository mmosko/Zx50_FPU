"""Integration tests for UserOpcode.FLOOR_F64 and UserOpcode.CEIL_F64."""

import math
import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import bits_to_f64, f64_to_bits, user_pop32, user_pop64, user_push32, user_push64
from fpu_emu.user_opcodes import UserOpcode


@pytest.mark.parametrize(
    "x,expected_floor,expected_ceil,desc",
    [
        # Exact integers
        (0.0, 0.0, 0.0, "0.0"),
        (1.0, 1.0, 1.0, "1.0"),
        (-1.0, -1.0, -1.0, "-1.0"),
        (2.0, 2.0, 2.0, "2.0"),
        (-2.0, -2.0, -2.0, "-2.0"),
        (42.0, 42.0, 42.0, "42.0"),
        (-42.0, -42.0, -42.0, "-42.0"),
        (65535.0, 65535.0, 65535.0, "65535.0"),
        (-65535.0, -65535.0, -65535.0, "-65535.0"),
        (4503599627370496.0, 4503599627370496.0, 4503599627370496.0, "2^52"),
        (-4503599627370496.0, -4503599627370496.0, -4503599627370496.0, "-2^52"),
        (1e16, 1e16, 1e16, "1e16 > 2^52"),
        (-1e16, -1e16, -1e16, "-1e16 < -2^52"),
        # Fractions |x| < 1.0
        (0.1, 0.0, 1.0, "0.1"),
        (0.5, 0.0, 1.0, "0.5"),
        (0.999999999999, 0.0, 1.0, "0.999999999999"),
        (-0.1, -1.0, -0.0, "-0.1"),
        (-0.5, -1.0, -0.0, "-0.5"),
        (-0.999999999999, -1.0, -0.0, "-0.999999999999"),
        # Fractions |x| > 1.0
        (1.1, 1.0, 2.0, "1.1"),
        (1.5, 1.0, 2.0, "1.5"),
        (1.75, 1.0, 2.0, "1.75 (carries into 2.0)"),
        (1.999999999999, 1.0, 2.0, "1.999999999999"),
        (3.5, 3.0, 4.0, "3.5 (power of 2 boundary)"),
        (-1.1, -2.0, -1.0, "-1.1"),
        (-1.5, -2.0, -1.0, "-1.5"),
        (-1.75, -2.0, -1.0, "-1.75 (carries into -2.0)"),
        (-1.999999999999, -2.0, -1.0, "-1.999999999999"),
        (-3.5, -4.0, -3.0, "-3.5 (power of 2 boundary)"),
        (42.25, 42.0, 43.0, "42.25"),
        (-42.25, -43.0, -42.0, "-42.25"),
        (1234567890.125, 1234567890.0, 1234567891.0, "1234567890.125"),
        (-1234567890.125, -1234567891.0, -1234567890.0, "-1234567890.125"),
        (1e12 + 0.5, 1e12, 1e12 + 1.0, "1e12 + 0.5"),
        (-1e12 - 0.5, -1e12 - 1.0, -1e12, "-1e12 - 0.5"),
        # Special values
        (float("inf"), float("inf"), float("inf"), "+inf"),
        (float("-inf"), float("-inf"), float("-inf"), "-inf"),
    ],
)
def test_floor_ceil_f64_standard(
    fpga: FpgaModel, x: float, expected_floor: float, expected_ceil: float, desc: str
) -> None:
    """Tests FLOOR_F64 and CEIL_F64 across positive, negative, and fractional values."""
    # Test FLOOR_F64
    user_push64(fpga, f64_to_bits(x))
    assert fpga.reg_file.sp.read_int() == 2

    fpga.dispatcher.execute(UserOpcode.FLOOR_F64)
    assert fpga.reg_file.sp.read_int() == 2

    # Check status flags before pop
    exp_f_bits = f64_to_bits(expected_floor)
    is_zero = (exp_f_bits & 0x7FFFFFFFFFFFFFFF) == 0
    is_neg = bool(exp_f_bits & 0x8000000000000000)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO) == is_zero
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN) == is_neg
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.CARRY)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)

    res_floor_bits = user_pop64(fpga)
    assert res_floor_bits == exp_f_bits, (
        f"FLOOR failed on {desc}: got 0x{res_floor_bits:016X} ({bits_to_f64(res_floor_bits)}), "
        f"expected 0x{exp_f_bits:016X} ({expected_floor})"
    )

    # Test CEIL_F64
    user_push64(fpga, f64_to_bits(x))
    assert fpga.reg_file.sp.read_int() == 2

    fpga.dispatcher.execute(UserOpcode.CEIL_F64)
    assert fpga.reg_file.sp.read_int() == 2

    # Check status flags before pop
    exp_c_bits = f64_to_bits(expected_ceil)
    is_c_zero = (exp_c_bits & 0x7FFFFFFFFFFFFFFF) == 0
    is_c_neg = bool(exp_c_bits & 0x8000000000000000)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO) == is_c_zero
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN) == is_c_neg
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.CARRY)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)

    res_ceil_bits = user_pop64(fpga)
    assert res_ceil_bits == exp_c_bits, (
        f"CEIL failed on {desc}: got 0x{res_ceil_bits:016X} ({bits_to_f64(res_ceil_bits)}), "
        f"expected 0x{exp_c_bits:016X} ({expected_ceil})"
    )


def test_floor_ceil_f64_signed_zeros(fpga: FpgaModel) -> None:
    """Tests IEEE-754 signed zeros preservation: floor(+/-0) = +/-0, ceil(+/-0) = +/-0."""
    # +0.0
    user_push64(fpga, 0x0000000000000000)
    fpga.dispatcher.execute(UserOpcode.FLOOR_F64)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)
    assert user_pop64(fpga) == 0x0000000000000000

    user_push64(fpga, 0x0000000000000000)
    fpga.dispatcher.execute(UserOpcode.CEIL_F64)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)
    assert user_pop64(fpga) == 0x0000000000000000

    # -0.0
    user_push64(fpga, 0x8000000000000000)
    fpga.dispatcher.execute(UserOpcode.FLOOR_F64)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)
    assert user_pop64(fpga) == 0x8000000000000000

    user_push64(fpga, 0x8000000000000000)
    fpga.dispatcher.execute(UserOpcode.CEIL_F64)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)
    assert user_pop64(fpga) == 0x8000000000000000


def test_floor_ceil_f64_nan(fpga: FpgaModel) -> None:
    """Tests that NaN operands return NaN."""
    nan_bits = 0x7FF8000000000000
    user_push64(fpga, nan_bits)
    fpga.dispatcher.execute(UserOpcode.FLOOR_F64)
    res = user_pop64(fpga)
    assert math.isnan(bits_to_f64(res))

    user_push64(fpga, nan_bits)
    fpga.dispatcher.execute(UserOpcode.CEIL_F64)
    res = user_pop64(fpga)
    assert math.isnan(bits_to_f64(res))


def test_floor_ceil_f64_underflow(fpga: FpgaModel) -> None:
    """Tests stack underflow trap with ERR=1."""
    # 0 words on stack
    assert fpga.reg_file.sp.read_int() == 0
    fpga.dispatcher.execute(UserOpcode.FLOOR_F64)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)

    fpga.reg_file.status.set_bit(StatusFlag.ERR, False)
    fpga.dispatcher.execute(UserOpcode.CEIL_F64)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)

    # Only 1 32-bit word on stack (needs 2 for 64-bit operand)
    fpga.reg_file.status.set_bit(StatusFlag.ERR, False)
    user_push32(fpga, 0x12345678)
    assert fpga.reg_file.sp.read_int() == 1
    fpga.dispatcher.execute(UserOpcode.FLOOR_F64)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)


def test_floor_ceil_f64_stack_preservation(fpga: FpgaModel) -> None:
    """Tests that underlying stack elements remain untouched."""
    user_push32(fpga, 0xCAFEBABE)
    user_push64(fpga, f64_to_bits(1.75))
    assert fpga.reg_file.sp.read_int() == 3

    fpga.dispatcher.execute(UserOpcode.FLOOR_F64)
    assert fpga.reg_file.sp.read_int() == 3

    assert bits_to_f64(user_pop64(fpga)) == 1.0
    assert user_pop32(fpga) == 0xCAFEBABE
    assert fpga.reg_file.sp.read_int() == 0
