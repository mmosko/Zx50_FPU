"""Unit tests for MicroCodeSource implementations and EBR instruction budget tracking."""

import pytest

from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.memory import Memory
from fpu_emu.micro_code import EbrMicroCode, ListMicroCode, MicroCode
from fpu_emu.micro_instruction import MicroInstruction
from fpu_emu.micro_opcodes import MicroOp
from fpu_emu.rom.ebr_loader import load_ebr_rom_buffers
from fpu_emu.user_opcodes import UserOpcode


def test_microcode_instruction_budget_under_1536() -> None:
    """Tests that the total microcode size complies with the 1536-word EBR capacity."""
    total = MicroCode.total_instructions()
    assert total > 0, "MicroCode table must not be empty"
    assert total <= MicroCode.MAX_MICRO_INSTRUCTIONS, f"MicroCode size ({total}) exceeds 1536 EBR word limit"


def test_microcode_remaining_capacity() -> None:
    """Tests remaining capacity calculation."""
    total = MicroCode.total_instructions()
    remaining = MicroCode.remaining_capacity()
    assert remaining == MicroCode.MAX_MICRO_INSTRUCTIONS - total
    assert remaining >= 0


def test_microcode_validate_budget_raises_on_overflow(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests that validate_budget raises ValueError when total exceeds limit."""
    monkeypatch.setattr(MicroCode, "MAX_MICRO_INSTRUCTIONS", 10)
    with pytest.raises(ValueError, match="exceeds EBR capacity limit"):
        MicroCode.validate_budget()


def test_ebr_microcode_get_address_and_instruction() -> None:
    """Verifies EbrMicroCode resolves opcodes and fetches decoded instructions from EBR 0."""
    clock = Clock()
    memory = Memory(rom_blocks=load_ebr_rom_buffers(), clock=clock)
    ebr_ucode = EbrMicroCode(memory=memory)

    addr = ebr_ucode.get_address(UserOpcode.ADD_F32)
    assert isinstance(addr, int)
    assert addr >= 0

    instr = ebr_ucode.get_instruction(addr)
    assert isinstance(instr, MicroInstruction)

    # Out of bounds should return HALT for get_instruction
    assert ebr_ucode.get_instruction(-1).op == MicroOp.HALT
    assert ebr_ucode.get_instruction(EbrMicroCode.MAX_MICRO_INSTRUCTIONS).op == MicroOp.HALT
    oob = ebr_ucode.get_instruction(99999)
    assert oob.op == MicroOp.HALT


def test_list_microcode_isolated_sequence() -> None:
    """Verifies ListMicroCode provides an isolated in-memory instruction sequence."""
    seq = [
        MicroInstruction(op=MicroOp.NOP),
        MicroInstruction(op=MicroOp.HALT),
    ]
    custom_map = {UserOpcode.ADD_F32: 1}
    list_ucode = ListMicroCode(instructions=seq, rom_map=custom_map)

    assert list_ucode.get_address(UserOpcode.ADD_F32) == 1
    assert list_ucode.get_address(UserOpcode.SUB_F32) == 0

    assert list_ucode.get_instruction(0).op == MicroOp.NOP
    assert list_ucode.get_instruction(1).op == MicroOp.HALT
    assert list_ucode.get_instruction(2).op == MicroOp.HALT
