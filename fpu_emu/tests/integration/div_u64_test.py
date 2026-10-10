"""Integration tests for UserOpcode.DIV_U64 executed via the microcode dispatcher."""

import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import user_pop64, user_push32, user_push64
from fpu_emu.user_opcodes import UserOpcode

MASK_64 = 0xFFFFFFFFFFFFFFFF


@pytest.mark.parametrize(
    "a,b,expected_quot,exp_zf,exp_sf,desc",
    [
        (100, 5, 20, False, False, "100 / 5 = 20"),
        (7, 2, 3, False, False, "7 / 2 = 3"),
        (0, 15, 0, True, False, "0 / 15 = 0"),
        (10, 20, 0, True, False, "10 / 20 = 0 (dividend < divisor)"),
        # Crossing 32-bit boundary into high word
        (0x1_00000000, 2, 0x80000000, False, False, "2^32 / 2 = 2^31"),
        (0x12345678_9ABCDEF0, 1, 0x12345678_9ABCDEF0, False, False, "X / 1 = X"),
        (0xFFFFFFFF_FFFFFFFF, 1, 0xFFFFFFFF_FFFFFFFF, False, True, "max_uint64 / 1 (MSB set)"),
        (0xFFFFFFFF_FFFFFFFF, 0xFFFFFFFF_FFFFFFFF, 1, False, False, "max_uint64 / max_uint64 = 1"),
        (0xFFFFFFFF_FFFFFFFF, 2, 0x7FFFFFFF_FFFFFFFF, False, False, "max_uint64 / 2"),
        (0x80000000_00000000, 2, 0x40000000_00000000, False, False, "2^63 / 2 = 2^62"),
        (0x80000000_00000000, 0x80000000_00000000, 1, False, False, "2^63 / 2^63 = 1"),
    ],
)
def test_user_opcode_div_u64(
    fpga: FpgaModel,
    a: int,
    b: int,
    expected_quot: int,
    exp_zf: bool,
    exp_sf: bool,
    desc: str,
) -> None:
    """Tests executing UserOpcode.DIV_U64 via dispatcher with 64-bit stack operands (a / b)."""
    user_push64(fpga, a & MASK_64)
    user_push64(fpga, b & MASK_64)
    assert fpga.reg_file.sp.read_int() == 4

    fpga.dispatcher.execute(UserOpcode.DIV_U64)

    assert fpga.reg_file.sp.read_int() == 2
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO) == exp_zf
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN) == exp_sf
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)

    res = user_pop64(fpga)
    assert res == expected_quot & MASK_64
    assert fpga.reg_file.sp.read_int() == 0


def test_user_opcode_div_u64_divide_by_zero(fpga: FpgaModel) -> None:
    """Tests executing UserOpcode.DIV_U64 with divisor 0 triggers ERR and OVERFLOW, aborting push."""
    user_push64(fpga, 42)
    user_push64(fpga, 0)
    assert fpga.reg_file.sp.read_int() == 4

    fpga.dispatcher.execute(UserOpcode.DIV_U64)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)
    assert fpga.reg_file.sp.read_int() == 0


def test_div_u64_underflow_empty_stack(fpga: FpgaModel) -> None:
    """Executing DIV_U64 with empty stack must trigger underflow and set ERR & UNDERFLOW."""
    assert fpga.reg_file.sp.read_int() == 0

    fpga.dispatcher.execute(UserOpcode.DIV_U64)

    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True


def test_div_u64_underflow_single_word(fpga: FpgaModel) -> None:
    """Executing DIV_U64 with only one 32-bit word must trigger underflow."""
    user_push32(fpga, 42)
    assert fpga.reg_file.sp.read_int() == 1

    fpga.dispatcher.execute(UserOpcode.DIV_U64)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True


def test_div_u64_underflow_single_operand(fpga: FpgaModel) -> None:
    """Executing DIV_U64 with only one 64-bit operand must trigger underflow on 2nd pop."""
    user_push64(fpga, 42)
    assert fpga.reg_file.sp.read_int() == 2

    fpga.dispatcher.execute(UserOpcode.DIV_U64)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True


def test_div_u64_underflow_three_words(fpga: FpgaModel) -> None:
    """Executing DIV_U64 with 3 words must trigger underflow."""
    user_push64(fpga, 100)
    user_push32(fpga, 200)
    assert fpga.reg_file.sp.read_int() == 3

    fpga.dispatcher.execute(UserOpcode.DIV_U64)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW) is True
