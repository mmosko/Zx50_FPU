# Zx50 FPU Rev 2 Development Roadmap

Target Hardware: Lattice MachXO2 FPGA on `boards/zx50_cpu_RevC4` (host: Zilog Z80 @ 10 MHz)  
Architecture Specifications: [SystemDesignV2.md](SystemDesignV2.md) & [SystemReference.md](SystemReference.md)  
Programmer's Guide: [ProgrammersGuide.md](ProgrammersGuide.md)

---

## Current Status & Capacity

- **Test Suite Status:** 100% pass rate (**1,473 / 1,473 tests passing**).
- **Microcode Capacity:** **1,023 / 1,024 words used** (**1 instruction word of headroom remaining** in a single 10-bit UPC address space).
- **Hardware Call Stack:** 16-deep $\times$ 10-bit return-address stack in distributed LUT RAM (`RAM16X1S`) with 4-bit `CSP` pointer fully implemented and verified.
- **Datapath Bus Symmetry:** `HA_MUX` and `HB_MUX` widened to full 4-bit symmetry (14:1 32-bit muxing across all 10 registers `AL`..`FH`, `EA`, `EB`, `C`, and `IMM`), allowing any register as `src1` without register shuffling.
- **Completed 32-Bit Math Operations:**
  - Standard integer arithmetic: `ADD_I32`, `SUB_I32`, `MUL_I32`, `DIV_I32` (100% complete).
  - Unsigned integer arithmetic: `ADD_U32`, `SUB_U32`, `MUL_U32`, `DIV_U32` (100% complete).
  - Floating-point arithmetic: `ADD_F32`, `SUB_F32`, `MUL_F32`, `DIV_F32`.
  - Conversions: `CONV_U32_I32`, `CONV_I32_U32`, `CONV_U32_F32`, `CONV_I32_F32`, `CONV_F32_I32`.
  - Math utilities: `ABS_I32`, `ABS_F32`, `CHS_I32`, `CHS_F32`, `FLOOR_F32`, `CEIL_F32`, `DUP4`.
  - Transcendentals: `SQRT_F32`, `EXP2_F32`, `LOG2_F32`, `POW_F32`.
  - CORDIC Trigonometrics: `SIN_F32`, `COS_F32`, `TAN_F32` (with Cody-Waite range reduction and asymptote detection).
  - Memory Storage: `CP_MEMx_TOS` (slots 0..15), `CP_TOS_MEMx` (slots 0..15), `ZERO_MEM` (using indirect addressing and latched opcode nibble dispatch).
  - Math Constants: `PUSH_PI_32`, `PUSH_E_32`, `PUSH_LN2_32`, `PUSH_LOG2E_32`, `PUSH_LOG2_10_32`, `PUSH_LOG10_2_32`, `PUSH_SQRT2_32`, `PUSH_INV_SQRT2_32`.
- **Completed 64-Bit Math Operations:**
  - Standard integer arithmetic: `ADD_I64`, `SUB_I64`, `MUL_I64`, `DIV_I64` (100% complete).
  - Unsigned integer arithmetic: `ADD_U64`, `SUB_U64`, `MUL_U64`, `DIV_U64` (100% complete).
  - Floating-point arithmetic: `ADD_F64`, `SUB_F64`, `MUL_F64`, `DIV_F64` (100% complete).
  - Rounding operations: `FLOOR_F64`, `CEIL_F64` (100% complete, 41 integration tests passing, 42 words).
  - Utilities: `ABS_I64`, `CHS_I64`, `ABS_F64`, `CHS_F64`, `DUP8`.
  - Math Constants: `PUSH_PI_64`, `PUSH_E_64`, `PUSH_LN2_64`, `PUSH_LOG2E_64`, `PUSH_LOG2_10_64`, `PUSH_LOG10_2_64`, `PUSH_SQRT2_64`, `PUSH_INV_SQRT2_64`.

---

## Architectural Optimizations

