"""Integration tests for CONV_F64_F32 (0xCB) user opcode."""

import math
import struct
import pytest

from fpu_asm.assembler import Assembler
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.hardware.rom import Rom
from fpu_emu.tests.test_helpers import (
    bits_to_f32,
    f64_to_bits,
    user_pop32,
    user_push32,
    user_push64,
)


@pytest.fixture(scope="module")
def conv_f64_f32_rom_and_entry():
    """Assembles CONV_F64_F32 dynamically in memory for testing."""
    asm = Assembler()
    source = """
    .include "fpu_emu/asm/pop_two_64.asm"
    .include "fpu_emu/asm/normalize_f32.asm"
    .include "fpu_emu/asm/conv_f64_f32.asm"
    """
    assembled = asm.assemble(source)
    instructions = [instr for _, instr in assembled]
    entry_addr = asm.symbols["USER_CONV_F64_F32"]
    return instructions, entry_addr


@pytest.fixture
def fpga(tmp_path):
    """Provides a clean FpgaModel instance for each test."""
    rom = Rom(size=1024, rom_path=tmp_path / "dummy.rom")
    return FpgaModel(rom=rom)


def run_conv_f64_f32(fpga, instructions, entry_addr, val_f64: float | int):
    """Helper to push a float64, run CONV_F64_F32, and pop the float32 result."""
    if isinstance(val_f64, int):
        bits64 = val_f64
    else:
        bits64 = f64_to_bits(val_f64)
    user_push64(fpga, bits64)
    fpga.reg_file.upc.write(entry_addr)
    fpga.dispatcher._run(instructions)
    res_bits = user_pop32(fpga)
    status = fpga.reg_file.status.read_int()
    return res_bits, status


class TestConvF64F32Normals:
    """Tests normal numbers converting from double to single precision."""

    @pytest.mark.parametrize(
        "val",
        [
            1.0,
            -1.0,
            2.0,
            -2.0,
            0.5,
            -0.5,
            0.25,
            0.125,
            2.5,
            -2.5,
            42.0,
            -42.0,
            100.0,
            -100.0,
            1000.0,
            math.pi,
            math.e,
            1.5e10,
            -1.5e10,
            3.0e30,
            -3.0e30,
            1.0e-10,
            -1.0e-10,
            1.0e-30,
            -1.0e-30,
        ],
    )
    def test_normal_values(self, fpga, conv_f64_f32_rom_and_entry, val):
        instructions, entry = conv_f64_f32_rom_and_entry
        res_bits, status = run_conv_f64_f32(fpga, instructions, entry, val)
        res_f32 = bits_to_f32(res_bits)

        # Expected float32 representation
        expected_f32 = struct.unpack(">f", struct.pack(">f", val))[0]
        expected_bits = struct.unpack(">I", struct.pack(">f", expected_f32))[0]

        # Verify bit-exact or within 1 ULP due to truncation
        assert abs(res_bits - expected_bits) <= 1
        assert math.isclose(res_f32, expected_f32, rel_tol=1e-6)

        # Check flags
        sign_bit = (res_bits >> 31) & 1
        expected_sign = bool(status & (1 << StatusFlag.SIGN.value))
        assert expected_sign == (sign_bit == 1)
        assert bool(status & (1 << StatusFlag.ZERO.value)) is False
        assert bool(status & (1 << StatusFlag.OVERFLOW.value)) is False
        assert bool(status & (1 << StatusFlag.UNDERFLOW.value)) is False


