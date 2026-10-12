"""Integration tests for CONV_U64_F64 (0xC5) user opcode."""

import math
import pytest

from fpu_asm.assembler import Assembler
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.hardware.rom import Rom
from fpu_emu.tests.test_helpers import (
    bits_to_f64,
    f64_to_bits,
    user_pop32,
    user_pop64,
    user_push32,
    user_push64,
)


@pytest.fixture(scope="module")
def conv_u64_f64_rom_and_entry(tmp_path_factory):
    """Assembles CONV_U64_F64 with required subroutines into an in-memory instruction list."""
    tmp_path = tmp_path_factory.mktemp("rom_u64")
    asm = Assembler()
    source = """
    .include "fpu_emu/asm/pop_two_64.asm"
    .include "fpu_emu/asm/normalize_f64.asm"
    .include "fpu_emu/asm/conv_int_f64.asm"
    """
    assembled = asm.assemble(source)
    instructions = [instr for _, instr in assembled]
    entry_addr = asm.symbols["USER_CONV_U64_F64"]
    return instructions, entry_addr, tmp_path


@pytest.fixture
def fpga(conv_u64_f64_rom_and_entry):
    _, _, tmp_path = conv_u64_f64_rom_and_entry
    rom = Rom(size=1024, rom_path=tmp_path / "dummy.rom")
    return FpgaModel(rom=rom)


def run_conv_u64_f64(fpga, instructions, entry, val_u64):
    """Executes CONV_U64_F64 on the FPGA model with the given 64-bit uint."""
    user_push64(fpga, val_u64)
    fpga.reg_file.upc.write(entry)
    fpga.dispatcher._run(instructions)
    result_bits = user_pop64(fpga)
    status = fpga.reg_file.status.read_int()
    return result_bits, status


class TestConvU64F64Normals:
    """Tests normal integer conversion across varied values and ranges."""

    @pytest.mark.parametrize(
        "val",
        [
            1,
            2,
            3,
            4,
            5,
            10,
            42,
            100,
            1000,
            65535,
            65536,
            1000000,
            0xFFFFFFFF,  # 2^32 - 1
            0x100000000,  # 2^32
            0x1FFFFFFFFFFFFF,  # 2^53 - 1 (exact in double)
            0x20000000000000,  # 2^53 (exact in double)
            0x7FFFFFFFFFFFFFFF,  # 2^63 - 1
            0x8000000000000000,  # 2^63
            0x8000000000000001,
            0xFFFFFFFFFFFFFFFE,
            0xFFFFFFFFFFFFFFFF,  # 2^64 - 1
            0xDEADBEEFCAFEBABE,
            0x123456789ABCDEF0,
        ],
    )
    def test_u64_values(self, fpga, conv_u64_f64_rom_and_entry, val):
        instructions, entry, _ = conv_u64_f64_rom_and_entry
        res_bits, status = run_conv_u64_f64(fpga, instructions, entry, val)
        res_float = bits_to_f64(res_bits)
        expected_float = float(val)

        if val <= (1 << 53):
            # Must be bit-exact for values representable exactly in IEEE double
            assert res_bits == f64_to_bits(expected_float)
            assert res_float == expected_float
        else:
            # Must match within double precision floating point tolerance
            assert math.isclose(res_float, expected_float, rel_tol=1e-15)

        # Flag assertions
        assert bool(status & (1 << StatusFlag.ZERO.value)) is False
        assert bool(status & (1 << StatusFlag.SIGN.value)) is False  # Unsigned is always positive
        assert bool(status & (1 << StatusFlag.OVERFLOW.value)) is False
        assert bool(status & (1 << StatusFlag.UNDERFLOW.value)) is False
        assert bool(status & (1 << StatusFlag.ERR.value)) is False

    @pytest.mark.parametrize("p", list(range(64)))
    def test_powers_of_two(self, fpga, conv_u64_f64_rom_and_entry, p):
        """All powers of 2 from 2^0 to 2^63 are exactly representable."""
        instructions, entry, _ = conv_u64_f64_rom_and_entry
        val = 1 << p
        res_bits, status = run_conv_u64_f64(fpga, instructions, entry, val)
        expected_float = float(val)

        assert res_bits == f64_to_bits(expected_float)
        assert bits_to_f64(res_bits) == expected_float
        assert bool(status & (1 << StatusFlag.SIGN.value)) is False
        assert bool(status & (1 << StatusFlag.ZERO.value)) is False


class TestConvU64F64Zeros:
    """Tests zero conversion to +0.0 with ZERO=1."""

    def test_zero(self, fpga, conv_u64_f64_rom_and_entry):
        instructions, entry, _ = conv_u64_f64_rom_and_entry
        res_bits, status = run_conv_u64_f64(fpga, instructions, entry, 0)

        assert res_bits == 0x0000000000000000
        assert bits_to_f64(res_bits) == 0.0
        assert bool(status & (1 << StatusFlag.ZERO.value)) is True
        assert bool(status & (1 << StatusFlag.SIGN.value)) is False
        assert bool(status & (1 << StatusFlag.OVERFLOW.value)) is False
        assert bool(status & (1 << StatusFlag.UNDERFLOW.value)) is False
        assert bool(status & (1 << StatusFlag.ERR.value)) is False


class TestConvU64F64Stack:
    """Tests stack depth invariants and underflow handling."""

    def test_net_stack_depth(self, fpga, conv_u64_f64_rom_and_entry):
        instructions, entry, _ = conv_u64_f64_rom_and_entry
        # Push sentinel word, then 64-bit uint
        user_push32(fpga, 0xCAFEBABE)
        user_push64(fpga, 0x123456789ABCDEF0)

        # Initial stack depth = 3 words (1 sentinel + 2 for uint64)
        assert fpga.reg_file.sp.read_int() == 3

        fpga.reg_file.upc.write(entry)
        fpga.dispatcher._run(instructions)

        # In-place conversion: net depth remains 3 words (1 sentinel + 2 for float64)
        assert fpga.reg_file.sp.read_int() == 3

        # Verify float64 result on top
        res_bits = user_pop64(fpga)
        assert math.isclose(bits_to_f64(res_bits), float(0x123456789ABCDEF0), rel_tol=1e-15)

        # Verify sentinel word below is intact
        sentinel = user_pop32(fpga)
        assert sentinel == 0xCAFEBABE

    def test_stack_underflow_empty(self, fpga, conv_u64_f64_rom_and_entry):
        instructions, entry, _ = conv_u64_f64_rom_and_entry
        fpga.reg_file.upc.write(entry)
        fpga.dispatcher._run(instructions)

        assert bool(fpga.reg_file.status.read_int() & (1 << StatusFlag.ERR.value)) is True
        assert fpga.reg_file.sp.read_int() == 0

    def test_stack_underflow_partial(self, fpga, conv_u64_f64_rom_and_entry):
        instructions, entry, _ = conv_u64_f64_rom_and_entry
        # Only push 1 word (4 bytes) when 2 words (8 bytes) are required
        user_push32(fpga, 0x12345678)
        assert fpga.reg_file.sp.read_int() == 1

        fpga.reg_file.upc.write(entry)
        fpga.dispatcher._run(instructions)

        assert bool(fpga.reg_file.status.read_int() & (1 << StatusFlag.ERR.value)) is True
        assert fpga.reg_file.sp.read_int() == 0