### 1. Widen `HA_MUX` to Full 4-Bit Symmetry (~20–30 Words Saved)
- [x] **Expand `HA_MUX` from 3 Bits to 4 Bits (Completed)**:
  - `HA_MUX` and `HB_MUX` both support full 4-bit addressing across `{AL, AH, BL, BH, CL, CH, DL, DH, FL, FH, EA, EB, C, IMM}`.
  - Eliminates redundant register shuffling (`MOV AL, FL; ADD AL, BL; MOV FL, AL`), allowing any register as `src1`.

### 2. Populate Range Reduction Constants in `CONST` ROM (Low Priority - Minimal Savings)
- [ ] **Add Cody-Waite Constants to `CONST` ROM (Low Priority)**:
  - Add $C_1 = 102943$ and $C_2 = 11601$ into unused slots of `CONST` ROM.
  - Low priority: saves very little microcode space (~8 words) and is deferred in favor of functional features.

### 3. Implement 64-Bit Hardware Support for `CMP` and `SWAP` (`_cmp64` & `_swap64`)
- [x] **Hardware 64-Bit Comparison (`_cmp64` in `AdderBlock`)**:
  - Implement full 64-bit compare `CMP AX, BX` (`W=1`, 2 cycles) evaluating 64-bit `{src1_h, src1_l} - {src2_h, src2_l}` without register writeback, setting `CF`, `ZF`, `SF`, and `VF` according to the full 64-bit comparison.
  - Shrinks `ALIGN_F64` mantissa comparison from 5 microcode instructions to 1 (`CMP AX, BX`).
- [x] **Hardware 64-Bit Register Exchange (`_swap64` in `MemoryBlock`)**:
  - Implement full 64-bit register exchange `SWAP AX, BX` (`W=1`, 4 cycles) exchanging `{AH, AL} <-> {BH, BL}` using internal staging registers `{FH, FL}`.
  - Shrinks `ALIGN_F64` operand swap from 3 microcode instructions to 1 (`SWAP AX, BX`).

### 4. Microcode Compaction & ISA Optimization (36 Words Saved, 100 Words Headroom Opened)
- [x] **Dynamic Constant Table Loading (`push_const.asm`)**:
  - Replaced individual constant loaders with dynamic lookup using `LSL C, 1` into the `CONST` table for all 16 float32/float64 constants.
  - Saved **24 words** of microcode ROM.
- [x] **64-Bit Alignment Optimization (`align_f64.asm`)**:
  - Leveraged 64-bit `CMP AX, BX` (replacing 5-word comparison) and 64-bit `SWAP AX, BX` (replacing 3-word register juggling).
  - Saved **5 words** of microcode ROM.
- [x] **Integer Division Optimizations (`div_int.asm`)**:
  - Ternary sign setup: `XOR DL, AH, BH` (saved 1 word).
  - Consolidated restoring loop branches Path 1 & Path 2 at `.restoring_step` (saved 3 words).
  - Shared exit tails across 64-bit division paths (saved 2 words).
  - Saved **6 words** of microcode ROM total.
- [x] **64-Bit Integer Negation Optimization (`chs_i64.asm`)**:
  - Replaced `MOV FX, AX` + `XOR AX, AX` + `SUB AX, FX` with `XOR FX, FX` + `SUB AX, FX, AX`.
  - Saved **1 word** of microcode ROM and **2 clock cycles** of execution latency.

---

## Remaining Functional Roadmap

### 1. Pure Integer Conversions
- [x] Implement `CONV_I32_I64` (`0xC8`): Sign-extend signed 32-bit int to 64-bit int (net $+4$ bytes on stack).
- [x] Implement `CONV_I64_I32` (`0xCA`): Narrow signed 64-bit int to 32-bit int with truncation overflow check ($V=1$) (net $-4$ bytes on stack).
- [x] Implement `CONV_U32_U64` (`0xC2`): Zero-extend unsigned 32-bit uint to 64-bit uint (net $+4$ bytes on stack).
- [ ] Implement `CONV_U64_U32` (`0xC3`): Narrow unsigned 64-bit uint to 32-bit uint with truncation overflow check ($V=1$) (net $-4$ bytes on stack) — **NEXT IN QUEUE**.
- [x] Implement `CONV_U32_I32` (`0xC6`): Convert unsigned 32-bit uint to signed 32-bit int with range overflow check ($V=1$ if $u32 \ge 2^{31}$) (net $0$ bytes).
- [x] Implement `CONV_I32_U32` (`0xC7`): Convert signed 32-bit int to unsigned 32-bit uint with range overflow check ($V=1$ if $i32 < 0$) (net $0$ bytes).

