# Zx50 FPU Rev 2 Development Roadmap

Target Hardware: Lattice MachXO2 FPGA on `boards/zx50_cpu_RevC4` (host: Zilog Z80 @ 10 MHz)  
Architecture Specifications: [SystemDesignV2.md](SystemDesignV2.md) & [SystemReference.md](SystemReference.md)  
Programmer's Guide: [ProgrammersGuide.md](ProgrammersGuide.md)

---

## Current Status & Capacity

- **Test Suite Status:** 100% pass rate (**2,183 / 2,183 tests passing**).
- **Microcode Size:** **1,563 words** across unified single- and double-precision math, transcendentals, and polynomials
  (down from initial 1,749 baseline; target is $\le 1,536$ words to fit 6 EBR blocks).

---

### Completed Architectural Enhancements

---

## Remaining Functional Roadmap


> [!IMPORTANT]
> ### 100% On-Chip EBR Memory Architecture (MachXO2-2000: 8 EBRs Total, Zero External SRAM)
> By delegating 32-bit transcendentals to 64-bit cores and eliminating obsolete tables, the entire FPU (Code, Stack,
Scratchpad, and ROM Tables) fits **100% within the 8 on-chip EBR blocks of the MachXO2-2000**, completely eliminating
external 10ns byte SRAM, bus turnarounds, wait-state generators, and 26+ external PCB pins.
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
> Rather than maintaining separate, duplicate 32-bit and 64-bit polynomial engines, all 32-bit transcendentals and
trigonometrics are implemented as thin wrappers calling the verified 64-bit cores via standard format conversions:
>
> 1. **Unary Transcendentals (`EXP2_F32`, `LOG2_F32`, `SIN_F32`, `COS_F32`, `TAN_F32`):**
>    - `POP_ONE_32` pops 32-bit float $X$ into `AL`.
    >    - `CALL CONV_F32_F64_CORE` expands $X$ to 64-bit double in `AX`.
    >    - `CALL <OP>_F64_CORE` computes high-precision 53-bit result in `AX`.
    >    - `CALL CONV_F64_F32_CORE` narrows back to float32 in `AL` (handles IEEE rounding, F32 overflow/underflow via
           `NORMALIZE_F32`).
    >    - `HALT AL` pushes result and halts.
    >    - Size per operation: **5 words** each (replaces 60w in `exp2_f32`, 81w in `log2_f32`, 144w in `trig_f32`).
>
> 2. **Binary Power (`POW_F32`):**
>    - `POP_TWO_32` pops base $Y$ and exponent $X$.
    >    - Converts both operands to float64, dispatches to `POW_F64_CORE`, and narrows back via `CONV_F64_F32_CORE`.
    >    - Size: **~12 words** (replaces 30w in `pow_f32`).
>
> 3. **Elimination of Obsolete ROM Tables:**
>    - **`CHEB` (128 words):** Polynomial constants solely used by 32-bit `exp2`, `log2`, and `trig`. **100%
       ELIMINATED.**
    >    - **`TRIG` (128 words):** CORDIC arctangent tables unused since migration to Horner. **100% ELIMINATED.**
    >    - **`SEEDS` (256 words):** Newton-Raphson seeds unused since adopting restoring division and binary sqrt.
           **100% ELIMINATED.**
    >    - **`CONST` (64 words):** Retained in EBR 6–7 for common float32/float64 math constants
           ($\pi, e, \ln (2), \text{MAGIC}, 1.0, C_1..C_3$).
>
> 4. **Archiving Dedicated High-Speed F32 Routines (Future Larger FPGA Path):**
>    - The current high-speed single-cycle Booth-multiplier implementations (`exp2_f32.asm`, `log2_f32.asm`,
       `pow_f32.asm`, `trig_f32.asm`) will be preserved in standalone archive files (e.g.,
       `fpu_emu/asm/archived_fast_f32/` or `*_fast.asm`).
    >    - They will **NOT** be `.include`d in `ucode.asm` / `ucode_f64.asm`, preserving the strict $\le 1,536$-word
           footprint for the MachXO2-2000.
    >    - If the project later transitions to a larger FPGA (such as the Lattice MachXO3 or ECP5 with additional EBRs),
           these fast dedicated routines (~45 cycles) can be swapped back in directly to regain wire-speed 32-bit
           transcendental execution without re-engineering.
>
> **Projected Net Savings:** **~276 microcode words** saved ($315 \to 39$ words across the 4 files), reducing total microcode from **1,563 words down to ~1,287 words** (well under the 1,536 limit with ~249 words of headroom).

### Active Implementation Plan: F32 $\to$ F64 $\to$ F32 Delegation & 100% On-Chip Architecture

#### Phase 1: Archive & Delegation Primitives
- [x] **Step 1: Archive Dedicated Fast F32 Assembly**
  - Created directory `fpu_emu/asm/archive/`.
  - Copied `exp2_f32.asm`, `log2_f32.asm`, `pow_f32.asm`, and `trig_f32.asm` into `fpu_emu/asm/archive/`.
  - Safely preserved in source control without being included in current microcode.
