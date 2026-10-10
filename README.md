# Zx50 FPU: Hardware Floating-Point & Stack Coprocessor

The **Zx50 FPU** is a high-performance, FPGA-based hardware floating-point and stack coprocessor designed for the **Zx50 distributed computing cluster** (specifically integrated on the **Zx50 CPU Card Rev C4**). 

It tightly couples to a vintage or modern host **Zilog Z80 CPU** (running at 5–10 MHz) and accelerates 32-bit and 64-bit integer, single-precision (`f32`), and double-precision (`f64`) IEEE-754 floating-point arithmetic using an internal micro-sequencer clocked at up to 80 MHz.

---

## Architecture Overview

```
                      +---------------------------------------+
                      |         Host Z80 CPU (5.0V)           |
                      |          Base I/O Ports:              |
                      |  Port 0x70: Data Stack (Push / Pop)   |
                      |  Port 0x71: Opcode & Status Register  |
                      +---------------------------------------+
                                          |
                      [ 74CBTD3861 5V <-> 3.3V Level Shifters ]
                                          |
                      +---------------------------------------+
                      | Lattice MachXO2-2000HC FPGA (3.3V)    |
                      |                                       |
                      |  +---------------------------------+  |
                      |  | 64-Word Operand Stack (EBR 0-3) |  |
                      |  +---------------------------------+  |
                      |                  |                    |
                      |  +---------------------------------+  |
                      |  | Datapath: HA_MUX & HB_MUX Buses |  |
                      |  +---------------------------------+  |
                      |     |          |             |        |
                      |   [ALU]   [Shifter]   [Booth Mul]     |
                      |   [DIV]   [Pack/Unp]  [LZC Normal]    |
                      |                  |                    |
                      |  +---------------------------------+  |
                      |  | 1024-Word Microcode (EBR 4-7)   |  |
                      |  | 16-Word Call Stack / Sequencer  |  |
                      |  +---------------------------------+  |
                      |                  |                    |
                      |  +---------------------------------+  |
                      |  | Wait-State Generator (BWAIT_N)  | ---> Q4 (2N7002) -> ~WAIT
                      |  +---------------------------------+  |
                      +---------------------------------------+
```

### Key Technical Highlights

* **Host Port Interface:** Controlled via just two Z80 I/O ports:
  * **Port `0x70` (`DATA`):** Bi-directional 8-bit portal to the 64-word hardware operand stack. Pushing 4 or 8 bytes pushes an `i32`, `u32`, `f32`, `i64`, `u64`, or `f64` operand; reading pops the result in Little-Endian byte order.
  * **Port `0x71` (`CMD` / `STATUS`):** Write an 8-bit UserOpcode to trigger an operation; read to query the 8-bit `STATUS` register (`BUSY`, `ERR`, `ZERO`, `SIGN`, `OVERFLOW`, `UNDERFLOW`, `CARRY`).
* **Zero-Overhead Hardware Wait States:** Dedicated open-drain handshake circuitry (`BWAIT_N` driving MOSFET `Q4`) automatically holds the Z80's `~WAIT` line low during calculation in **Blocking Mode**. The Z80 issues an `OUT (0x71), A` instruction and resumes execution the instant calculation finishes—requiring zero software polling loops. Non-blocking polling mode is also supported.
* **FPGA Logic Optimized for MachXO2:** Implemented entirely in soft logic and embedded block RAM (SysMEM EBR) on a Lattice MachXO2-2000HC / MachXO3:
  * **0 DSP blocks used** (synthesizes cleanly into CCU2C carry-chains and PFU slices).
  * **8 EBR 9Kb blocks total** (4 blocks for 2KB Data RAM & stack, 4 blocks for 1,024-word microcode ROM).
  * **Dedicated Datapath Blocks:** 32-bit parallel adder/subtractor, 64-bit logarithmic barrel shifter, 16-cycle Radix-4 Booth multiplier, 32-cycle non-restoring divider, single-cycle Leading Zero Counter (LZC), and float pack/unpack circuits.
* **Comprehensive Arithmetic Matrix:** Full 60-operation instruction set supporting arithmetic, square roots, transcendental functions ($\sin, \cos, \tan, e^x, 2^x, \ln, \log_2$), powers, mathematical constants ($\pi, e, \sqrt{2}$, etc.), and cross-type conversions.

---

## Documentation Index

The project documentation is organized across specialized technical specifications:

| Document | Description |
|:---|:---|
| **[ProgrammersGuide.md](ProgrammersGuide.md)** | **Z80 Host Programming Guide & Instruction Reference.** Details Port `0x70`/`0x71` conventions, status register bitfields, byte ordering, cycle timing benchmarks, and complete Z80 assembly code examples (`add_f32`, `vector_dot_product`, polling vs. blocking). |
| **[FPU_REV2.md](FPU_REV2.md)** | **High-Level Hardware Architecture & Interface Specification.** Documents CPU Card (Rev C4) hardware integration, voltage translation, pin mappings, wait-state handshake circuitry, and system interconnects. |
| **[SystemDesignV2.md](SystemDesignV2.md)** | **Low-Level Internal FPGA Micro-Architecture.** Detailed breakdown of datapath blocks, 16-input `HA_MUX` / `HB_MUX` operand routing, register files, micro-sequencer, and MachXO2 hardware resource budget. |
| **[SystemReference.md](SystemReference.md)** | **Authoritative Microcode ISA Reference Manual.** The single source of truth for all microcode assembly instructions ($\mu$-ops), mnemonics, valid operand combinations, cycle latencies, and flag side-effects. |
| **[SystemAssembler.md](SystemAssembler.md)** | **Microcode Assembler (`fpu_asm`) Specification.** Syntax rules, two-pass parsing grammar, label resolution, delay-slot handling, and UserOpcode dispatch table generation. |
| **[FPU_EMULATOR.md](FPU_EMULATOR.md)** | **Cycle-Accurate Hardware Emulator Architecture.** Design rules, bit-accurate models, and constraints for the Python-based digital twin. |
| **[TODO.md](TODO.md)** | **Development Roadmap & Verification Status.** Tracks implementation phases, completed instructions, microcode ROM headroom, and automated test suite coverage. |

---

## Repository Structure

```text
zx50_fpu/
├── README.md               # Repository introduction and documentation index
├── FPU_REV2.md             # Hardware architecture specification
├── ProgrammersGuide.md     # Z80 assembly programmer's guide
├── SystemDesignV2.md       # FPGA micro-architecture and datapath design
├── SystemReference.md      # Microcode instruction reference manual
├── SystemAssembler.md      # Microcode assembler specification
├── FPU_EMULATOR.md         # Emulator design rules and verification architecture
├── TODO.md                 # Roadmap and test verification tracking
├── fpu_asm/                # Python microcode assembler (fasm)
│   ├── assembler.py        # Two-pass assembler & label resolver
│   ├── ucode.lark          # Lark EBNF microcode grammar
│   └── emitter.py          # Python / binary ROM image code generator
├── fpu_emu/                # Cycle-accurate hardware emulator (machine model)
│   ├── asm/                # Individual microcode routines per UserOpcode (.asm)
│   ├── ucode.asm           # Top-level microcode assembly include file
│   ├── ucode.py            # Assembled runtime microcode store (1,024 words)
│   ├── blocks/             # Synthesizable hardware functional block models
│   │   ├── adder/          # Adder, Booth multiplier, Non-restoring divider
│   │   ├── shifter/        # 64-bit barrel shifter, LZC priority encoder
│   │   ├── logic_block.py  # Bitwise logic & sign manipulation
│   │   ├── memory/         # SysMEM EBR stack & scratchpad memory
│   │   └── control/        # Microcode program counter, call stack, sequencer
│   └── tests/              # 996 automated unit and integration tests (100% pass)
├── src/                    # Verilog HDL synthesizable modules
├── sim/                    # Verilog testbenches (Icarus Verilog)
└── syn/                    # Lattice Diamond synthesis constraints and scripts
```

---

## Quick Start & Emulator Verification

The repository includes a digital twin emulator and a unit test suite that enforces cycle-accurate hardware modeling:

### 1. Requirements
* Python 3.10+
* `uv` or standard Python `venv`

### 2. Environment Setup
```bash
# Create and activate virtual environment
uv venv .venv
source .venv/bin/activate

# Install package in editable mode with dependencies
uv pip install -e ".[dev]"
```

### 3. Run the Test Suite
```bash
# Run all 990+ emulator unit and integration tests
pytest
```

### 4. Assemble Microcode
To re-assemble the microcode programs from `fpu_emu/asm/` into the runtime emulator image:
```bash
python3 -m fpu_asm -i fpu_emu/ucode.asm -o fpu_emu/ucode.py --no-pad
```

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