### 2. Hybrid Integer $\leftrightarrow$ Floating-Point Conversions
- [x] Implement `CONV_U32_F32` (`0xC4`): Unsigned 32-bit uint to IEEE-754 single float (net $0$ bytes on stack).
- [x] Implement `CONV_I32_F32` (`0xCC`): Signed 32-bit int to IEEE-754 single float (net $0$ bytes on stack).
- [x] Implement `CONV_F32_I32` (`0xCD`): IEEE-754 single float to signed 32-bit int (truncate toward zero, $V=1$ on range overflow).
- [ ] Implement `CONV_U64_F64` (`0xC5`): Unsigned 64-bit uint to IEEE-754 double float (net $0$ bytes on stack, ~10–14 words).
- [ ] Implement `CONV_I64_F64` (`0xCE`): Signed 64-bit int to IEEE-754 double float (net $0$ bytes on stack, ~14–18 words).
- [ ] Implement `CONV_F64_I64` (`0xCF`): IEEE-754 double float to signed 64-bit int (truncate toward zero, $V=1$ on range overflow, ~18–22 words).

### 3. Floating-Point Conversions & Utilities
- [x] Implement `CONV_F32_F64` (`0xC9`): Expand IEEE single float to double float (net $+4$ bytes on stack, 100% complete, 40 integration tests passing, 36 words).
- [x] Implement `CONV_F64_F32` (`0xCB`): Narrow IEEE double float to single float (net $-4$ bytes on stack, $V=1$ on exponent overflow, $U=1$ on underflow, 100% complete, 52 integration tests passing, 40 words).
- [x] Implement `FLOOR_F32` (`0x61`): Mathematical floor toward $-\infty$.
- [x] Implement `FLOOR_F64` (`0x63`): Mathematical floor toward $-\infty$ (100% complete, 41 integration tests passing, shared implementation with `CEIL_F64`).
- [x] Implement `CEIL_F32` (`0x69`): Mathematical ceiling toward $+\infty$.
- [x] Implement `CEIL_F64` (`0x6B`): Mathematical ceiling toward $+\infty$ (100% complete, 41 integration tests passing, 42 words total for both).

### 4. 64-Bit Floating-Point Arithmetic & Transcendentals
- [x] Implement `ADD_F64` (`0x04`): 64-bit IEEE-754 double-precision addition with `align_f64` and `normalize_f64` (100% complete, 30 integration tests passing, 28 words).
- [x] Implement `SUB_F64` (`0x0C`): 64-bit IEEE-754 double-precision subtraction (reusing `ADD_F64_CORE`, 28 integration tests passing, 6 words).
- [x] Implement `MUL_F64` (`0x14`): 64-bit IEEE-754 double-precision multiplication using cross-terms via hardware Booth multiplier (100% complete, 29 integration tests passing, 25 words).
- [x] Implement `DIV_F64` (`0x1C`): 64-bit IEEE-754 double-precision division via 54-iteration restoring loop (100% complete, 45 integration tests passing, 28 words).
- [ ] Implement `SQRT_F64` (`0x23`): 64-bit IEEE-754 double-precision square root via digit-by-digit binary loop (~35–45 words).
- [ ] Implement `POW_F64` (`0x2B`): 64-bit IEEE-754 double-precision power ($x^y$) via $2^{y \log_2 x}$ dispatch (~20–30 words).
- [ ] Implement `LOG2_F64` (`0x33`): 64-bit base-2 logarithm via degree 7–8 Chebyshev polynomial (~90–130 words).
- [ ] Implement `EXP2_F64` (`0x3B`): 64-bit base-2 exponential ($2^x$) via degree 7–8 polynomial (~80–110 words).
- [ ] Implement 64-bit CORDIC trigonometrics: `SIN_F64` (`0x73`), `COS_F64` (`0x7B`), `TAN_F64` (`0x83`) (~180–240 words).