- [x] **Step 2: Expose `CONV_F32_F64_CORE` and `CONV_F64_F32_CORE` Subroutines**
  - In `conv_f32_f64.asm`: Split `USER_CONV_F32_F64` to call a new `CONV_F32_F64_CORE` subroutine that takes float32 in `AL`, returns float64 in `AX`, and ends with `RET`.
  - In `conv_f64_f32.asm`: Split `USER_CONV_F64_F32` to call a new `CONV_F64_F32_CORE` subroutine that takes float64 in `AX`, returns float32 in `AL` (preserving `OVERFLOW`/`UNDERFLOW` flags), and ends with `RET`.
  - Ran unit & integration test suites (92 conversion tests, 2,183 total tests all passed).
- [x] **Step 3: Expose `TRIG_F64_CORE` and `POW_F64_CORE` Callable Subroutines**
  - In `trig_f64.asm`: Refactored common exit points to execute `RET` with result in `AX`, leaving `USER_SIN_F64`, `USER_COS_F64`, and `USER_TAN_F64` to do `CALL TRIG_F64_CORE; HALT AX`.
  - In `pow_f64.asm`: Extracted `POW_F64_CORE` (taking base in `AX` and exponent in `BX`, returning `AX` via `RET`).
  - Ran 64-bit trigonometric and power tests (167 tests passed, 2,183 total tests passed).

#### Phase 2: Implement F32 Delegation Wrappers
- [x] **Step 4: Implement Delegation Wrapper in `exp2_f32.asm`**
  - Replaced the 56-word Horner algorithm with the delegation wrapper calling `CONV_F32_F64_CORE` $\to$ `EXP2_F64_CORE` $\to$ `CONV_F64_F32_CORE`.
  - Updated hardware models (`UpcAdder`, `registers.py`, `control_block.py` call stack, `dispatcher.py`) and budget validation in `micro_code.py` to 11-bit UPC (1,536-word / 6-EBR Code ROM limit).
  - Verified all 35 `exp2_f32` tests and edge cases pass, and full test suite (2,183 tests) passes with 0 regressions.
- [x] **Step 5: Implement Delegation Wrapper in `log2_f32.asm`**
  - Replaced the 81-word odd-series algorithm with the delegation wrapper calling `CONV_F32_F64_CORE` $\to$ `LOG2_F64_CORE` $\to$ `CONV_F64_F32_CORE`.
  - Microcode total footprint reduced from 1,518 words to **1,447 words** (71 words saved).
  - Verified all 34 `log2_f32` tests, domain error checks, and full 2,183 test suite pass.
- [x] **Step 6: Implement Delegation Wrapper in `pow_f32.asm`**
  - Replaced `USER_POW_F32` with the delegation wrapper: pops both operands, widens to float64, calls `POW_F64_CORE`, narrows back via `CONV_F64_F32_CORE`, and preserves `OVERFLOW` on $0^\text{neg}$.
  - Microcode total footprint reduced from 1,447 words to **1,433 words** (14 words saved).
  - Verified all 39 `pow_f32` tests pass, 247 power/log/exp integration tests pass, and full 2,183 test suite passes with 0 regressions.
- [ ] **Step 7: Implement Delegation Wrapper in `trig_f32.asm`**
  - Replace the 144-word `trig_f32.asm` with thin dispatchers for `USER_SIN_F32`, `USER_COS_F32`, and `USER_TAN_F32` that load `CL` (0, 1, 2) and call `CONV_F32_F64_CORE` $\to$ `TRIG_F64_CORE` $\to$ `CONV_F64_F32_CORE` $\to$ `HALT AL`.
  - Verify all single-precision `sin`, `cos`, and `tan` test suites pass.

#### Phase 3: Table Retirement & Unified Microcode Verification
- [ ] **Step 8: Retire Obsolete `CHEB` Table**
  - Remove the 128-word `CHEB` definition from `fpu_const_map.py` and `build_flash.py`.
  - Verify no lingering references remain.
- [ ] **Step 9: Microcode Reassembly & Verification**
  - Reassemble unified microcode and verify that total microcode drops from **1,563 words to ~1,287 words** (saving ~276 words and well within the 1,536 limit).
  - Run the full test suite (2,183+ tests) to confirm all operations pass.

#### Phase 4: Hardware Memory, Flash Packaging & Microcode Execution Refactor
- [ ] **Step 10: Update `hardware/memory.py` for 8-EBR Layout**
  - Reconfigure `Memory` in `fpu_emu/hardware/memory.py`:
    - EBR 0..5: 1,536 words $\times$ 32-bit Code ROM (`readonly=True`).
    - EBR 6..7: 512 words $\times$ 32-bit Data RAM (`readonly=False`).
- [ ] **Step 11: Update `build_flash.py` for 8 KB Image and 6 KB / 2 KB Split**
  - Generate unified 8 KB binary with exact byte-for-byte order matching EBR layout (EBR 0..5 = 6 KB Code ROM, EBR 6..7 = 2 KB Data RAM) for the bootloader.
  - Automatically produce split outputs: 6 KB Code ROM binary and 2 KB Data RAM binary.
