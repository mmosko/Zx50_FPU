"""Integration tests for CONV_F64_I64 (0xCF) user opcode."""

import pytest

from fpu_emu.dispatcher import UserOpcode
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import (
    f64_to_bits,
    user_pop32,
    user_pop64,
    user_push32,
    user_push64,
)


def run_conv_f64_i64(fpga: FpgaModel, float_val: float) -> tuple[int, int]:
    """Executes CONV_F64_I64 on the FPGA model with the given float."""
    user_push64(fpga, f64_to_bits(float_val))
    fpga.dispatcher.execute(UserOpcode.CONV_F64_I64)
    status = fpga.reg_file.status.read_int()
    result_bits = user_pop64(fpga)
    return result_bits, status


class TestConvF64I64Normals:
    """Tests normal conversions within valid 64-bit signed integer range."""

    @pytest.mark.parametrize(
        ("val", "expected_int"),
        [
            (1.0, 1),
            (-1.0, -1),
            (1.25, 1),
            (-1.25, -1),
            (1.9999, 1),
            (-1.9999, -1),
            (2.0, 2),
            (-2.0, -2),
            (42.0, 42),
            (-42.0, -42),
            (42.875, 42),
            (-42.875, -42),
            (100.0, 100),
            (-100.0, -100),
            (1000.5, 1000),
            (-1000.5, -1000),
            (65535.0, 65535),
            (-65535.0, -65535),
            (2147483647.0, 2147483647),  # 2^31 - 1
            (-2147483648.0, -2147483648),  # -2^31
            (9007199254740991.0, 9007199254740991),  # 2^53 - 1
            (-9007199254740991.0, -9007199254740991),
            (9007199254740992.0, 9007199254740992),  # 2^53
            (-9007199254740992.0, -9007199254740992),
            (4611686018427387904.0, 4611686018427387904),  # 2^62
            (-4611686018427387904.0, -4611686018427387904),
            (-9223372036854775808.0, -9223372036854775808),  # -2^63 exact
        ],
    )
    def test_normal_values(self, fpga: FpgaModel, val: float, expected_int: int) -> None:
        res_bits, status = run_conv_f64_i64(fpga, val)
        expected_bits = expected_int if expected_int >= 0 else (1 << 64) + expected_int

        assert res_bits == expected_bits
        assert bool(status & (1 << StatusFlag.ZERO.value)) is False
        assert bool(status & (1 << StatusFlag.SIGN.value)) is (expected_int < 0)
        assert bool(status & (1 << StatusFlag.OVERFLOW.value)) is False
        assert bool(status & (1 << StatusFlag.ERR.value)) is False

    @pytest.mark.parametrize(
        "val",
        [
            0.0,
            -0.0,
            0.5,
            -0.5,
            0.999999,
            -0.999999,
            1e-10,
            -1e-10,
            1e-300,
            -1e-300,
        ],
    )
    def test_zeros_and_sub_unit(self, fpga: FpgaModel, val: float) -> None:
        """Values in (-1.0, 1.0) truncate toward zero yielding 0."""
        res_bits, status = run_conv_f64_i64(fpga, val)

        assert res_bits == 0
        assert bool(status & (1 << StatusFlag.ZERO.value)) is True
        assert bool(status & (1 << StatusFlag.SIGN.value)) is False
        assert bool(status & (1 << StatusFlag.OVERFLOW.value)) is False
        assert bool(status & (1 << StatusFlag.ERR.value)) is False


class TestConvF64I64Overflow:
    """Tests overflow and clamp behavior for out-of-range floats, infinities, and NaN."""

    @pytest.mark.parametrize(
        ("val", "expected_clamp", "expected_sign"),
        [
            (9223372036854775808.0, 0x7FFFFFFFFFFFFFFF, False),  # +2^63
            (1e20, 0x7FFFFFFFFFFFFFFF, False),
            (1e300, 0x7FFFFFFFFFFFFFFF, False),
            (float("inf"), 0x7FFFFFFFFFFFFFFF, False),
            (float("nan"), 0x7FFFFFFFFFFFFFFF, False),
            (-9223372036854777856.0, 0x8000000000000000, True),  # < -2^63
            (-1e20, 0x8000000000000000, True),
            (-1e300, 0x8000000000000000, True),
            (float("-inf"), 0x8000000000000000, True),
        ],
    )
    def test_overflow_cases(self, fpga: FpgaModel, val: float, expected_clamp: int, expected_sign: bool) -> None:
        res_bits, status = run_conv_f64_i64(fpga, val)

        assert res_bits == expected_clamp
        assert bool(status & (1 << StatusFlag.OVERFLOW.value)) is True
        assert bool(status & (1 << StatusFlag.ERR.value)) is True
        assert bool(status & (1 << StatusFlag.SIGN.value)) is expected_sign


class TestConvF64I64Stack:
    """Tests stack depth invariants and underflow handling."""

    def test_net_stack_depth(self, fpga: FpgaModel) -> None:
        user_push32(fpga, 0xCAFEBABE)
        user_push64(fpga, f64_to_bits(-42.75))

        assert fpga.reg_file.sp.read_int() == 3

        fpga.dispatcher.execute(UserOpcode.CONV_F64_I64)

        assert fpga.reg_file.sp.read_int() == 3
        res_bits = user_pop64(fpga)
        assert res_bits == (1 << 64) - 42

        sentinel = user_pop32(fpga)
        assert sentinel == 0xCAFEBABE

    def test_stack_underflow_empty(self, fpga: FpgaModel) -> None:
        fpga.dispatcher.execute(UserOpcode.CONV_F64_I64)

        assert bool(fpga.reg_file.status.read_int() & (1 << StatusFlag.ERR.value)) is True
        assert fpga.reg_file.sp.read_int() == 0

    def test_stack_underflow_partial(self, fpga: FpgaModel) -> None:
        user_push32(fpga, 0x12345678)
        assert fpga.reg_file.sp.read_int() == 1

        fpga.dispatcher.execute(UserOpcode.CONV_F64_I64)

        assert bool(fpga.reg_file.status.read_int() & (1 << StatusFlag.ERR.value)) is True
        assert fpga.reg_file.sp.read_int() == 0