#### Remaining F64 Functions & Estimated Instruction Counts
| Category | Operations | Status | Estimated Instructions |
| :--- | :--- | :---: | :---: |
| **Basic 64-Bit Float Arithmetic** | `ADD_F64`, `SUB_F64`, `MUL_F64`, `DIV_F64` | **Done** | **87 words (actual)** |
| **Sign / Magnitude Utilities** | `CHS_F64`, `ABS_F64`, `DUP8` | **Done** | **11 words (actual)** |
| **Math Constants** | `PUSH_PI_64` .. `PUSH_INV_SQRT2_64` (8) | **Done** | **22 words (actual)** |
| **Rounding Operations** | `FLOOR_F64`, `CEIL_F64` | **Done** | **42 words (actual)** |
| **Pure Float Conversions** | `CONV_F32_F64`, `CONV_F64_F32` | **Done** | **76 words (actual)** |
| **Integer $\leftrightarrow$ Float Conversions** | `CONV_U64_F64`, `CONV_I64_F64`, `CONV_F64_I64` | Pending | **~42 – 54 words** |
| **Square Root** | `SQRT_F64` | Pending | **~35 – 45 words** |
| **Transcendentals** | `LOG2_F64`, `EXP2_F64`, `POW_F64` | Pending | **~190 – 270 words** |
| **CORDIC Trigonometrics** | `SIN_F64`, `COS_F64`, `TAN_F64` | Pending | **~180 – 240 words** |
| **TOTAL REMAINING F64 INSTRUCTIONS** | **10 remaining operations** | Pending | **~395 – 495 words** |

