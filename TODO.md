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
- [x] Implement `CONV_U64_F64` (`0xC5`): Unsigned 64-bit uint to IEEE-754 double float (net $0$ bytes on stack, 100% complete, 91 integration tests passing, 8 words).
- [x] Implement `CONV_I64_F64` (`0xCE`): Signed 64-bit int to IEEE-754 double float (net $0$ bytes on stack, 100% complete, 167 integration tests passing, 7 words, shares unsigned core).
- [x] Implement `CONV_F64_I64` (`0xCF`): IEEE-754 double float to signed 64-bit int (truncate toward zero, $V=1$ on range overflow, 100% complete, 49 integration tests passing, 51 words).

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
- [x] Implement `SQRT_F64` (`0x23`): 64-bit IEEE-754 double-precision square root via digit-by-digit binary loop (100% complete, 43 integration tests passing, 57 words).
- [x] Implement `POW_F64` (`0x2B`): 64-bit IEEE-754 double-precision power ($y^x$) via $2^{x \log_2 y}$ dispatch (100% complete, 44 integration tests passing, 33 words).
- [x] Implement `LOG2_F64` (`0x33`): 64-bit base-2 logarithm via argument reduction and 11-term odd series (100% complete, 43 integration tests passing, 113 words).
- [x] Implement `EXP2_F64` (`0x3B`): 64-bit base-2 exponential ($2^x$) via range reduction and 13-term Horner evaluation (100% complete, 52 integration tests passing, 150 words).
- [x] Implement 64-bit trigonometrics: `SIN_F64` (`0x73`), `COS_F64` (`0x7B`), `TAN_F64` (`0x83`) via Cody-Waite range reduction and 8-term Horner evaluation (100% complete, 123 integration tests passing, 216 words total).

#### Remaining F64 Functions & Estimated Instruction Counts
| Category | Operations | Status | Instructions |
| :--- | :--- | :---: | :---: |
| **Basic 64-Bit Float Arithmetic** | `ADD_F64`, `SUB_F64`, `MUL_F64`, `DIV_F64` | **Done** | **87 words (actual)** |
| **Sign / Magnitude Utilities** | `CHS_F64`, `ABS_F64`, `DUP8` | **Done** | **11 words (actual)** |
| **Math Constants** | `PUSH_PI_64` .. `PUSH_INV_SQRT2_64` (8) | **Done** | **22 words (actual)** |
| **Rounding Operations** | `FLOOR_F64`, `CEIL_F64` | **Done** | **42 words (actual)** |
| **Pure Float Conversions** | `CONV_F32_F64`, `CONV_F64_F32` | **Done** | **76 words (actual)** |
| **Integer $\leftrightarrow$ Float Conversions** | `CONV_U64_F64` (8w), `CONV_I64_F64` (7w), `CONV_F64_I64` (51w) | **Done** | **66 words (actual)** |
| **Square Root** | `SQRT_F64` | **Done** | **57 words (actual)** |
| **Logarithm (Base 2)** | `LOG2_F64` | **Done** | **113 words (actual)** |
| **Exponential (Base 2)** | `EXP2_F64` | **Done** | **150 words (actual)** |
| **General Power** | `POW_F64` | **Done** | **33 words (actual)** |
| **Trigonometrics** | `SIN_F64`, `COS_F64`, `TAN_F64` | **Done** | **216 words (actual)** |
| **ALL F64 PRE-REFACTOR OPERATIONS** | **12 operations complete** | **100% DONE** | **873 words total** |

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
>    - **Cumulative Size Tracking:** Track cumulative total size in `fpu_emu/ucode_f64.asm` (currently at 1,335 words).
>    - **Unit / Verification Testing:** Run tests against a fresh `FpgaModel` by executing `fpga.dispatcher._run(assembled_instructions)` directly on pushed stack inputs.
>    - **Instruction Word Accounting:** Measure and log the exact static instruction word count for each routine.
>    - **Refactor Execution:** Once all 12 routines pass unit testing and the total instruction count is verified, execute the machine word rearrangement and EBR 0–5 expansion refactor.
>
> #### F64 Pre-Refactor Implementation Checklist
> - [x] **1. `CONV_F32_F64` (`0xC9`)**: Widens IEEE-754 32-bit float to 64-bit float (100% complete, 40 integration tests passing, 36 words).
> - [x] **2. `CONV_F64_F32` (`0xCB`)**: Narrows IEEE-754 64-bit float to 32-bit float (100% complete, 52 integration tests passing, 40 words, $V=1$ on overflow, $U=1$ on underflow).
> - [x] **3. `CONV_U64_F64` (`0xC5`)**: Unsigned 64-bit integer $\to$ Double float (100% complete, 91 integration tests passing, 8 words).
> - [x] **4. `CONV_I64_F64` (`0xCE`)**: Signed 64-bit integer $\to$ Double float (100% complete, 167 integration tests passing, 7 words, shares unsigned core).
> - [x] **5. `CONV_F64_I64` (`0xCF`)**: Double float $\to$ Signed 64-bit integer (100% complete, 49 integration tests passing, 51 words).
> - [x] **6. `SQRT_F64` (`0x23`)**: 64-bit square root via 54-iteration restoring binary shift-and-subtract loop (100% complete, 43 integration tests passing, 57 words).
> - [x] **7. `LOG2_F64` (`0x33`)**: 64-bit base-2 logarithm via argument reduction and 11-term odd series (100% complete, 43 integration tests passing, 113 words).
> - [x] **8. `EXP2_F64` (`0x3B`)**: 64-bit base-2 exponential ($2^x$) via range reduction and 13-term Horner evaluation (100% complete, 52 integration tests passing, 150 words).
> - [x] **9. `POW_F64` (`0x2B`)**: 64-bit general power ($y^x = 2^{x \cdot \log_2(y)}$) via $2^{x \log_2 y}$ dispatch (100% complete, 44 integration tests passing, 33 words).
> - [x] **10. `SIN_F64` (`0x73`)**: 64-bit sine via Cody-Waite range reduction and 8-term Horner evaluation (100% complete, 42 integration tests passing, shared trig core).
> - [x] **11. `COS_F64` (`0x7B`)**: 64-bit cosine via Cody-Waite range reduction and 8-term Horner evaluation (100% complete, 42 integration tests passing, shared trig core).
> - [x] **12. `TAN_F64` (`0x83`)**: 64-bit tangent via Cody-Waite range reduction and 8-term Horner evaluation (100% complete, 39 integration tests passing, 216 words total for all 3 trig functions).

