"""Integration tests for UserOpcode.MUL_U64 executed via the microcode dispatcher."""

import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import user_pop64, user_push32, user_push64
from fpu_emu.user_opcodes import UserOpcode

MASK_64 = 0xFFFFFFFFFFFFFFFF


@pytest.mark.parametrize(
    "a,b,expected_res,exp_cf,desc",
    [
        (0, 0, 0, False, "zero * zero"),
        (10, 0, 0, False, "positive * zero"),
        (0, 10, 0, False, "zero * positive"),
        (10, 25, 250, False, "small positive integers: 10 * 25"),
        (100000, 200000, 20000000000, False, "100,000 * 200,000 = 20,000,000,000"),
        # Crossing 32-bit boundary into high word without 64-bit overflow
        (0x1_00000000, 3, 0x3_00000000, False, "2^32 * 3 = 3 * 2^32"),
        (0x1_00000002, 3, 0x3_00000006, False, "cross term fits in 64 bits"),
        (0x12345678_9ABCDEF0, 1, 0x12345678_9ABCDEF0, False, "X * 1 = X"),
        (0x7FFFFFFF_FFFFFFFF, 2, 0xFFFFFFFF_FFFFFFFE, False, "max signed int64 * 2 fits in uint64"),
        # 64-bit unsigned overflow (CF = True)
        (0x1_00000002, 0x2_00000003, 0x7_00000006, True, "cross terms with both high words non-zero (overflow)"),
        (0x2_00000000, 0x2_00000000, 0, True, "2^33 * 2^33 = 2^66 -> wraps to 0 mod 2^64 (overflow)"),
        (0xFFFFFFFF_FFFFFFFF, 2, 0xFFFFFFFF_FFFFFFFE, True, "(2^64 - 1) * 2 wraps mod 2^64 (overflow)"),
        (0xFFFFFFFF_FFFFFFFF, 0xFFFFFFFF_FFFFFFFF, 1, True, "(2^64 - 1)^2 wraps to 1 mod 2^64 (overflow)"),
    ],
)
def test_user_opcode_mul_u64(fpga: FpgaModel, a: int, b: int, expected_res: int, exp_cf: bool, desc: str) -> None:
    """Tests executing UserOpcode.MUL_U64 via dispatcher with 64-bit stack operands."""
    user_push64(fpga, a)
    user_push64(fpga, b)
    assert fpga.reg_file.sp.read_int() == 4

    fpga.dispatcher.execute(UserOpcode.MUL_U64)

    assert fpga.reg_file.sp.read_int() == 2
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.CARRY) == exp_cf
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.OVERFLOW)

    res = user_pop64(fpga)
    assert res == expected_res, desc
    assert fpga.reg_file.sp.read_int() == 0


def test_mul_u64_underflow_empty_stack(fpga: FpgaModel) -> None:
    """Executing MUL_U64 with empty stack must trigger underflow and set ERR (not UNDERFLOW)."""
    assert fpga.reg_file.sp.read_int() == 0

    fpga.dispatcher.execute(UserOpcode.MUL_U64)

    assert fpga.reg_file.sp.read_int() == 0
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)


def test_mul_u64_underflow_single_word(fpga: FpgaModel) -> None:
    """Executing MUL_U64 with only 1 word on stack must trigger underflow."""
    user_push32(fpga, 42)
    assert fpga.reg_file.sp.read_int() == 1

    fpga.dispatcher.execute(UserOpcode.MUL_U64)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)


def test_mul_u64_underflow_single_operand(fpga: FpgaModel) -> None:
    """Executing MUL_U64 with only 1 64-bit operand must trigger underflow on 2nd pop."""
    user_push64(fpga, 42)
    assert fpga.reg_file.sp.read_int() == 2

    fpga.dispatcher.execute(UserOpcode.MUL_U64)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)


def test_mul_u64_underflow_three_words(fpga: FpgaModel) -> None:
    """Executing MUL_U64 with 3 words must trigger underflow."""
    user_push64(fpga, 100)
    user_push32(fpga, 200)
    assert fpga.reg_file.sp.read_int() == 3

    fpga.dispatcher.execute(UserOpcode.MUL_U64)

    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR) is True
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
