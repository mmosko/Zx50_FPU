"""Microcode ROM mapping UserOpcode to micro-instruction sequences."""

import importlib.util
from pathlib import Path
import struct
from typing import Dict, List, Optional

from fpu_emu.fpga_resource import fpga_resource
from fpu_emu.micro_instruction import MicroInstruction
from fpu_emu.micro_opcodes import MicroOp
from fpu_emu.user_opcodes import UserOpcode


def _locate_ucode_py() -> Optional[Path]:
    """Check for development / debugging ucode.py."""
    candidates = [
        Path(__file__).parent / "ucode.py",
        Path.cwd() / "ucode.py",
        Path("/tmp/ucode.py"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _locate_flash_bin() -> Path:
    """Find the default unified flash binary."""
    candidates = [
        Path(__file__).parent / "rom" / "fpu_flash.bin",
        Path(__file__).parent.parent / "bin" / "fpu_flash.bin",
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError("Could not find fpu_flash.bin in rom/ or bin/")


class MicroCode:
    """Microcode ROM lookup table and instruction store."""

    # 1536 words (EBR 0-5) for runtime microcode execution store (6 KB Code ROM)
    HARD_MAX_MICRO_INSTRUCTIONS: int = 1536
    SOFT_MAX_MICRO_INSTRUCTIONS: int = 1536
    MAX_MICRO_INSTRUCTIONS: int = HARD_MAX_MICRO_INSTRUCTIONS

    _using_ucode_py: bool = False
    _symbols: Dict[str, int] = {}
    _instructions: List[MicroInstruction] = []
    _override: Optional[List[MicroInstruction]] = None
    _total_instructions_count: int = 0

    @classmethod
    def _load(cls) -> None:
        """Initializes microcode from either ucode.py (if found) or fpu_flash.bin."""
        ucode_path = _locate_ucode_py()
        if ucode_path is not None:
            spec = importlib.util.spec_from_file_location("_ucode_dev", ucode_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            cls._symbols = getattr(mod, "fpu_symbols", {})
            cls._instructions = list(getattr(mod, "fpu_ucode", []))
            cls._total_instructions_count = len(cls._instructions)
            cls._using_ucode_py = True
        else:
            flash_path = _locate_flash_bin()
            with open(flash_path, "rb") as f:
                data = f.read(cls.MAX_MICRO_INSTRUCTIONS * 4)

            num_words = len(data) // 4
            words = struct.unpack(f"<{num_words}I", data[: num_words * 4])
            cls._instructions = [MicroInstruction.from_int(w) for w in words]
            if len(cls._instructions) < cls.MAX_MICRO_INSTRUCTIONS:
                cls._instructions.extend(
                    [MicroInstruction(op=MicroOp.NOP)]
                    * (cls.MAX_MICRO_INSTRUCTIONS - len(cls._instructions))
                )

            # Find last non-NOP / non-zero word for total instructions count
            nop_word = 0x79FFE000
            last_active = 0
            for i in range(len(words) - 1, -1, -1):
                if words[i] != nop_word and words[i] != 0:
                    last_active = i + 1
                    break
            cls._total_instructions_count = last_active if last_active > 0 else len(words)
            cls._using_ucode_py = False

    @classmethod
    def set_override(cls, instructions: Optional[List[MicroInstruction]]) -> None:
        """Sets a temporary override instruction list (e.g. for testing)."""
        cls._override = instructions

    @classmethod
    def get_address(cls, opcode: UserOpcode) -> int:
        """Returns the start UPC address for an opcode in the microcode ROM."""
        if cls._using_ucode_py:
            sym = f"USER_{opcode.name}"
            if sym in cls._symbols:
                return cls._symbols[sym]
        from fpu_emu.rom.fpu_rom_map import USER_OPCODE_MAP

        return USER_OPCODE_MAP.get(opcode, 0)

    @classmethod
    def has_instruction(cls, address: int) -> bool:
        """Returns True if the address is within the active microcode bounds."""
        if cls._override is not None:
            return 0 <= address < len(cls._override)
        return 0 <= address < cls._total_instructions_count

    @classmethod
    @fpga_resource(
        approach="Cascaded Single-Port SysMEM EBR (EBR 0-5, 1536x32) for runtime microcode execution store",
        luts=0,
        ffs=0,
        ebr=6,
        delay_ns=3.2,
        cycles=1,
        shared_unit="ebr_microcode_rom",
    )
    def get_instruction(cls, address: int) -> MicroInstruction:
        """Returns the micro-instruction at the given microcode ROM address."""
        if cls._override is not None:
            if 0 <= address < len(cls._override):
                return cls._override[address]
            return MicroInstruction(op=MicroOp.HALT)

        if 0 <= address < len(cls._instructions):
            return cls._instructions[address]
        return MicroInstruction(op=MicroOp.HALT)

    # @classmethod
    # def get(cls, opcode: UserOpcode) -> List[MicroInstruction]:
    #     """Returns the instruction sequence (retained for backward compatibility)."""
    #     if cls._override is not None:
    #         return cls._override
    #     return cls._instructions

    @classmethod
    def total_instructions(cls) -> int:
        """Returns the total number of micro-instructions across all defined opcodes."""
        return cls._total_instructions_count

    @classmethod
    def remaining_capacity(cls) -> int:
        """Returns the remaining micro-instruction slots available in the 1536-word EBR store."""
        return cls.MAX_MICRO_INSTRUCTIONS - cls.total_instructions()

    @classmethod
    def validate_budget(cls) -> None:
        """Validates that total micro-instructions do not exceed the EBR limit."""
        total = cls.total_instructions()
        if total > cls.MAX_MICRO_INSTRUCTIONS:
            raise ValueError(
                f"Total microcode instructions ({total}) exceeds EBR capacity limit of {cls.MAX_MICRO_INSTRUCTIONS}"
            )


# Initialize microcode at module import time
MicroCode._load()
MicroCode.validate_budget()
