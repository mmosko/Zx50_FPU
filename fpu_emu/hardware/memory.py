from typing import List, Optional

from fpu_emu.fpga_resource import fpga_resource
from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.ebr import EBR, NullEbr


@fpga_resource(
    approach="SysMEM EBR Blocks (EBR 0-5 1536x32 CODE ROM, EBR 6-7 512x32 DATA RAM)",
    luts=0,
    ffs=0,
    ebr=8,
    delay_ns=3.2,
    cycles=1,
    shared_unit="ebr_sysmem_ram",
)
class Memory:
    def __init__(self, rom_blocks: List[Optional[List[int]]], clock: Clock) -> None:
        self._ebr = [
            EBR(name="0", size=1536, width=32, read_only_buffer=rom_blocks[0], clock=clock, readonly=True),
            NullEbr(clock),
            NullEbr(clock),
            NullEbr(clock),
            NullEbr(clock),
            NullEbr(clock),
            EBR(name="6", size=512, width=32, read_only_buffer=rom_blocks[6], clock=clock, readonly=False),
            NullEbr(clock),
        ]

    def read(self, block: int, addr: int) -> int:
        return self._ebr[block].read(addr)

    def write(self, block: int, addr: int, data: int) -> None:
        self._ebr[block].write(addr, data)
