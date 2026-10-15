"""Integration tests for CONV_I64_F64 (0xCE) user opcode."""

import math
import pytest

from fpu_emu.dispatcher import UserOpcode
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.tests.test_helpers import (
    bits_to_f64,
    f64_to_bits,
    user_pop32,
    user_pop64,
    user_push32,
    user_push64,
)


def run_conv_i64_f64(fpga: FpgaModel, val_i64: int) -> tuple[int, int]:
    """Executes CONV_I64_F64 on the FPGA model with the given signed 64-bit int."""
    u64_bits = val_i64 if val_i64 >= 0 else (1 << 64) + val_i64
    user_push64(fpga, u64_bits)
    fpga.dispatcher.execute(UserOpcode.CONV_I64_F64)
    result_bits = user_pop64(fpga)
    status = fpga.reg_file.status.read_int()
    return result_bits, status


class TestConvI64F64Normals:
    """Tests normal signed integer conversion across positive and negative values."""

    @pytest.mark.parametrize(
        "val",
        [
            1,
            -1,
            2,
            -2,
            3,
            -3,
            4,
            -4,
            5,
            -5,
            10,
            -10,
            42,
            -42,
            100,
            -100,
            1000,
            -1000,
            65535,
            -65535,
            65536,
            -65536,
            1000000,
            -1000000,
            0x7FFFFFFF,  # 2^31 - 1
            -0x7FFFFFFF,
            -0x80000000,  # -2^31
            0x1FFFFFFFFFFFFF,  # 2^53 - 1 (exact in double)
            -0x1FFFFFFFFFFFFF,
            0x20000000000000,  # 2^53 (exact in double)
            -0x20000000000000,
            0x7FFFFFFFFFFFFFFF,  # 2^63 - 1
            -0x7FFFFFFFFFFFFFFF,
            -0x8000000000000000,  # -2^63
            0x123456789ABCDEF0,
            -0x123456789ABCDEF0,
        ],
    )
    def test_i64_values(self, fpga: FpgaModel, val: int) -> None:
        res_bits, status = run_conv_i64_f64(fpga, val)
        res_float = bits_to_f64(res_bits)
        expected_float = float(val)

        if abs(val) <= (1 << 53) or val == -0x8000000000000000:
            # Must be bit-exact for values representable exactly in IEEE double
            assert res_bits == f64_to_bits(expected_float)
            assert res_float == expected_float
        else:
            # Must match within double precision floating point tolerance
            assert math.isclose(res_float, expected_float, rel_tol=1e-15)

        # Flag assertions
        assert bool(status & (1 << StatusFlag.ZERO.value)) is False
        assert bool(status & (1 << StatusFlag.SIGN.value)) is (val < 0)
        assert bool(status & (1 << StatusFlag.OVERFLOW.value)) is False
        assert bool(status & (1 << StatusFlag.UNDERFLOW.value)) is False
        assert bool(status & (1 << StatusFlag.ERR.value)) is False

    @pytest.mark.parametrize("p", list(range(63)))
    def test_powers_of_two_positive(self, fpga: FpgaModel, p: int) -> None:
        """All positive powers of 2 from 2^0 to 2^62 are exactly representable."""
        val = 1 << p
        res_bits, status = run_conv_i64_f64(fpga, val)
        expected_float = float(val)

        assert res_bits == f64_to_bits(expected_float)
        assert bits_to_f64(res_bits) == expected_float
        assert bool(status & (1 << StatusFlag.SIGN.value)) is False
        assert bool(status & (1 << StatusFlag.ZERO.value)) is False

    @pytest.mark.parametrize("p", list(range(63)))
    def test_powers_of_two_negative(self, fpga: FpgaModel, p: int) -> None:
        """All negative powers of 2 from -2^0 to -2^62 are exactly representable."""
        val = -(1 << p)
        res_bits, status = run_conv_i64_f64(fpga, val)
        expected_float = float(val)

        assert res_bits == f64_to_bits(expected_float)
        assert bits_to_f64(res_bits) == expected_float
        assert bool(status & (1 << StatusFlag.SIGN.value)) is True
        assert bool(status & (1 << StatusFlag.ZERO.value)) is False

    def test_min_i64(self, fpga: FpgaModel) -> None:
        """Tests the most negative 64-bit integer (-2^63)."""
        val = -0x8000000000000000
        res_bits, status = run_conv_i64_f64(fpga, val)
        expected_float = float(val)

        assert res_bits == f64_to_bits(expected_float)
        assert bits_to_f64(res_bits) == expected_float
        assert bool(status & (1 << StatusFlag.SIGN.value)) is True
        assert bool(status & (1 << StatusFlag.ZERO.value)) is False


class TestConvI64F64Zeros:
    """Tests zero conversion to +0.0 with ZERO=1 and SIGN=0."""

    def test_zero(self, fpga: FpgaModel) -> None:
        res_bits, status = run_conv_i64_f64(fpga, 0)

        assert res_bits == 0x0000000000000000
        assert bits_to_f64(res_bits) == 0.0
        assert bool(status & (1 << StatusFlag.ZERO.value)) is True
        assert bool(status & (1 << StatusFlag.SIGN.value)) is False
        assert bool(status & (1 << StatusFlag.OVERFLOW.value)) is False
        assert bool(status & (1 << StatusFlag.UNDERFLOW.value)) is False
        assert bool(status & (1 << StatusFlag.ERR.value)) is False


class TestConvI64F64Stack:
    """Tests stack depth invariants and underflow handling."""

    def test_net_stack_depth(self, fpga: FpgaModel) -> None:
        # Push sentinel word, then 64-bit int
        user_push32(fpga, 0xCAFEBABE)
        user_push64(fpga, 0xFFFFFFFFFFFFFFFE)  # -2

        # Initial stack depth = 3 words (1 sentinel + 2 for int64)
        assert fpga.reg_file.sp.read_int() == 3

        fpga.dispatcher.execute(UserOpcode.CONV_I64_F64)

        # In-place conversion: net depth remains 3 words (1 sentinel + 2 for float64)
        assert fpga.reg_file.sp.read_int() == 3

        # Verify float64 result on top
        res_bits = user_pop64(fpga)
        assert bits_to_f64(res_bits) == -2.0

        # Verify sentinel word below is intact
        sentinel = user_pop32(fpga)
        assert sentinel == 0xCAFEBABE

    def test_stack_underflow_empty(self, fpga: FpgaModel) -> None:
        fpga.dispatcher.execute(UserOpcode.CONV_I64_F64)

        assert bool(fpga.reg_file.status.read_int() & (1 << StatusFlag.ERR.value)) is True
        assert fpga.reg_file.sp.read_int() == 0

    def test_stack_underflow_partial(self, fpga: FpgaModel) -> None:
        # Only push 1 word (4 bytes) when 2 words (8 bytes) are required
        user_push32(fpga, 0x12345678)
        assert fpga.reg_file.sp.read_int() == 1

        fpga.dispatcher.execute(UserOpcode.CONV_I64_F64)

        assert bool(fpga.reg_file.status.read_int() & (1 << StatusFlag.ERR.value)) is True
        assert fpga.reg_file.sp.read_int() == 0
