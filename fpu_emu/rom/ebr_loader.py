"""EBR ROM buffer loader for Zx50 FPU.

Loads initial ROM buffers for EBR 0 (DATA_RAM) and EBR 4 (CODE_ROM) from the
compiled 8KB flash ROM binary image (fpu_flash.bin).
"""

from pathlib import Path
import struct
from typing import List, Optional


def get_default_rom_path() -> Path:
    return Path(__file__).parent / "fpu_flash.bin"


def load_ebr_rom_buffers(rom_path: Optional[Path] = None) -> List[Optional[List[int]]]:
    """Generates the EBR initialization buffers for Memory.

    The 8KB flash ROM image is split into:
      - EBR 0: CODE_ROM (1536 words x 32-bit, first 6144 bytes)
      - EBR 1..5: NullEbr (unallocated)
      - EBR 6: DATA_RAM (512 words x 32-bit, last 2048 bytes)
      - EBR 7: NullEbr (unallocated)
    """
    code_rom = [0] * 1536
    data_ram = [0] * 512

    path = rom_path if (rom_path is not None and rom_path.exists()) else get_default_rom_path()
    if path.exists():
        with open(path, "rb") as f:
            data = f.read()

        if len(data) >= 8192:
            code_rom = list(struct.unpack("<1536I", data[:6144]))
            data_ram = list(struct.unpack("<512I", data[6144:8192]))

    return [code_rom, None, None, None, None, None, data_ram, None]
