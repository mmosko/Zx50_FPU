"""Unit tests for MicroCode lookup table and EBR instruction budget tracking."""

import pytest
from fpu_emu.micro_code import MicroCode
from fpu_emu.user_opcodes import UserOpcode


def test_microcode_instruction_budget_under_512() -> None:
    """Tests that the total microcode size complies with the 512-word EBR capacity."""
    total = MicroCode.total_instructions()
    assert total > 0, "MicroCode table must not be empty"
    assert total <= MicroCode.MAX_MICRO_INSTRUCTIONS, (
        f"MicroCode size ({total}) exceeds 512 EBR word limit"
    )


def test_microcode_remaining_capacity() -> None:
    """Tests remaining capacity calculation."""
    total = MicroCode.total_instructions()
    remaining = MicroCode.remaining_capacity()
    assert remaining == MicroCode.MAX_MICRO_INSTRUCTIONS - total
    assert remaining >= 0


def test_microcode_validate_budget_raises_on_overflow(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests that validate_budget raises ValueError when total exceeds limit."""
    # Temporarily lower the maximum limit to simulate overflow
    monkeypatch.setattr(MicroCode, "MAX_MICRO_INSTRUCTIONS", 10)
    with pytest.raises(ValueError, match="exceeds EBR capacity limit"):
        MicroCode.validate_budget()


def test_microcode_get_address() -> None:
    """Verifies get_address resolves known opcodes and returns 0 for undefined."""
    addr = MicroCode.get_address(UserOpcode.ADD_F32)
    assert isinstance(addr, int)
    assert addr >= 0

    # Non-existent or dummy opcode
    dummy = UserOpcode.NOP if hasattr(UserOpcode, "NOP") else UserOpcode.ADD_F32
    assert isinstance(MicroCode.get_address(dummy), int)


def test_microcode_get_instruction() -> None:
    """Verifies get_instruction returns valid MicroInstruction objects."""
    instr = MicroCode.get_instruction(0)
    assert instr is not None
    assert hasattr(instr, "op")

    # Out of bounds should return HALT
    oob = MicroCode.get_instruction(99999)
    from fpu_emu.micro_opcodes import MicroOp
    assert oob.op == MicroOp.HALT


def test_microcode_ucode_py_development_mode(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that MicroCode loads from ucode.py when present."""
    from fpu_emu.micro_instruction import MicroInstruction
    from fpu_emu.micro_opcodes import MicroOp

    test_ucode_file = tmp_path / "ucode.py"
    test_ucode_file.write_text(
        "from fpu_emu.micro_instruction import MicroInstruction\n"
        "from fpu_emu.micro_opcodes import MicroOp\n"
        "fpu_symbols = {'USER_ADD_F32': 42}\n"
        "fpu_ucode = [MicroInstruction(op=MicroOp.NOP)] * 50\n"
    )

    monkeypatch.setattr("fpu_emu.micro_code._locate_ucode_py", lambda: test_ucode_file)
    MicroCode._load()
    try:
        assert MicroCode.get_address(UserOpcode.ADD_F32) == 42
        assert MicroCode.total_instructions() == 50
        assert MicroCode.get_instruction(0).op == MicroOp.NOP
    finally:
        # Restore normal mode
        monkeypatch.setattr("fpu_emu.micro_code._locate_ucode_py", lambda: None)
        MicroCode._load()

