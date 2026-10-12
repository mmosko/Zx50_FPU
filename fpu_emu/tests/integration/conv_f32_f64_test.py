"""Integration tests for CONV_F32_F64 (0xC9) microcode operation."""

from pathlib import Path
import struct
import pytest
from fpu_asm.assembler import Assembler
from fpu_emu.fpga_model import FpgaModel
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.hardware.rom import Rom
from fpu_emu.tests.test_helpers import (
    bits_to_f64,
    f32_to_bits,
    user_pop64,
    user_push32,
)


@pytest.fixture(scope="module")
def conv_f32_f64_ucode():
    """Assembles the CONV_F32_F64 routine with its dependencies in-memory."""
    asm = Assembler()
    source = """
.include "fpu_emu/asm/pop_two_32.asm"
.include "fpu_emu/asm/normalize_f64.asm"
.include "fpu_emu/asm/conv_f32_f64.asm"
"""
    assembled = asm.assemble(source)
    instructions = [instr for _, instr in assembled]
    entry_addr = asm.symbols["USER_CONV_F32_F64"]
    return instructions, entry_addr


def run_conv_f32_f64(tmp_path: Path, ucode_bundle, input_bits: int):
    """Executes CONV_F32_F64 on FpgaModel with input_bits on the stack."""
    instructions, entry_addr = ucode_bundle
    rom = Rom(size=1024, rom_path=tmp_path / "dummy.rom")
    fpga = FpgaModel(rom=rom)

    user_push32(fpga, input_bits)
    fpga.reg_file.upc.write(entry_addr)
    fpga.dispatcher._run(instructions)

    result_bits = user_pop64(fpga)
    status_reg = fpga.reg_file.status.read_int()
    return result_bits, status_reg, fpga


@pytest.mark.parametrize(
    "val",
    [
        0.0,
        1.0,
        -1.0,
        2.0,
        -2.0,
        0.5,
        -0.5,
        0.25,
        -0.25,
        0.75,
        1.5,
        2.5,
        -2.5,
        10.0,
        100.0,
        -100.0,
        3.1415927,
        1.5e10,
        1e20,
        1e38,
        1e-10,
        1e-20,
        1e-37,
    ],
)
def test_conv_f32_f64_normal_numbers(tmp_path: Path, conv_f32_f64_ucode, val: float):
    input_bits = f32_to_bits(val)
    result_bits, _, _ = run_conv_f32_f64(tmp_path, conv_f32_f64_ucode, input_bits)
    actual_f64 = bits_to_f64(result_bits)
    expected_f64 = struct.unpack(">d", struct.pack(">d", struct.unpack(">f", struct.pack(">f", val))[0]))[0]
    assert actual_f64 == expected_f64


def test_conv_f32_f64_signed_zeros(tmp_path: Path, conv_f32_f64_ucode):
    # Positive zero
    pos_res, pos_status, _ = run_conv_f32_f64(tmp_path, conv_f32_f64_ucode, 0x00000000)
    assert pos_res == 0x0000000000000000
    assert (pos_status & (1 << StatusFlag.ZERO.value)) != 0
    assert (pos_status & (1 << StatusFlag.SIGN.value)) == 0

    # Negative zero
    neg_res, neg_status, _ = run_conv_f32_f64(tmp_path, conv_f32_f64_ucode, 0x80000000)
    assert neg_res == 0x8000000000000000
    assert (neg_status & (1 << StatusFlag.ZERO.value)) != 0
    assert (neg_status & (1 << StatusFlag.SIGN.value)) != 0


def test_conv_f32_f64_infinities(tmp_path: Path, conv_f32_f64_ucode):
    # +Infinity
    pos_inf, _, _ = run_conv_f32_f64(tmp_path, conv_f32_f64_ucode, 0x7F800000)
    assert pos_inf == 0x7FF0000000000000

    # -Infinity
    neg_inf, _, _ = run_conv_f32_f64(tmp_path, conv_f32_f64_ucode, 0xFF800000)
    assert neg_inf == 0xFFF0000000000000


@pytest.mark.parametrize(
    "subnormal_u32",
    [
        0x00000001,  # Smallest positive subnormal
        0x80000001,  # Smallest negative subnormal
        0x00000002,
        0x00000010,
        0x00010000,
        0x00400000,
        0x007FFFFF,  # Largest positive subnormal
        0x807FFFFF,  # Largest negative subnormal
    ],
)
def test_conv_f32_f64_subnormals(tmp_path: Path, conv_f32_f64_ucode, subnormal_u32: int):
    result_bits, _, _ = run_conv_f32_f64(tmp_path, conv_f32_f64_ucode, subnormal_u32)
    actual_f64 = bits_to_f64(result_bits)
    expected_f64 = struct.unpack(">d", struct.pack(">d", struct.unpack(">f", struct.pack(">I", subnormal_u32))[0]))[0]
    assert actual_f64 == expected_f64


@pytest.mark.parametrize(
    "nan_u32, expected_u64",
    [
        (0x7FC00000, 0x7FF8000000000000),  # Quiet NaN
        (0xFFC00000, 0xFFF8000000000000),  # Negative Quiet NaN
        (0x7F800001, 0x7FF0000020000000),  # Signaling NaN
        (0xFF800001, 0xFFF0000020000000),  # Negative Signaling NaN
        (0x7FC00001, 0x7FF8000020000000),  # QNaN with payload
        (0x7FA55A55, 0x7FF4AB4AA0000000),  # SNaN with pattern
    ],
)
def test_conv_f32_f64_nans(tmp_path: Path, conv_f32_f64_ucode, nan_u32: int, expected_u64: int):
    result_bits, _, _ = run_conv_f32_f64(tmp_path, conv_f32_f64_ucode, nan_u32)
    assert result_bits == expected_u64


def test_conv_f32_f64_stack_underflow(tmp_path: Path, conv_f32_f64_ucode):
    """Verifies that an empty stack triggers ERR and halts without pushing."""
    instructions, entry_addr = conv_f32_f64_ucode
    rom = Rom(size=1024, rom_path=tmp_path / "dummy.rom")
    fpga = FpgaModel(rom=rom)

    # Empty stack
    fpga.reg_file.upc.write(entry_addr)
    fpga.dispatcher._run(instructions)

    # Error flag must be set
    assert fpga.reg_file.status.is_bit_set(StatusFlag.ERR)
    # Stack pointer must not have grown
    assert fpga.reg_file.sp.read_int() == 0