> [!IMPORTANT]
> ### Microcode ROM Expansion & Architecture Refactor Plan (80–120 MHz)
> To comfortably host the complete 64-bit floating-point, transcendental, and trigonometric suite without compromise, the FPU architecture is being upgraded from 1,024 words to **1,536 words**:
>
> 1. **EBR Memory Re-partitioning (MachXO2-2000, 8 EBRs Total):**
>    - **EBR 0–5 (Microcode Store):** 6 EBR blocks configured as **1,536 words $\times$ 32 bits** (expanding microcode capacity by 512 words).
>    - **EBR 6–7 (Data RAM & Stack):** 2 EBR blocks configured as **512 words $\times$ 32 bits** (dedicated to math stack [128 words], scratchpad [64 words], user storage [16 words], and core constants [304 words]).
>    - **Zero-Contention Parallel Access:** Microcode fetching (EBR 0–5) and Stack/Scratchpad read/write (EBR 6–7) operate on physically isolated EBR blocks, guaranteeing single-cycle concurrent execution without pipeline stalls.
>    - **External 10ns Fast SRAM:** Large lookup tables (CORDIC angle tables, Chebyshev polynomial coefficients, Newton-Raphson seeds) are offloaded to external 10ns SRAM. At 80–120 MHz ($T_{\text{clk}} = 8.3\text{ – }12.5\text{ ns}$), SRAM accesses execute with 1–2 NOPs / wait cycles, which is negligible for multi-cycle transcendental routines.
>
> 2. **Machine Word Rearrangement (Fixed 32-Bit Word):**
>    - Retains fixed 32-bit instructions (avoiding variable-length/16-bit decoding penalties, alignment logic, and timing degradation at 80–120 MHz).
>    - Reuses bits `[24:21]` as a shared `DST/FLAG` field (since branches evaluate condition flags without a destination register, while datapath ops write to a destination register without condition flags).
>    ```text
>     31        26 25 24        21 20        17 16        13 12                                 0
>    +------------+--+------------+------------+------------+------------------------------------+
>    |   OPCODE   |W |  DST/FLAG  |    SRC1    |    SRC2    |          IMMEDIATE / ADDR          |
>    |   [31:26]  |  |  [24:21]   |  [20:17]   |  [16:13]   |              [12:0]                |
>    |   (6 bits) |  |  (4 bits)  |  (4 bits)  |  (4 bits)  |             (13 bits)              |
>    +------------+--+------------+------------+------------+------------------------------------+
>    ```
>    - **13-Bit Immediate / Address Reach (`[12:0]`, 0 .. 8,191):** Directly addresses up to 8,192 words of microcode and allows full IEEE-754 double-precision exponent and constant immediates (like 1023, 1075, 2047) without masking workarounds.
>    - **Full 3-Address Ternary Operations:** Preserves `DST`, `SRC1`, and `SRC2` for single-cycle ternary ALU arithmetic (`EXP_SUB`, `SUB`, `ADD`, `MULU`).
>
> 3. **F64 Pre-Refactor Plan (In-Memory Assembly & Verification):**
>    To avoid polluting the repository with binary/object files and prevent blowing past the 1,024-word ROM limit before the hardware refactor:
>    - **Standalone Assembly Files:** Author each of the remaining 12 F64 operations in standalone `.asm` files under `fpu_emu/asm/`.
>    - **Exclude from `ucode.asm`:** Do **not** `.include` these new files into `ucode.asm` yet. The existing 1,023-word ROM remains green with all 1,473 tests passing.
>    - **In-Memory Assembly:** In tests, assemble the `.asm` files dynamically via `fpu_asm.Assembler().assemble_file(path)` directly into `List[MicroInstruction]` in memory (zero filesystem object artifacts).
>    - **Cumulative Size Tracking:** Track cumulative total size in `fpu_emu/ucode_f64.asm` (currently at 1,099 words).
>    - **Unit / Verification Testing:** Run tests against a fresh `FpgaModel` by executing `fpga.dispatcher._run(assembled_instructions)` directly on pushed stack inputs.
>    - **Instruction Word Accounting:** Measure and log the exact static instruction word count for each routine.
>    - **Refactor Execution:** Once all 12 routines pass unit testing and the total instruction count is verified, execute the machine word rearrangement and EBR 0–5 expansion refactor.
>
> #### F64 Pre-Refactor Implementation Checklist
> - [x] **1. `CONV_F32_F64` (`0xC9`)**: Widens IEEE-754 32-bit float to 64-bit float (100% complete, 40 integration tests passing, 36 words).
> - [x] **2. `CONV_F64_F32` (`0xCB`)**: Narrows IEEE-754 64-bit float to 32-bit float (100% complete, 52 integration tests passing, 40 words, $V=1$ on overflow, $U=1$ on underflow).
> - [ ] **3. `CONV_U64_F64` (`0xC5`)**: Unsigned 64-bit integer $\to$ Double float.
> - [ ] **4. `CONV_I64_F64` (`0xCE`)**: Signed 64-bit integer $\to$ Double float (shares unsigned core).
> - [ ] **5. `CONV_F64_I64` (`0xCF`)**: Double float $\to$ Signed 64-bit integer.
> - [ ] **6. `SQRT_F64` (`0x23`)**: 64-bit square root via 54-iteration restoring binary shift-and-subtract loop.
> - [ ] **7. `LOG2_F64` (`0x33`)**: 64-bit base-2 logarithm via argument reduction and Chebyshev polynomial.
> - [ ] **8. `EXP2_F64` (`0x3B`)**: 64-bit base-2 exponential ($2^x$) via range reduction and polynomial evaluation.
> - [ ] **9. `POW_F64` (`0x2B`)**: 64-bit general power ($y^x = 2^{x \cdot \log_2(y)}$).
> - [ ] **10. `SIN_F64` (`0x73`)**: 64-bit circular CORDIC sine (53 iterations).
> - [ ] **11. `COS_F64` (`0x7B`)**: 64-bit circular CORDIC cosine (shared CORDIC core).
> - [ ] **12. `TAN_F64` (`0x83`)**: 64-bit circular CORDIC tangent (CORDIC $\to$ `DIV_F64_CORE`).

### 5. Hardware Simulation & Verilog RTL
- [ ] **Host Interface Simulation**:
  - Combinatorial Z80 SRAM memory mapping/decoding and strobe qualification model.
  - Autonomous SPI Flash bootloader copy simulation.
- [ ] **Verilog Implementation**:
  - Modular Verilog RTL corresponding to V2 functional blocks, MUXes, AND walls, and write-back registers.
  - Self-checking Verilog testbenches with `$fatal` assertions on errors.
  - Synthesis for Lattice MachXO2 (`LCMXO2-2000HC-4TG100C`) and timing verification at 80 MHz.
