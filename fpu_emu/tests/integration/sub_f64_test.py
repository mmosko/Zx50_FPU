"""Integration tests for UserOpcode.SUB_F64 executed via the microcode dispatcher."""

import pytest
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import bits_to_f64, f64_to_bits, user_pop64, user_push64
from fpu_emu.user_opcodes import UserOpcode


@pytest.mark.parametrize(
    "a,b,expected,desc",
    [
        # Simple positive subtractions
        (3.0, 1.0, 2.0, "3.0 - 1.0"),
        (1.0, 2.0, -1.0, "1.0 - 2.0 (A < B -> negative)"),
        (2.5, 1.5, 1.0, "2.5 - 1.5"),
        (4.0, 1.5, 2.5, "4.0 - 1.5"),
        (111.11111101111, 98.765432109876, 12.345678901234, "High-precision subtraction"),
        # Subtraction with operand swap (A < B in magnitude)
        (0.25, 1.75, -1.5, "0.25 - 1.75"),
        (1.0, 5.0, -4.0, "1.0 - 5.0"),
        (1.0, 1.5, -0.5, "1.0 - 1.5 (same exp, B mantissa larger)"),
        # Subtracting negative numbers (effective addition)
        (1.0, -2.0, 3.0, "1.0 - (-2.0)"),
        (-1.0, 2.0, -3.0, "-1.0 - 2.0"),
        (-1.0, -2.0, 1.0, "-1.0 - (-2.0)"),
        (-2.0, -1.0, -1.0, "-2.0 - (-1.0)"),
        (-5.0, -2.0, -3.0, "-5.0 - (-2.0)"),
        (-2.0, -5.0, 3.0, "-2.0 - (-5.0)"),
        # Exact cancellation to zero
        (1.0, 1.0, 0.0, "1.0 - 1.0 (exact cancellation)"),
        (2.5, 2.5, 0.0, "2.5 - 2.5 (exact cancellation)"),
        (-5.0, -5.0, 0.0, "-5.0 - (-5.0) (exact cancellation)"),
        # Leading bit cancellation (left normalization)
        (1.00000000000005, 1.0, 5e-14, "Leading bit cancellation"),
        (2.0, 1.9999999999999, 1e-13, "Near-equality cancellation"),
        # Zero operand handling
        (5.0, 0.0, 5.0, "5.0 - 0.0"),
        (0.0, 5.0, -5.0, "0.0 - 5.0"),
        (-5.0, 0.0, -5.0, "-5.0 - 0.0"),
        (0.0, -5.0, 5.0, "0.0 - (-5.0)"),
        (0.0, 0.0, 0.0, "0.0 - 0.0"),
        # Exponent differences >= 54 (smaller mantissa shifts completely out)
        (1000.0, 1e-20, 1000.0, "1000.0 - 1e-20 (diff > 53)"),
        (1e-20, 1000.0, -1000.0, "1e-20 - 1000.0 (diff > 53, swapped)"),
    ],
)
def test_user_opcode_sub_f64(fpga: FpgaModel, a: float, b: float, expected: float, desc: str) -> None:
    """Tests executing UserOpcode.SUB_F64 via dispatcher."""
    user_push64(fpga, f64_to_bits(a))
    user_push64(fpga, f64_to_bits(b))
    assert fpga.reg_file.sp.read_int() == 4

    # Execute SUB_F64
    fpga.dispatcher.execute(UserOpcode.SUB_F64)

    # After SUB_F64, stack pointer should be 2
    assert fpga.reg_file.sp.read_int() == 2
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)

    # Pop result from stack
    res_bits = user_pop64(fpga)
    res_float = bits_to_f64(res_bits)
    assert fpga.reg_file.sp.read_int() == 0

    if expected == 0.0:
        assert res_float == 0.0, f"Failed {desc}: got {res_float}, expected 0.0"
    else:
        assert pytest.approx(res_float, rel=1e-12) == expected, f"Failed {desc}: got {res_float}, expected {expected}"


def test_sub_f64_stack_underflow(fpga: FpgaModel) -> None:
    """Tests that SUB_F64 with empty stack asserts ERR (not UNDERFLOW)."""
    fpga.dispatcher.execute(UserOpcode.SUB_F64)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)


def test_sub_f64_stack_single_operand(fpga: FpgaModel) -> None:
    """Tests that SUB_F64 with only one operand on stack asserts ERR (not UNDERFLOW)."""
    user_push64(fpga, f64_to_bits(1.0))
    fpga.dispatcher.execute(UserOpcode.SUB_F64)
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    assert not fpga.reg_file.status.is_bit_set(StatusFlag.UNDERFLOW)
