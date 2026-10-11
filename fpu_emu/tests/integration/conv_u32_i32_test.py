"""Integration tests for UserOpcode.CONV_U32_I32 and UserOpcode.CONV_I32_U32."""

import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import user_pop32, user_push32
from fpu_emu.user_opcodes import UserOpcode


@pytest.mark.parametrize(
    "val_32,expected_res,exp_zf,exp_sf,exp_vf",
    [
        (0, 0, True, False, False),
        (1, 1, False, False, False),
        (42, 42, False, False, False),
        (1000, 1000, False, False, False),
        (0x7FFFFFFF, 0x7FFFFFFF, False, False, False),  # 2^31 - 1: max representable positive
        (0x80000000, 0x80000000, False, True, True),  # 2^31: overflow into negative
        (0x80000001, 0x80000001, False, True, True),
        (0xFFFFFFFE, 0xFFFFFFFE, False, True, True),
        (0xFFFFFFFF, 0xFFFFFFFF, False, True, True),  # 2^32 - 1: overflow into negative
    ],
)
def test_user_opcode_conv_u32_i32(
    fpga: FpgaModel, val_32: int, expected_res: int, exp_zf: bool, exp_sf: bool, exp_vf: bool
) -> None:
    """Tests CONV_U32_I32 converting unsigned 32-bit int to signed 32-bit int with range check."""
    user_push32(fpga, val_32)
    assert fpga.reg_file.sp.read_int() == 1

    fpga.dispatcher.execute(UserOpcode.CONV_U32_I32)

    # In-place conversion (net delta SP = 0)
    assert fpga.reg_file.sp.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.CARRY)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO) == exp_zf
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN) == exp_sf
    assert fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW) == exp_vf

    res = user_pop32(fpga)
    assert res == expected_res
    assert fpga.reg_file.sp.read_int() == 0


@pytest.mark.parametrize(
    "val_32,expected_res,exp_zf,exp_sf,exp_vf",
    [
        (0, 0, True, False, False),
        (1, 1, False, False, False),
        (42, 42, False, False, False),
        (1000, 1000, False, False, False),
        (0x7FFFFFFF, 0x7FFFFFFF, False, False, False),  # +2147483647: valid unsigned
        (-1, 0xFFFFFFFF, False, True, True),  # negative -> overflow (bit 31 is 1)
        (-2, 0xFFFFFFFE, False, True, True),
        (-2147483648, 0x80000000, False, True, True),  # -2^31 -> overflow (bit 31 is 1)
        (0x80000000, 0x80000000, False, True, True),
    ],
)
def test_user_opcode_conv_i32_u32(
    fpga: FpgaModel, val_32: int, expected_res: int, exp_zf: bool, exp_sf: bool, exp_vf: bool
) -> None:
    """Tests CONV_I32_U32 converting signed 32-bit int to unsigned 32-bit int with range check."""
    user_push32(fpga, val_32)
    assert fpga.reg_file.sp.read_int() == 1

    fpga.dispatcher.execute(UserOpcode.CONV_I32_U32)

    # In-place conversion (net delta SP = 0)
    assert fpga.reg_file.sp.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.CARRY)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO) == exp_zf
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN) == exp_sf
    assert fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW) == exp_vf

    res = user_pop32(fpga)
    assert res == expected_res
    assert fpga.reg_file.sp.read_int() == 0


def test_user_opcode_conv_u32_i32_underflow(fpga: FpgaModel) -> None:
    """Tests CONV_U32_I32 on empty stack traps with ERR=1 and preserves SP=0."""
    assert fpga.reg_file.sp.read_int() == 0
    fpga.dispatcher.execute(UserOpcode.CONV_U32_I32)
    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)


def test_user_opcode_conv_i32_u32_underflow(fpga: FpgaModel) -> None:
    """Tests CONV_I32_U32 on empty stack traps with ERR=1 and preserves SP=0."""
    assert fpga.reg_file.sp.read_int() == 0
    fpga.dispatcher.execute(UserOpcode.CONV_I32_U32)
    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)


def test_user_opcode_conv_u32_i32_stack_preservation(fpga: FpgaModel) -> None:
    """Tests that CONV_U32_I32 leaves underlying stack elements intact."""
    user_push32(fpga, 0xCAFEBABE)
    user_push32(fpga, 0x12345678)
    assert fpga.reg_file.sp.read_int() == 2

    fpga.dispatcher.execute(UserOpcode.CONV_U32_I32)
    assert fpga.reg_file.sp.read_int() == 2

    assert user_pop32(fpga) == 0x12345678
    assert user_pop32(fpga) == 0xCAFEBABE
    assert fpga.reg_file.sp.read_int() == 0
