"""Integration tests for UserOpcode.CONV_U32_F32 and UserOpcode.CONV_I32_F32."""

import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import bits_to_f32, f32_to_bits, user_pop32, user_push32
from fpu_emu.user_opcodes import UserOpcode


def _u32_to_f32_bits(val: int) -> int:
    return f32_to_bits(float(val))


@pytest.mark.parametrize(
    "val_32",
    [
        0,
        1,
        2,
        3,
        42,
        100,
        1000,
        65535,
        65536,
        16777215,  # 2^24 - 1 (exact)
        16777216,  # 2^24 (exact)
        0x7FFFFFFF,  # 2^31 - 1
        0x80000000,  # 2^31
        0x80000001,
        0xFFFFFFFE,
        0xFFFFFFFF,  # 2^32 - 1
    ],
)
def test_user_opcode_conv_u32_f32(fpga: FpgaModel, val_32: int) -> None:
    """Tests CONV_U32_F32 converting unsigned 32-bit uint to IEEE-754 single float."""
    user_push32(fpga, val_32)
    assert fpga.reg_file.sp.read_int() == 1

    fpga.dispatcher.execute(UserOpcode.CONV_U32_F32)

    # In-place conversion (delta SP = 0)
    assert fpga.reg_file.sp.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)  # unsigned is always non-negative
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO) == (val_32 == 0)

    res = user_pop32(fpga)
    if val_32 <= 16777216 or val_32 == 0x80000000:
        expected = _u32_to_f32_bits(val_32)
        assert res == expected
    else:
        assert pytest.approx(bits_to_f32(res), rel=1e-6) == float(val_32)
    assert fpga.reg_file.sp.read_int() == 0


@pytest.mark.parametrize(
    "val_32",
    [
        0,
        1,
        -1,
        2,
        -2,
        42,
        -42,
        1000,
        -1000,
        16777215,
        -16777215,
        16777216,
        -16777216,
        0x7FFFFFFF,  # +2147483647
        -2147483648,  # -2^31 (0x80000000)
    ],
)
def test_user_opcode_conv_i32_f32(fpga: FpgaModel, val_32: int) -> None:
    """Tests CONV_I32_F32 converting signed 32-bit int to IEEE-754 single float."""
    user_push32(fpga, val_32 & 0xFFFFFFFF)
    assert fpga.reg_file.sp.read_int() == 1

    fpga.dispatcher.execute(UserOpcode.CONV_I32_F32)

    # In-place conversion (delta SP = 0)
    assert fpga.reg_file.sp.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)

    is_neg = val_32 < 0
    is_zero = val_32 == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO) == is_zero
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN) == is_neg

    res = user_pop32(fpga)
    if abs(val_32) <= 16777216 or val_32 == -2147483648:
        expected = f32_to_bits(float(val_32))
        assert res == expected
    else:
        assert pytest.approx(bits_to_f32(res), rel=1e-6) == float(val_32)
    assert fpga.reg_file.sp.read_int() == 0


def test_user_opcode_conv_u32_f32_underflow(fpga: FpgaModel) -> None:
    """Tests CONV_U32_F32 on empty stack traps with ERR=1 and preserves SP=0."""
    assert fpga.reg_file.sp.read_int() == 0
    fpga.dispatcher.execute(UserOpcode.CONV_U32_F32)
    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)


def test_user_opcode_conv_i32_f32_underflow(fpga: FpgaModel) -> None:
    """Tests CONV_I32_F32 on empty stack traps with ERR=1 and preserves SP=0."""
    assert fpga.reg_file.sp.read_int() == 0
    fpga.dispatcher.execute(UserOpcode.CONV_I32_F32)
    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)


def test_user_opcode_conv_int_f32_stack_preservation(fpga: FpgaModel) -> None:
    """Tests that CONV_I32_F32 leaves underlying stack elements intact."""
    user_push32(fpga, 0xCAFEBABE)
    user_push32(fpga, 42)
    assert fpga.reg_file.sp.read_int() == 2

    fpga.dispatcher.execute(UserOpcode.CONV_I32_F32)
    assert fpga.reg_file.sp.read_int() == 2

    # Top element is 42.0f
    assert user_pop32(fpga) == f32_to_bits(42.0)
    # Bottom element is preserved
    assert user_pop32(fpga) == 0xCAFEBABE
    assert fpga.reg_file.sp.read_int() == 0
