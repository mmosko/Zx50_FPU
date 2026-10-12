# Zx50 FPU Rev 2 Development Roadmap

Target Hardware: Lattice MachXO2 FPGA on `boards/zx50_cpu_RevC4` (host: Zilog Z80 @ 10 MHz)  
Architecture Specifications: [SystemDesignV2.md](SystemDesignV2.md) & [SystemReference.md](SystemReference.md)  
Programmer's Guide: [ProgrammersGuide.md](ProgrammersGuide.md)

---

## Current Status & Capacity

- **Test Suite Status:** 100% pass rate (**2,183 / 2,183 tests passing**).
- **Microcode Size:** **1,563 words** across unified single- and double-precision math, transcendentals, and polynomials (down from initial 1,749 baseline; target is $\le 1,536$ words to fit 6 EBR blocks).
- **Machine Word Format (Rev 2):** Fully transitioned to 13-bit immediate format (`[31:26]` OPCODE, `[25]` W, `[24:21]` DST/FLAG, `[20:17]` SRC1, `[16:13]` SRC2, `[12:0]` IMM/ADDR) with `SET <flag>, <src1>` instruction.
- **Hardware Call Stack:** 16-deep $\times$ 10-bit return-address stack in distributed LUT RAM (`RAM16X1S`) with 4-bit `CSP` pointer fully implemented and verified.
- **Datapath Bus Symmetry:** `HA_MUX` and `HB_MUX` widened to full 4-bit symmetry (14:1 32-bit muxing across all 10 registers `AL`..`FH`, `EA`, `EB`, `C`, and `IMM`), allowing any register as `src1` without register shuffling.
- **Completed 32-Bit Math Operations:**
  - Standard integer arithmetic: `ADD_I32`, `SUB_I32`, `MUL_I32`, `DIV_I32` (100% complete).
  - Unsigned integer arithmetic: `ADD_U32`, `SUB_U32`, `MUL_U32`, `DIV_U32` (100% complete).
  - Floating-point arithmetic: `ADD_F32`, `SUB_F32`, `MUL_F32`, `DIV_F32`.
  - Conversions: `CONV_U32_I32`, `CONV_I32_U32`, `CONV_U32_F32`, `CONV_I32_F32`, `CONV_F32_I32`.
  - Math utilities: `ABS_I32`, `ABS_F32`, `CHS_I32`, `CHS_F32`, `FLOOR_F32`, `CEIL_F32`, `DUP4`.
  - Transcendentals: `SQRT_F32`, `EXP2_F32`, `LOG2_F32`, `POW_F32`.
  - Trigonometrics: `SIN_F32`, `COS_F32`, `TAN_F32` (via Cody-Waite range reduction and fast unrolled Horner polynomial evaluation; CORDIC table eliminated).
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

### Completed Architectural Enhancements