- [ ] **Step 12: Convert `micro_code.py` to Fetch from Hardware Memory**
  - Refactor `fpu_emu/micro_code.py` to decode and read micro-instructions from `Memory` rather than importing them directly from `ucode.py` (detailed breakdown to follow).

### 5. Hardware Simulation & Verilog RTL

- [ ] **Host Interface Simulation**:
    - Combinatorial Z80 SRAM memory mapping/decoding and strobe qualification model.
    - Autonomous SPI Flash bootloader copy simulation.
- [ ] **Verilog Implementation**:
    - Modular Verilog RTL corresponding to V2 functional blocks, MUXes, AND walls, and write-back registers.
    - Self-checking Verilog testbenches with `$fatal` assertions on errors.
    - Synthesis for Lattice MachXO2 (`LCMXO2-2000HC-4TG100C`) and timing verification at 80 MHz.

## Appendix: Microcode Optimization & Footprint Reduction Analysis (Saving $\ge 250$ Words)

To fit all microcode within the 1,536-word limit of EBR 0–5 (expanding down from the initial 1,749 baseline in
`ucode_f64.asm` to $\le 1,536$ words), the following optimization strategies have been analyzed across all 58 `.asm`
files in `fpu_emu/asm/`:

### Summary of Identified Savings

| Strategy                                  | Area                                                                   |  Potential Savings   |       Complexity / Risk       |            Status            |
|:------------------------------------------|:-----------------------------------------------------------------------|:--------------------:|:-----------------------------:|:----------------------------:|
| **5. F32 $\to$ F64 $\to$ F32 Delegation** | Delegate `EXP2`, `LOG2`, `POW`, `TRIG` to F64 cores                    |    **~276 words**    |    Low (Assembly wrappers)    |      **NEXT IN QUEUE**       |
| **6. Common Shared Subroutines**          | Deduplicate Quiet NaN / Domain Error / Return 1.0                      |    **~35 words**     |     None (Assembly only)      |       Optional Reserve       |
| **CURRENT PROGRESS**                      | **Initial: 1,749 words $\to$ Current: 1,563 words**                    | **-186 words saved** | **Target: $\le 1,536$ words** |   **Only 27 words to go!**   |
| **PROJECTED AFTER STRATEGY 5**            | **1,563 words $\to$ ~1,287 words**                                     | **-276 words saved** |  **8 EBR On-Chip Goal: MET**  | **~249 words free headroom** |

Adopting Strategies 1, 1b, 2, 3, and 4 has saved **186 words** (bringing microcode down from 1,749 to 1,563 words).
Executing Strategy 5 (F32 $\to$ F64 $\to$ F32 Delegation) will save another **~276 words**, comfortably landing at
**~1,287 words** and achieving 100% on-chip EBR residency (zero external SRAM).


---

### Strategy 3: Hardware Enhancement — `UNPACK` Sets NaN/Infinity Flag (Saves 45–55 words)

Currently, `adder_block.py` only writes `ZERO`, `SIGN`, and `DIFF_SIGN` during `UNPACK`. It does not flag when the
exponent is all 1s (`0xFF` in F32, `0x7FF` in F64).

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

`sqrt_f64`, `log2_f64`, `exp2_f64`, `pow_f64`, `trig_f64`, `div_f64` each independently generate Quiet NaN
`0x7FF80000_00000000`:

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
  Each caller simply executes `JMP COMMON_F64_DOMAIN_ERR` (1 word). **Savings: $(7 - 1) \times 6 = 36$ words.**

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

This can reuse `CONV_INT_F64_COMMON` from `fpu_emu/asm/conv_int_f64.asm`. **Savings: ~12 words.**

---


---

### Actionable Roadmap to Save $\ge 250$ Words

|  Step  | Action                                                           | Files                                                                          |    Savings     |     Cumulative Microcode Size     |      Status       |
|:------:|:-----------------------------------------------------------------|:-------------------------------------------------------------------------------|:--------------:|:---------------------------------:|:-----------------:|
|   —    | *Initial baseline*                                               | `ucode_f64.asm`                                                                |       —        |          **1,749 words**          |     Baseline      |
| **5**  | **F32 $\to$ F64 $\to$ F32 Delegation & 100% On-Chip EBR Budget** | `exp2_f32`, `log2_f32`, `pow_f32`, `trig_f32`, `conv_f32_f64`, `conv_f64_f32`  | **-276 words** | **~1,287 words** *(Fits 8 EBRs!)* | **NEXT IN QUEUE** |
| **6**  | Deduplicate Quiet NaN, domain error, and 1.0 exit trampolines    | `trig_f64`, `exp2_f64`, `log2_f64`, `pow_f64`, `sqrt_f64`                      | **~35 words**  |         **~1,252 words**          | Optional Reserve  |
| **7**  | Make `UNPACK` set `OVERFLOW` flag on NaN/Inf                     | `add_f64`, `mul_f64`, `div_f64`, `trig_f64`, `exp2_f64`, `sqrt_f64`            | **~30 words**  |         **~1,222 words**          | Optional Reserve  |
