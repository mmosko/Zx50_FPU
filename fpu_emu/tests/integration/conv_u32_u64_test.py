"""Integration tests for UserOpcode.CONV_U32_U64 executed via the microcode dispatcher."""

import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import user_pop32, user_pop64, user_push32
from fpu_emu.user_opcodes import UserOpcode


@pytest.mark.parametrize(
    "val_32,expected_res_64,exp_zf",
    [
        (0, 0, True),
        (1, 1, False),
        (42, 42, False),
        (1000, 1000, False),
        (0x7FFFFFFF, 0x000000007FFFFFFF, False),
        (0x80000000, 0x0000000080000000, False),  # 2^31: bit 31 is 1, but for u64 bit 63 is 0 (SF=0)
        (0x80000001, 0x0000000080000001, False),
        (0xFFFFFFFE, 0x00000000FFFFFFFE, False),
        (0xFFFFFFFF, 0x00000000FFFFFFFF, False),  # 2^32 - 1
    ],
)
def test_user_opcode_conv_u32_u64(
    fpga: FpgaModel, val_32: int, expected_res_64: int, exp_zf: bool
) -> None:
    """Tests CONV_U32_U64 zero-extending unsigned 32-bit integer to 64-bit integer."""
    user_push32(fpga, val_32)
    assert fpga.reg_file.sp.read_int() == 1

    fpga.dispatcher.execute(UserOpcode.CONV_U32_U64)

    # Net stack effect is +4 bytes (+1 32-bit word), so SP goes from 1 to 2 words
    assert fpga.reg_file.sp.read_int() == 2
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)

    # Check flags: CARRY=0, OVERFLOW=0, SIGN=0 (always for u64), ZERO=(X==0)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.CARRY)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.SIGN)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO) == exp_zf

    res = user_pop64(fpga)
    assert res == expected_res_64
    assert fpga.reg_file.sp.read_int() == 0


def test_user_opcode_conv_u32_u64_underflow(fpga: FpgaModel) -> None:
    """Tests CONV_U32_U64 on empty stack traps with ERR=1 and preserves SP=0."""
    assert fpga.reg_file.sp.read_int() == 0
    fpga.dispatcher.execute(UserOpcode.CONV_U32_U64)
    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)


def test_user_opcode_conv_u32_u64_overflow(fpga: FpgaModel) -> None:
    """Tests CONV_U32_U64 when stack is full (SP=127) traps overflow on pushing second word."""
    # Set SP to maximum capacity (127 words)
    fpga.reg_file.sp.write(127)
    fpga.memory.write(0, fpga.memory_block.MTH_BASE | 126, 0x12345678)

    fpga.dispatcher.execute(UserOpcode.CONV_U32_U64)

    # After popping 1 word (SP=126), pushing 2 words will hit overflow on the second push
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)


def test_user_opcode_conv_u32_u64_stack_preservation(fpga: FpgaModel) -> None:
    """Tests that CONV_U32_U64 leaves underlying stack elements intact."""
    user_push32(fpga, 0xCAFEBABE)
    user_push32(fpga, 0x12345678)
    assert fpga.reg_file.sp.read_int() == 2

    fpga.dispatcher.execute(UserOpcode.CONV_U32_U64)
    assert fpga.reg_file.sp.read_int() == 3

    # Top element is 64-bit zero-extended 0x12345678
    assert user_pop64(fpga) == 0x0000000012345678
    assert fpga.reg_file.sp.read_int() == 1

    # Bottom element is preserved
    assert user_pop32(fpga) == 0xCAFEBABE
    assert fpga.reg_file.sp.read_int() == 0
