"""Integration tests for UserOpcode.CONV_I32_I64 executed via the microcode dispatcher."""

import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import user_pop64, user_push32
from fpu_emu.user_opcodes import UserOpcode


@pytest.mark.parametrize(
    "val,expected_res,exp_zf,exp_sf",
    [
        (0, 0, True, False),
        (1, 1, False, False),
        (42, 42, False, False),
        (1000, 1000, False, False),
        (0x7FFFFFFF, 0x000000007FFFFFFF, False, False),  # max positive 32-bit int
        (0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF, False, True),  # -1 sign-extended
        ((-42) & 0xFFFFFFFF, (-42) & 0xFFFFFFFFFFFFFFFF, False, True),
        ((-1000) & 0xFFFFFFFF, (-1000) & 0xFFFFFFFFFFFFFFFF, False, True),
        (0x80000000, 0xFFFFFFFF80000000, False, True),  # min negative 32-bit int (-2147483648)
        (0x80000001, 0xFFFFFFFF80000001, False, True),
        (0xFFFFFFFE, 0xFFFFFFFFFFFFFFFE, False, True),  # -2
    ],
)
def test_user_opcode_conv_i32_i64(
    fpga: FpgaModel, val: int, expected_res: int, exp_zf: bool, exp_sf: bool
) -> None:
    """Tests CONV_I32_I64 widening signed 32-bit integer to 64-bit integer."""
    user_push32(fpga, val)
    assert fpga.reg_file.sp.read_int() == 1

    fpga.dispatcher.execute(UserOpcode.CONV_I32_I64)

    # Net stack effect is +4 bytes (+1 32-bit word), so SP goes from 1 to 2 words
    assert fpga.reg_file.sp.read_int() == 2
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)

    # Check flags: CARRY=0, OVERFLOW=0, ZERO, SIGN
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.CARRY)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO) == exp_zf
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN) == exp_sf

    res = user_pop64(fpga)
    assert res == expected_res


def test_user_opcode_conv_i32_i64_underflow(fpga: FpgaModel) -> None:
    """Tests CONV_I32_I64 on empty stack traps with ERR=1 and preserves SP=0."""
    assert fpga.reg_file.sp.read_int() == 0
    fpga.dispatcher.execute(UserOpcode.CONV_I32_I64)
    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)


def test_user_opcode_conv_i32_i64_overflow(fpga: FpgaModel) -> None:
    """Tests CONV_I32_I64 when stack is full (SP=127) traps overflow on the second push."""
    # Set SP to maximum capacity (127 words)
    fpga.reg_file.sp.write(127)
    assert fpga.reg_file.sp.read_int() == 127

    # CONV_I32_I64 will pop 1 word (SP -> 126), push word 1 (SP -> 127),
    # then push word 2 (SP -> 128 > 127) -> traps overflow with ERR=1
    fpga.dispatcher.execute(UserOpcode.CONV_I32_I64)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