- [x] **Machine Word Rearrangement (Rev 2, 13-Bit Immediate):** Fully implemented and verified. Fixed 32-bit layout with `OPCODE[31:26]`, `W[25]`, `DST/FLAG[24:21]`, `SRC1[20:17]`, `SRC2[16:13]`, `IMM[12:0]`. Added `SET <flag>, <src1>` instruction. Exponent bounds (2047, 1075, 1034) directly evaluated via 13-bit immediates.
- [x] **Hardware Macro Opcode (`HALT <reg>`):** Fused stack push + halt opcode saving 76 microcode words.
- [x] **Hardware Call Stack:** 16-deep $\times$ 10-bit return-address stack in distributed LUT RAM (`RAM16X1S`) with 4-bit `CSP` pointer.
- [x] **Full 4-Bit Bus Symmetry:** `HA_MUX` and `HB_MUX` widened to 14:1 32-bit muxing across all registers (`AL`..`FH`, `EA`, `EB`, `C`, `IMM`).
- [x] **Hardware 64-Bit Arithmetic Extensions:** 64-bit comparison (`_cmp64`, `CMP AX, BX`) and 64-bit register swap (`_swap64`, `SWAP AX, BX`).
- [x] **Microcode Compaction & ISA Tuning:** Dynamic constant loading (`push_const.asm`), restoring division loop shared tails, ternary sign setup. Saved 36 words.

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
> ### 100% On-Chip EBR Memory Architecture (MachXO2-2000: 8 EBRs Total, Zero External SRAM)
> By delegating 32-bit transcendentals to 64-bit cores and eliminating obsolete tables, the entire FPU (Code, Stack, Scratchpad, and ROM Tables) fits **100% within the 8 on-chip EBR blocks of the MachXO2-2000**, completely eliminating external 10ns byte SRAM, bus turnarounds, wait-state generators, and 26+ external PCB pins.
>
> ```text
> +-----------------------------------------------------------------------------------+
> |                           MACHXO2-2000 (8 EBR BLOCKS)                             |
> +---------------------------------------------------+-------------------------------+
> |             EBR 0 .. 5: CODE_ROM                  |       EBR 6 .. 7: DATA_RAM    |
> |             (1,536 Words x 32-bit)                |       (512 Words x 32-bit)    |
> +---------------------------------------------------+-------------------------------+
> |  Microcode Store (All 32-bit & 64-bit operations): | - Math Stack:     128 words   |
> |    - Current Baseline: 1,563 words                | - Scratchpad:      64 words   |
> |    - After F32 Delegation: ~1,287 words           | - User Storage:    16 words   |
> |    - Free Headroom:    ~249 words in EBR 0..5     | - CONST ROM:       64 words   |
> |                                                   |   (Total Used:    272 words)  |
> |                                                   | - Free Headroom:  240 words   |
> +---------------------------------------------------+-------------------------------+
> ```
>
> ### F32 $\to$ F64 $\to$ F32 Transcendental Delegation Architecture
>
> Rather than maintaining separate, duplicate 32-bit and 64-bit polynomial engines, all 32-bit transcendentals and trigonometrics are implemented as thin wrappers calling the verified 64-bit cores via standard format conversions:
>
> 1. **Unary Transcendentals (`EXP2_F32`, `LOG2_F32`, `SIN_F32`, `COS_F32`, `TAN_F32`):**
>    - `POP_ONE_32` pops 32-bit float $X$ into `AL`.
>    - `CALL CONV_F32_F64_CORE` expands $X$ to 64-bit double in `AX`.
>    - `CALL <OP>_F64_CORE` computes high-precision 53-bit result in `AX`.
>    - `CALL CONV_F64_F32_CORE` narrows back to float32 in `AL` (handles IEEE rounding, F32 overflow/underflow via `NORMALIZE_F32`).
>    - `HALT AL` pushes result and halts.
>    - Size per operation: **5 words** each (replaces 60w in `exp2_f32`, 81w in `log2_f32`, 144w in `trig_f32`).
>
> 2. **Binary Power (`POW_F32`):**
>    - `POP_TWO_32` pops base $Y$ and exponent $X$.
>    - Converts both operands to float64, dispatches to `POW_F64_CORE`, and narrows back via `CONV_F64_F32_CORE`.
>    - Size: **~12 words** (replaces 30w in `pow_f32`).
>
> 3. **Elimination of Obsolete ROM Tables:**
>    - **`CHEB` (128 words):** Polynomial constants solely used by 32-bit `exp2`, `log2`, and `trig`. **100% ELIMINATED.**
>    - **`TRIG` (128 words):** CORDIC arctangent tables unused since migration to Horner. **100% ELIMINATED.**
>    - **`SEEDS` (256 words):** Newton-Raphson seeds unused since adopting restoring division and binary sqrt. **100% ELIMINATED.**
>    - **`CONST` (64 words):** Retained in EBR 6–7 for common float32/float64 math constants ($\pi, e, \ln(2), \text{MAGIC}, 1.0, C_1..C_3$).
>
> 4. **Archiving Dedicated High-Speed F32 Routines (Future Larger FPGA Path):**
>    - The current high-speed single-cycle Booth-multiplier implementations (`exp2_f32.asm`, `log2_f32.asm`, `pow_f32.asm`, `trig_f32.asm`) will be preserved in standalone archive files (e.g., `fpu_emu/asm/archived_fast_f32/` or `*_fast.asm`).
>    - They will **NOT** be `.include`d in `ucode.asm` / `ucode_f64.asm`, preserving the strict $\le 1,536$-word footprint for the MachXO2-2000.
>    - If the project later transitions to a larger FPGA (such as the Lattice MachXO3 or ECP5 with additional EBRs), these fast dedicated routines (~45 cycles) can be swapped back in directly to regain wire-speed 32-bit transcendental execution without re-engineering.
>
> **Projected Net Savings:** **~276 microcode words** saved ($315 \to 39$ words across the 4 files), reducing total microcode from **1,563 words down to ~1,287 words** (well under the 1,536 limit with ~249 words of headroom).

### 5. Hardware Simulation & Verilog RTL
- [ ] **Host Interface Simulation**:
  - Combinatorial Z80 SRAM memory mapping/decoding and strobe qualification model.
  - Autonomous SPI Flash bootloader copy simulation.
- [ ] **Verilog Implementation**:
  - Modular Verilog RTL corresponding to V2 functional blocks, MUXes, AND walls, and write-back registers.
  - Self-checking Verilog testbenches with `$fatal` assertions on errors.
  - Synthesis for Lattice MachXO2 (`LCMXO2-2000HC-4TG100C`) and timing verification at 80 MHz.

