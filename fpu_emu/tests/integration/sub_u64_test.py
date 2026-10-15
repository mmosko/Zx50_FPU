"""Integration tests for UserOpcode.SUB_U64 executed via the microcode dispatcher."""

import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import user_pop64, user_push32, user_push64
from fpu_emu.user_opcodes import UserOpcode


@pytest.mark.parametrize(
    "a,b,expected_res,exp_cf,exp_zf,exp_sf,desc",
    [
        (0, 0, 0, False, True, False, "zero - zero"),
        (35, 10, 25, False, False, False, "35 - 10 = 25"),
        (10, 35, 0xFFFFFFFFFFFFFFE7, True, False, True, "10 - 35 = -25 (borrow)"),
        (300, 100, 200, False, False, False, "300 - 100 = 200"),
        (0x00000002_00000000, 1, 0x00000001_FFFFFFFF, False, False, False, "borrow from high word"),
        (0x00000003_00000000, 0x00000001_00000000, 0x00000002_00000000, False, False, False, "high words only"),
        (0, 1, 0xFFFFFFFFFFFFFFFF, True, False, True, "0 - 1 = max uint64 (borrow)"),
        (0xFFFFFFFFFFFFFFFF, 0xFFFFFFFFFFFFFFFF, 0, False, True, False, "max uint64 - max uint64"),
        (0xFFFFFFFFFFFFFFFF, 1, 0xFFFFFFFFFFFFFFFE, False, False, True, "max uint64 - 1"),
    ],
)
def test_user_opcode_sub_u64(
    fpga: FpgaModel, a: int, b: int, expected_res: int, exp_cf: bool, exp_zf: bool, exp_sf: bool, desc: str
) -> None:
    """Tests executing UserOpcode.SUB_U64 via dispatcher with 64-bit stack operands (a - b)."""
    user_push64(fpga, a)
    user_push64(fpga, b)
    assert fpga.reg_file.sp.read_int() == 4

    fpga.dispatcher.execute(UserOpcode.SUB_U64)

    assert fpga.reg_file.sp.read_int() == 2
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.CARRY) == exp_cf
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ZERO) == exp_zf
    assert fpga.reg_file.status.is_bit_set(StatusFlag.SIGN) == exp_sf
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)

    res = user_pop64(fpga)
    assert res == expected_res, desc
    assert fpga.reg_file.sp.read_int() == 0


def test_sub_u64_underflow_empty_stack(fpga: FpgaModel) -> None:
    """Executing SUB_U64 with empty stack must trigger underflow and set ERR (not UNDERFLOW)."""
    assert fpga.reg_file.sp.read_int() == 0

    fpga.dispatcher.execute(UserOpcode.SUB_U64)

    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)


def test_sub_u64_underflow_single_word(fpga: FpgaModel) -> None:
    """Executing SUB_U64 with only one 32-bit word must trigger underflow during first 64-bit pop."""
    user_push32(fpga, 42)
    assert fpga.reg_file.sp.read_int() == 1

    fpga.dispatcher.execute(UserOpcode.SUB_U64)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)


def test_sub_u64_underflow_single_operand(fpga: FpgaModel) -> None:
    """Executing SUB_U64 with only one 64-bit operand must trigger underflow during second 64-bit pop."""
    user_push64(fpga, 42)
    assert fpga.reg_file.sp.read_int() == 2

    fpga.dispatcher.execute(UserOpcode.SUB_U64)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)


def test_sub_u64_underflow_three_words(fpga: FpgaModel) -> None:
    """Executing SUB_U64 with 3 words (1 full operand + half of second) must trigger underflow."""
    user_push64(fpga, 100)
    user_push32(fpga, 200)
    assert fpga.reg_file.sp.read_int() == 3

    fpga.dispatcher.execute(UserOpcode.SUB_U64)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
