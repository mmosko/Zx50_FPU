"""Microcode ROM sources and EBR instruction budget tracking."""

from abc import ABC, abstractmethod
from pathlib import Path
import struct
from typing import Mapping, Optional, Sequence

from fpu_emu.fpga_resource import fpga_resource
from fpu_emu.hardware.memory import Memory
from fpu_emu.micro_instruction import MicroInstruction
from fpu_emu.micro_opcodes import MicroOp
from fpu_emu.rom.fpu_rom_map import USER_OPCODE_MAP
from fpu_emu.user_opcodes import UserOpcode

NOP_WORD: int = 0x79FFE000
CODE_ROM_WORDS: int = 1536
WORD_BYTES: int = 4


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


class MicroCodeSource(ABC):
    """Abstract interface for a microcode instruction store and opcode entry lookup."""

    @abstractmethod
    def get_address(self, opcode: UserOpcode) -> int:
        """Returns the start UPC address for an opcode in the microcode store."""

    @abstractmethod
    def get_instruction(self, address: int) -> MicroInstruction:
        """Returns the micro-instruction at the given address."""


class EbrMicroCode(MicroCodeSource):
    """Hardware-accurate microcode store backed by EBR Block 0 (CODE_ROM)."""

    EBR_BLOCK: int = 0
    MAX_MICRO_INSTRUCTIONS: int = CODE_ROM_WORDS

    def __init__(
        self,
        memory: Memory,
        rom_map: Optional[Mapping[UserOpcode, int]] = None,
    ) -> None:
        self._memory = memory
        self._rom_map: Mapping[UserOpcode, int] = rom_map if rom_map is not None else USER_OPCODE_MAP

    def get_address(self, opcode: UserOpcode) -> int:
        """Returns the start UPC address for an opcode in the microcode ROM."""
        return self._rom_map.get(opcode, 0)

    @fpga_resource(
        approach="Cascaded Single-Port SysMEM EBR (EBR 0-5, 1536x32) for runtime microcode execution store",
        luts=0,
        ffs=0,
        ebr=6,
        delay_ns=3.2,
        cycles=1,
        shared_unit="ebr_microcode_rom",
    )
    def get_instruction(self, address: int) -> MicroInstruction:
        """Reads a 32-bit word from EBR Block 0 and decodes into a MicroInstruction."""
        if not (0 <= address < self.MAX_MICRO_INSTRUCTIONS):
            return MicroInstruction(op=MicroOp.HALT)
        word = self._memory.read(self.EBR_BLOCK, address)
        return MicroInstruction.from_int(word)


class ListMicroCode(MicroCodeSource):
    """In-memory microcode sequence for isolated unit testing."""

    def __init__(
        self,
        instructions: Sequence[MicroInstruction],
        rom_map: Optional[Mapping[UserOpcode, int]] = None,
    ) -> None:
        self._instructions = list(instructions)
        self._rom_map: Mapping[UserOpcode, int] = rom_map if rom_map is not None else {}

    def get_address(self, opcode: UserOpcode) -> int:
        """Returns the start UPC address for an opcode (defaults to 0)."""
        return self._rom_map.get(opcode, 0)

    def get_instruction(self, address: int) -> MicroInstruction:
        """Returns the micro-instruction at the given index, or HALT if out of bounds."""
        if 0 <= address < len(self._instructions):
            return self._instructions[address]
        return MicroInstruction(op=MicroOp.HALT)


class MicroCode(EbrMicroCode):
    """Microcode ROM capacity budget tracker and EbrMicroCode specialization."""

    # 1536 words (EBR 0-5) for runtime microcode execution store (6 KB Code ROM)
    HARD_MAX_MICRO_INSTRUCTIONS: int = CODE_ROM_WORDS
    MAX_MICRO_INSTRUCTIONS: int = HARD_MAX_MICRO_INSTRUCTIONS

    @classmethod
    def total_instructions(cls, flash_path: Optional[Path] = None) -> int:
        """Returns the total number of active micro-instructions in the flash ROM image."""
        path = flash_path if flash_path is not None else _locate_flash_bin()
        with open(path, "rb") as f:
            data = f.read(cls.HARD_MAX_MICRO_INSTRUCTIONS * WORD_BYTES)

        num_words = len(data) >> 2
        words = struct.unpack(f"<{num_words}I", data[: num_words << 2])

        last_active = 0
        for i in range(len(words) - 1, -1, -1):
            if words[i] != NOP_WORD and words[i] != 0:
                last_active = i + 1
                break
        return last_active if last_active > 0 else len(words)

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


# Validate microcode budget at module import time
MicroCode.validate_budget()