### 5. Hardware Simulation & Verilog RTL
- [ ] **Host Interface Simulation**:
  - Combinatorial Z80 SRAM memory mapping/decoding and strobe qualification model.
  - Autonomous SPI Flash bootloader copy simulation.
- [ ] **Verilog Implementation**:
  - Modular Verilog RTL corresponding to V2 functional blocks, MUXes, AND walls, and write-back registers.
  - Self-checking Verilog testbenches with `$fatal` assertions on errors.
  - Synthesis for Lattice MachXO2 (`LCMXO2-2000HC-4TG100C`) and timing verification at 80 MHz.

## Appendix: Microcode Optimization & Footprint Reduction Analysis (Saving $\ge 250$ Words)

To fit all microcode within the 1,536-word limit of EBR 0–5 (expanding down from the current 1,743 assembled words in `ucode_f64.asm` to $\le 1,493$ words), the following optimization strategies have been analyzed across all 58 `.asm` files in `fpu_emu/asm/`:

### Summary of Identified Savings

| Strategy | Area | Potential Savings | Complexity / Risk |
| :--- | :--- | :---: | :---: |
| **1. Hardware Macro / Fused Opcode** | `PUSH_HALT <reg>` (or `HALT <reg>`) | **70 words** | Very Low (Hardware/Decoder) |
| **2. Algorithmic Overhaul** | Replace F32 CORDIC with 4-term Horner in `trig_f32.asm` | **105–110 words** | Low (Proven math) |
| **3. Hardware Flag Enhancement** | `UNPACK` sets `OVERFLOW` (or `SPECIAL`) on NaN/Inf | **45–55 words** | Very Low (Datapath flag) |
| **4. Common Shared Subroutines** | Deduplicate Domain Error / Return 1.0 / Int-to-Float | **55–65 words** | None (Assembly only) |
| **5. ROM Constant Offloading** | Load `1.0`, `MAGIC`, $\sqrt{2}$ from CONST ROM instead of synthesizing | **30–40 words** | None (Assembly only) |
| **TOTAL IDENTIFIED SAVINGS** | | **305 – 340 words** | **Target: 250 words** |

Adopting Strategies 1, 2, and 4 alone yields **$\approx 240\text{--}245$ words** with minimal risk. Adding Strategy 3 or 5 brings the total microcode down to **$\approx 1,400\text{--}1,450$ words** (leaving $\approx 100$ words of headroom in EBR 0–5).

---

### Strategy 1: Fused Hardware Opcode — `PUSH_HALT` / `HALT <reg>` (Saves 70 words)

Every user-facing instruction ends by pushing its result to the stack and halting:
- `PUSH AL; HALT`: **35 occurrences**
- `PUSH AX; HALT`: **35 occurrences**
- **Exact total**: **70 occurrences** across all `.asm` files.