class TestConvF64F32Zeros:
    """Tests signed zero representations."""

    def test_positive_zero(self, fpga, conv_f64_f32_rom_and_entry):
        instructions, entry = conv_f64_f32_rom_and_entry
        res_bits, status = run_conv_f64_f32(fpga, instructions, entry, 0.0)
        assert res_bits == 0x00000000
        assert bool(status & (1 << StatusFlag.ZERO.value)) is True
        assert bool(status & (1 << StatusFlag.SIGN.value)) is False
        assert bool(status & (1 << StatusFlag.UNDERFLOW.value)) is False
        assert bool(status & (1 << StatusFlag.OVERFLOW.value)) is False

    def test_negative_zero(self, fpga, conv_f64_f32_rom_and_entry):
        instructions, entry = conv_f64_f32_rom_and_entry
        res_bits, status = run_conv_f64_f32(fpga, instructions, entry, -0.0)
        assert res_bits == 0x80000000
        assert bool(status & (1 << StatusFlag.ZERO.value)) is True
        assert bool(status & (1 << StatusFlag.SIGN.value)) is True
        assert bool(status & (1 << StatusFlag.UNDERFLOW.value)) is False
        assert bool(status & (1 << StatusFlag.OVERFLOW.value)) is False


class TestConvF64F32Overflow:
    """Tests exponent overflow to +/-Infinity with V=1."""

    @pytest.mark.parametrize(
        ("val", "expected_bits", "expected_sign"),
        [
            (1.0e39, 0x7F800000, False),
            (-1.0e39, 0xFF800000, True),
            (1.0e100, 0x7F800000, False),
            (-1.0e100, 0xFF800000, True),
            (1.0e308, 0x7F800000, False),
            (-1.0e308, 0xFF800000, True),
            (1.7976931348623157e308, 0x7F800000, False),
            (-1.7976931348623157e308, 0xFF800000, True),
        ],
    )
    def test_overflow_to_infinity(self, fpga, conv_f64_f32_rom_and_entry, val, expected_bits, expected_sign):
        instructions, entry = conv_f64_f32_rom_and_entry
        res_bits, status = run_conv_f64_f32(fpga, instructions, entry, val)
        assert res_bits == expected_bits
        assert bool(status & (1 << StatusFlag.OVERFLOW.value)) is True
        assert bool(status & (1 << StatusFlag.SIGN.value)) is expected_sign


class TestConvF64F32Underflow:
    """Tests exponent underflow to signed zero with U=1."""

    @pytest.mark.parametrize(
        ("val", "expected_bits", "expected_sign"),
        [
            (1.0e-39, 0x00000000, False),
            (-1.0e-39, 0x80000000, True),
            (1.0e-50, 0x00000000, False),
            (-1.0e-50, 0x80000000, True),
            (1.0e-100, 0x00000000, False),
            (-1.0e-100, 0x80000000, True),
            (1.0e-300, 0x00000000, False),
            (-1.0e-300, 0x80000000, True),
        ],
    )
    def test_underflow_to_zero(self, fpga, conv_f64_f32_rom_and_entry, val, expected_bits, expected_sign):
        instructions, entry = conv_f64_f32_rom_and_entry
        res_bits, status = run_conv_f64_f32(fpga, instructions, entry, val)
        assert res_bits == expected_bits
        assert bool(status & (1 << StatusFlag.UNDERFLOW.value)) is True
        assert bool(status & (1 << StatusFlag.ZERO.value)) is True
        assert bool(status & (1 << StatusFlag.SIGN.value)) is expected_sign