## Appendix: Microcode Optimization & Footprint Reduction Analysis (Saving $\ge 250$ Words)

To fit all microcode within the 1,536-word limit of EBR 0–5 (expanding down from the initial 1,749 baseline in `ucode_f64.asm` to $\le 1,536$ words), the following optimization strategies have been analyzed across all 58 `.asm` files in `fpu_emu/asm/`:

### Summary of Identified Savings

| Strategy | Area | Potential Savings | Complexity / Risk | Status |
| :--- | :--- | :---: | :---: | :---: |
| **1. Hardware Macro / Fused Opcode** | `HALT <reg>` (push and halt in memory block) | **-76 words** | Very Low (Hardware/Decoder) | **COMPLETE** |
| **1b. Mul Loop Consolidate** | Consolidate `LDI DL, 1` in `USER_MUL_U64` | **-12 words** | None (Assembly only) | **COMPLETE** |
| **2. Algorithmic Overhaul** | Replace F32 CORDIC with Horner in `trig_f32.asm` | **-15 words** | Low (Proven math) | **COMPLETE** |
| **3. ROM Constant Offloading** | Load `1.0`, `MAGIC`, $\sqrt{2}$ from CONST ROM instead of synthesizing | **-46 words** | None (Assembly only) | **COMPLETE** |
| **4. 13-Bit Immediate Optimization** | Direct exponent and bound checks (2047, 1075, 1034) | **-37 words** | None (Assembly only) | **COMPLETE** |
| **5. F32 $\to$ F64 $\to$ F32 Delegation** | Delegate `EXP2`, `LOG2`, `POW`, `TRIG` to F64 cores | **~276 words** | Low (Assembly wrappers) | **NEXT IN QUEUE** |
| **6. Common Shared Subroutines** | Deduplicate Quiet NaN / Domain Error / Return 1.0 | **~35 words** | None (Assembly only) | Optional Reserve |
| **CURRENT PROGRESS** | **Initial: 1,749 words $\to$ Current: 1,563 words** | **-186 words saved** | **Target: $\le 1,536$ words** | **Only 27 words to go!** |
| **PROJECTED AFTER STRATEGY 5** | **1,563 words $\to$ ~1,287 words** | **-276 words saved** | **8 EBR On-Chip Goal: MET** | **~249 words free headroom** |

Adopting Strategies 1, 1b, 2, 3, and 4 has saved **186 words** (bringing microcode down from 1,749 to 1,563 words). Executing Strategy 5 (F32 $\to$ F64 $\to$ F32 Delegation) will save another **~276 words**, comfortably landing at **~1,287 words** and achieving 100% on-chip EBR residency (zero external SRAM).

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
| **1** | Implement `HALT <reg>` (push and halt) in Memory Block | Assembler, emulator, all 58 `.asm` files | **-76 words** | 1,673 words | **COMPLETE** |
| **1b** | Consolidate `LDI DL, 1` in `USER_MUL_U64` | `mul_int.asm` | **-12 words** | 1,661 words | **COMPLETE** |
| **2** | Replace F32 CORDIC with Horner polynomial | `trig_f32.asm`, `build_flash.py` | **-15 words** | 1,646 words | **COMPLETE** |
| **3** | Use `LDC` from CONST ROM for `1.0`, `MAGIC`, $\sqrt{2}$ | `build_flash.py`, `log2_f64`, `exp2_f64`, `pow_f64`, `trig_f64` | **-46 words** | 1,600 words | **COMPLETE** |
| **4** | 13-bit immediate optimizations (direct 2047, 1075, bounds) | `conv_f64_f32`, `exp2_f64`, `log2_f64`, `sqrt_f64`, `trig_f64`, `conv_f32_f64` | **-37 words** | **1,563 words** | **COMPLETE** |
| **5** | **F32 $\to$ F64 $\to$ F32 Delegation & 100% On-Chip EBR Budget** | `exp2_f32`, `log2_f32`, `pow_f32`, `trig_f32`, `conv_f32_f64`, `conv_f64_f32` | **-276 words** | **~1,287 words** *(Fits 8 EBRs!)* | **NEXT IN QUEUE** |
| **6** | Deduplicate Quiet NaN, domain error, and 1.0 exit trampolines | `trig_f64`, `exp2_f64`, `log2_f64`, `pow_f64`, `sqrt_f64` | **~35 words** | **~1,252 words** | Optional Reserve |
| **7** | Make `UNPACK` set `OVERFLOW` flag on NaN/Inf | `add_f64`, `mul_f64`, `div_f64`, `trig_f64`, `exp2_f64`, `sqrt_f64` | **~30 words** | **~1,222 words** | Optional Reserve |