#### Architectural Implementation
In the rearranged machine word format:
```text
 31        26 25 24        21 20        17 16        13 12                                 0
+------------+--+------------+------------+------------+------------------------------------+
|   OPCODE   |W |  DST/FLAG  |    SRC1    |    SRC2    |          IMMEDIATE / ADDR          |
+------------+--+------------+------------+------------+------------------------------------+
```
When `HALT` (opcode `0b011_111`) executes, bits `[24:21]` (`DST`) are completely unused.
- If `DST == Reg.NONE` (`0`): Standard `HALT`.
- If `DST != Reg.NONE`: The hardware automatically triggers `PUSH dst` into the math stack in Cycle 1 and asserts `exec_done` in Cycle 2.

```assembly
; BEFORE (2 instructions):
    PUSH AX
    HALT

; AFTER (1 instruction):
    HALT AX
```
**Net Savings: 70 words (100% mechanical, 0 risk).**

---

### Strategy 2: Algorithmic Overhaul — Replace F32 CORDIC with 4-Term Horner (Saves 105–110 words)

`fpu_emu/asm/trig_f32.asm` currently occupies **165 instruction words**. 
It uses a 24-stage circular CORDIC engine with dynamic table lookups (`LDC AH, TRIG, C`), direction testing, dual arithmetic barrel shifts, quadrant unwinding, and coordinate normalization.

#### Why Horner is Superior for F32 on This Hardware:
The Zx50 FPGA hardware already features a **single-cycle 32-bit Booth multiplier** (`MUL` / `MULU`).
After Cody-Waite range reduction to $r \in [-\pi/4, \pi/4]$, IEEE-754 single-precision (24-bit mantissa) requires only **4 polynomial terms**:
$$\sin(r) \approx r \cdot \left(1 - \frac{r^2}{6} \left(1 - \frac{r^2}{20} \left(1 - \frac{r^2}{42}\right)\right)\right)$$
$$\cos(r) \approx 1 - \frac{r^2}{2} \left(1 - \frac{r^2}{12} \left(1 - \frac{r^2}{30}\right)\right)$$

Evaluating a 4-term polynomial with Horner's rule requires only:
1. One float multiplication $t = r^2$ via `MUL_F32_CORE`.
2. 3 multiply-adds with small integer constant divisors (or ROM constants).
3. The entire 24-step CORDIC loop, angle lookup table, and shift logic are eliminated.

- **Current `trig_f32.asm`**: 165 words.
- **Horner `trig_f32.asm`**: ~55 words (mirroring the clean structure of `trig_f64.asm`).
- **Net Savings: ~110 words**.

---

### Strategy 3: Hardware Enhancement — `UNPACK` Sets NaN/Infinity Flag (Saves 45–55 words)

Currently, `adder_block.py` only writes `ZERO`, `SIGN`, and `DIFF_SIGN` during `UNPACK`. It does not flag when the exponent is all 1s (`0xFF` in F32, `0x7FF` in F64).

Consequently, **almost every float routine implements manual NaN/Inf checking**:
- In F32 (2 words):
  ```assembly
  CMP EA, 255
  JZ ZERO, .handle_special
  ```
- In F64 (4 to 7 words):
  ```assembly
  ; Pattern A (4 words in log2_f64, sqrt_f64):
  EXP_SUB EB, EA, 1023
  EXP_SUB EB, EB, 1023
  EXP_SUB EB, EB, 1
  JZ ZERO, .handle_special

  ; Pattern B (6 words in trig_f64):
  MOV DH, AH
  LSL DH, 1
  LSR DH, 21
  ADD DL, DH, 1
  LSR DL, 11
  JNZ ZERO, .handle_special
  ```

#### Hardware Change:
During `UNPACK`, if `exp_val == (1 << exp_width) - 1`, assert `StatusFlag.OVERFLOW` (or `SPECIAL`).
Then in microcode:
```assembly
; BEFORE (4 to 6 words):
    EXP_SUB EB, EA, 1023
    EXP_SUB EB, EB, 1023
    EXP_SUB EB, EB, 1
    JZ ZERO, .special

; AFTER (1 word):
    JNZ OVERFLOW, .special
```
Tested across 15 floating-point routines:
**Net Savings: ~50 words**.

---

### Strategy 4: Common Shared Subroutines & Exit Trampolines (Saves 55–65 words)

Several verbose code sequences are duplicated verbatim across multiple files:

#### 1. F64 Domain Error / Quiet NaN Exit (Duplicated in 6 files)
`sqrt_f64`, `log2_f64`, `exp2_f64`, `pow_f64`, `trig_f64`, `div_f64` each independently generate Quiet NaN `0x7FF80000_00000000`:
```assembly
; Duplicated 6 times (7 instructions each = 42 words):
    XOR AL, AL
    LDI AH, 0x7F
    LSL AH, 8
    OR AH, AH, 0xF8
    LSL AH, 16
    LDI ERR, 1
    HALT AX
```
- **Solution**: Consolidate into a single shared trampoline in `fpu_emu/asm/common_f64.asm`:
  ```assembly
  COMMON_F64_DOMAIN_ERR:
      LDC AX, CONST, 36       ; Slot 36 is NAN_F64
      LDI ERR, 1
      HALT AX
  ```
  Each caller simply executes `JMP COMMON_F64_DOMAIN_ERR` (1 word).
  **Savings: $(7 - 1) \times 6 = 36$ words.**

#### 2. Shared Return +1.0 and 0.0 Exits
Used across `pow_f64`, `exp2_f64`, `trig_f64`, `cos_f64`, `floor_ceil_f64`:
```assembly
COMMON_RET_ONE_F64:
    LDC AX, CONST, 33       ; Slot 33 is ONE_F64
    HALT AX
```
**Savings: ~15 words.**

#### 3. Integer to Float64 Conversion Subroutine
In `exp2_f64` (Horner step divisor) and `trig_f64`:
```assembly
; Repeated 7-instruction conversion:
    LD AL, slot
    XOR AH, AH
    XOR DH, DH
    LDI EA, 1023
    EXP_ADD EA, 52
    CALL NORMALIZE_F64
```
This can reuse `CONV_INT_F64_COMMON` from `fpu_emu/asm/conv_int_f64.asm`.
**Savings: ~12 words.**

---

### Strategy 5: Utilizing CONST ROM vs In-line Synthesis (Saves 30–40 words)

Float64 `1.0` (`0x3FF00000_00000000`) is synthesized on the fly via 3 instructions:
`XOR BL, BL; LDI BH, 1023; LSL BH, 20` (occurs 16 times!).
Similarly, `MAGIC` ($1.5 \times 2^{52} = \text{0x43380000\_00000000}$) is synthesized in 6 instructions:
```assembly
; In exp2_f64 and trig_f64 (6 words each):
    XOR BL, BL
    LDI BH, 0x43
    LSL BH, 8
    OR BH, 0x38
    LSL BH, 16
    STO 2, BX
```
And $\sqrt{2}$ high-word threshold (`0x3FF6A09E`) in `log2_f64`:
```assembly
; In log2_f64 (6 words):
    LDI BL, 1023
    LSL BL, 10
    OR BL, 424
    LSL BL, 10
    OR BL, 158
```
All of these already exist (or can be placed) in the CONST ROM table:
- `ONE_F64` is slot 33–34.
- `SQRT2_F64` is slot 26–27 (`LDC BL, CONST, 27` loads `0x3FF6A09E` in 1 instruction!).
- `MAGIC_F64` can take unused CONST ROM slots 62–63.

Loading from CONST ROM with `LDC` replaces 3- to 6-instruction blocks with a single `LDC`.
**Savings: ~35 words.**

---

### Actionable Roadmap to Save $\ge 250$ Words

| Step | Action | Files | Savings | Cumulative Microcode Size | Status |
| :-: | :--- | :--- | :-: | :-: | :-: |
| — | *Initial baseline* | `ucode_f64.asm` | — | **1,749 words** | Baseline |
| **1** | Implement `HALT <reg>` (push and halt) in Memory Block | Assembler, emulator, all 58 `.asm` files | **-76 words** | **1,673 words** | **COMPLETE** |
| **2** | Replace F32 CORDIC with 4-term Horner | `trig_f32.asm` | **-110 words** | 1,563 words | Planned |
| **3** | Deduplicate Quiet NaN, domain error, and 1.0 exit trampolines | `trig_f64`, `exp2_f64`, `log2_f64`, `pow_f64`, `sqrt_f64` | **-50 words** | **1,513 words** *(< 1,536 limit!)* | Planned |
| **4** | Make `UNPACK` set `OVERFLOW` flag on NaN/Inf | `add_f64`, `mul_f64`, `div_f64`, `trig_f64`, `exp2_f64`, `sqrt_f64` | **-50 words** | **1,463 words** | Planned |
| **5** | Use `LDC` from CONST ROM for `1.0`, `MAGIC`, $\sqrt{2}$ | `log2_f64`, `exp2_f64`, `trig_f64`, `floor_ceil_f64` | **-35 words** | **1,428 words** | Planned |
