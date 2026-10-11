"""Integration tests for UserOpcode.CONV_I64_I32 executed via the microcode dispatcher."""

import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import user_pop32, user_push32, user_push64
from fpu_emu.user_opcodes import UserOpcode


@pytest.mark.parametrize(
    "val_64,expected_res,exp_zf,exp_sf,exp_vf",
    [
        # --- In-Range Conversions (VF = False) ---
        (0, 0, True, False, False),
        (1, 1, False, False, False),
        (42, 42, False, False, False),
        (123456, 123456, False, False, False),
        (0x7FFFFFFF, 0x7FFFFFFF, False, False, False),  # Max 32-bit positive
        (0xFFFFFFFFFFFFFFFF, 0xFFFFFFFF, False, True, False),  # -1
        ((-42) & 0xFFFFFFFFFFFFFFFF, (-42) & 0xFFFFFFFF, False, True, False),
        ((-123456) & 0xFFFFFFFFFFFFFFFF, (-123456) & 0xFFFFFFFF, False, True, False),
        (0xFFFFFFFF80000000, 0x80000000, False, True, False),  # Min 32-bit negative (-2^31)
        (0xFFFFFFFF80000001, 0x80000001, False, True, False),  # -2^31 + 1
        (0xFFFFFFFFFFFFFFFE, 0xFFFFFFFE, False, True, False),  # -2
        # --- Positive Overflow Conversions (VF = True) ---
        (0x0000000080000000, 0x80000000, False, True, True),  # 2^31 (truncated to negative 32-bit int)
        (0x0000000100000000, 0x00000000, True, False, True),  # 2^32 (truncated to 0)
        (0x0000000112345678, 0x12345678, False, False, True),
        (0x7FFFFFFFFFFFFFFF, 0xFFFFFFFF, False, True, True),  # Max 64-bit positive
        (0x1234567800000000, 0x00000000, True, False, True),
        (0x123456787FFFFFFF, 0x7FFFFFFF, False, False, True),
        # --- Negative Overflow Conversions (VF = True) ---
        (0xFFFFFFFF7FFFFFFF, 0x7FFFFFFF, False, False, True),  # -2^31 - 1
        (0xFFFFFFFF00000000, 0x00000000, True, False, True),  # -2^32
        (0x8000000000000000, 0x00000000, True, False, True),  # Min 64-bit negative (-2^63)
        (0x800000007FFFFFFF, 0x7FFFFFFF, False, False, True),
        (0x8000000080000000, 0x80000000, False, True, True),
    ],
)
def test_user_opcode_conv_i64_i32(
    fpga: FpgaModel, val_64: int, expected_res: int, exp_zf: bool, exp_sf: bool, exp_vf: bool
) -> None:
    """Tests CONV_I64_I32 narrowing signed 64-bit integer to 32-bit integer."""
    user_push64(fpga, val_64)
    assert fpga.reg_file.sp.read_int() == 2

    fpga.dispatcher.execute(UserOpcode.CONV_I64_I32)

    # Net stack effect is -4 bytes (-1 32-bit word), so SP goes from 2 to 1 word
    assert fpga.reg_file.sp.read_int() == 1
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)

    # Check flags: CARRY=0, OVERFLOW, ZERO, SIGN
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.CARRY)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW) == exp_vf
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO) == exp_zf
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN) == exp_sf

    res = user_pop32(fpga)
    assert res == expected_res
    assert fpga.reg_file.sp.read_int() == 0


def test_user_opcode_conv_i64_i32_underflow_empty(fpga: FpgaModel) -> None:
    """Tests CONV_I64_I32 on empty stack traps with ERR=1 and preserves SP=0."""
    assert fpga.reg_file.sp.read_int() == 0
    fpga.dispatcher.execute(UserOpcode.CONV_I64_I32)
    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)


def test_user_opcode_conv_i64_i32_underflow_one_word(fpga: FpgaModel) -> None:
    """Tests CONV_I64_I32 when stack has only 1 word (4 bytes < 8 bytes required)."""
    user_push32(fpga, 0x12345678)
    assert fpga.reg_file.sp.read_int() == 1

    fpga.dispatcher.execute(UserOpcode.CONV_I64_I32)

    # Underflow must set ERR=1
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)


def test_user_opcode_conv_i64_i32_stack_preservation(fpga: FpgaModel) -> None:
    """Tests that CONV_I64_I32 leaves underlying stack elements intact."""
    user_push32(fpga, 0xDEADBEEF)
    user_push64(fpga, 100)
    assert fpga.reg_file.sp.read_int() == 3

    fpga.dispatcher.execute(UserOpcode.CONV_I64_I32)
    assert fpga.reg_file.sp.read_int() == 2

    # Top element is 100 (32-bit)
    assert user_pop32(fpga) == 100
    assert fpga.reg_file.sp.read_int() == 1

    # Bottom element is preserved
    assert user_pop32(fpga) == 0xDEADBEEF
    assert fpga.reg_file.sp.read_int() == 0