class TestConvF64F32Specials:
    """Tests Infinities and NaNs."""

    def test_positive_infinity(self, fpga, conv_f64_f32_rom_and_entry):
        instructions, entry = conv_f64_f32_rom_and_entry
        res_bits, status = run_conv_f64_f32(fpga, instructions, entry, float("inf"))
        assert res_bits == 0x7F800000
        assert bool(status & (1 << StatusFlag.SIGN.value)) is False

    def test_negative_infinity(self, fpga, conv_f64_f32_rom_and_entry):
        instructions, entry = conv_f64_f32_rom_and_entry
        res_bits, status = run_conv_f64_f32(fpga, instructions, entry, float("-inf"))
        assert res_bits == 0xFF800000
        assert bool(status & (1 << StatusFlag.SIGN.value)) is True

    def test_quiet_nan(self, fpga, conv_f64_f32_rom_and_entry):
        instructions, entry = conv_f64_f32_rom_and_entry
        # Standard positive quiet NaN: 0x7FF8000000000000
        res_bits, status = run_conv_f64_f32(fpga, instructions, entry, 0x7FF8000000000000)
        assert (res_bits & 0x7F800000) == 0x7F800000
        assert (res_bits & 0x007FFFFF) != 0
        assert (res_bits & 0x00400000) != 0  # Quiet bit preserved
        assert (res_bits >> 31) == 0

    def test_negative_quiet_nan(self, fpga, conv_f64_f32_rom_and_entry):
        instructions, entry = conv_f64_f32_rom_and_entry
        # Negative quiet NaN: 0xFFF8000000000000
        res_bits, status = run_conv_f64_f32(fpga, instructions, entry, 0xFFF8000000000000)
        assert (res_bits & 0x7F800000) == 0x7F800000
        assert (res_bits & 0x007FFFFF) != 0
        assert (res_bits >> 31) == 1

    def test_signaling_nan(self, fpga, conv_f64_f32_rom_and_entry):
        instructions, entry = conv_f64_f32_rom_and_entry
        # Signaling NaN: 0x7FF0000000000001
        res_bits, status = run_conv_f64_f32(fpga, instructions, entry, 0x7FF0000000000001)
        assert (res_bits & 0x7F800000) == 0x7F800000
        assert (res_bits & 0x007FFFFF) != 0

    def test_nan_with_upper_payload(self, fpga, conv_f64_f32_rom_and_entry):
        instructions, entry = conv_f64_f32_rom_and_entry
        # NaN with payload in high mantissa: 0x7FF4560000000000
        res_bits, status = run_conv_f64_f32(fpga, instructions, entry, 0x7FF4560000000000)
        assert (res_bits & 0x7F800000) == 0x7F800000
        assert (res_bits & 0x007FFFFF) != 0


class TestConvF64F32Stack:
    """Tests stack underflow and net stack depth change."""

    def test_net_stack_depth(self, fpga, conv_f64_f32_rom_and_entry):
        instructions, entry = conv_f64_f32_rom_and_entry
        # Push a sentinel word, then a 64-bit float
        user_push32(fpga, 0xCAFEBABE)
        user_push64(fpga, f64_to_bits(123.456))

        # Initial stack depth = 3 words (1 sentinel + 2 for float64)
        assert fpga.reg_file.sp.read_int() == 3

        fpga.reg_file.upc.write(entry)
        fpga.dispatcher._run(instructions)

        # Net depth must be 2 words (1 sentinel + 1 for float32)
        assert fpga.reg_file.sp.read_int() == 2

        # Verify float32 result on top
        res_bits = user_pop32(fpga)
        assert math.isclose(bits_to_f32(res_bits), 123.456, rel_tol=1e-5)

        # Verify sentinel word below it is intact
        sentinel = user_pop32(fpga)
        assert sentinel == 0xCAFEBABE

    def test_stack_underflow_empty(self, fpga, conv_f64_f32_rom_and_entry):
        instructions, entry = conv_f64_f32_rom_and_entry
        fpga.reg_file.upc.write(entry)
        fpga.dispatcher._run(instructions)

        assert bool(fpga.reg_file.status.read_int() & (1 << StatusFlag.ERR.value)) is True
        assert fpga.reg_file.sp.read_int() == 0

    def test_stack_underflow_partial(self, fpga, conv_f64_f32_rom_and_entry):
        instructions, entry = conv_f64_f32_rom_and_entry
        # Only push 1 word (4 bytes) when 2 words (8 bytes) are required
        user_push32(fpga, 0x12345678)
        assert fpga.reg_file.sp.read_int() == 1

        fpga.reg_file.upc.write(entry)
        fpga.dispatcher._run(instructions)

        assert bool(fpga.reg_file.status.read_int() & (1 << StatusFlag.ERR.value)) is True
        assert fpga.reg_file.sp.read_int() == 0
