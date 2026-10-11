# Zx50 FPU Rev 2 Development Roadmap

Target Hardware: Lattice MachXO2 FPGA on `boards/zx50_cpu_RevC4` (host: Zilog Z80 @ 10 MHz)  
Architecture Specifications: [SystemDesignV2.md](SystemDesignV2.md) & [SystemReference.md](SystemReference.md)  
Programmer's Guide: [ProgrammersGuide.md](ProgrammersGuide.md)

---

## Current Status & Capacity

- **Test Suite Status:** 100% pass rate (**1,245 / 1,245 tests passing**).
- **Microcode Capacity:** **899 / 1,024 words used** (**125 instruction words of headroom remaining**).
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
- [ ] Implement `CONV_U64_F64` (`0xC5`): Unsigned 64-bit uint to IEEE-754 double float (net $0$ bytes on stack).
- [ ] Implement `CONV_I64_F64` (`0xCE`): Signed 64-bit int to IEEE-754 double float (net $0$ bytes on stack).
- [ ] Implement `CONV_F64_I64` (`0xCF`): IEEE-754 double float to signed 64-bit int (truncate toward zero, $V=1$ on range overflow).

### 3. Floating-Point Conversions & Utilities
- [ ] Implement `CONV_F32_F64` (`0xC9`): Expand IEEE single float to double float (net $+4$ bytes on stack).
- [ ] Implement `CONV_F64_F32` (`0xCB`): Narrow IEEE double float to single float (net $-4$ bytes on stack, $V=1$ on exponent overflow, $U=1$ on underflow).
- [x] Implement `FLOOR_F32` (`0x61`): Mathematical floor toward $-\infty$.
- [ ] Implement `FLOOR_F64` (`0x63`): Mathematical floor toward $-\infty$.
- [x] Implement `CEIL_F32` (`0x69`): Mathematical ceiling toward $+\infty$.
- [ ] Implement `CEIL_F64` (`0x6B`): Mathematical ceiling toward $+\infty$.

### 4. 64-Bit Floating-Point Arithmetic & Transcendentals (Estimated ~650–855 Microcode Instructions)
- [ ] Implement `ADD_F64` (`0x03`): 64-bit IEEE-754 double-precision addition (~70–85 words with `SUB_F64`, `align_f64`, `normalize_f64`).
- [ ] Implement `SUB_F64` (`0x0B`): 64-bit IEEE-754 double-precision subtraction (shares datapath with `ADD_F64`).
- [ ] Implement `MUL_F64` (`0x13`): 64-bit IEEE-754 double-precision multiplication using cross-terms via hardware Booth multiplier (~45–60 words).
- [ ] Implement `DIV_F64` (`0x1B`): 64-bit IEEE-754 double-precision division via 54-iteration non-restoring loop (~40–55 words).
- [ ] Implement `SQRT_F64` (`0x23`): 64-bit IEEE-754 double-precision square root via digit-by-digit binary loop (~50–65 words).
- [ ] Implement `POW_F64` (`0x2B`): 64-bit IEEE-754 double-precision power ($x^y$) via $2^{y \log_2 x}$ dispatch (~35–50 words).
- [ ] Implement `LOG2_F64` (`0x33`): 64-bit base-2 logarithm via degree 7–8 Chebyshev polynomial (~120–160 words).
- [ ] Implement `EXP2_F64` (`0x3B`): 64-bit base-2 exponential ($2^x$) via degree 7–8 polynomial (~90–120 words).
- [ ] Implement 64-bit CORDIC trigonometrics: `SIN_F64` (`0x73`), `COS_F64` (`0x7B`), `TAN_F64` (`0x83`) (~200–260 words).

#### Microcode ROM Capacity & Scaling Analysis for 64-Bit Suite
| Functional Group | Operations | Estimated Instructions |
| :--- | :--- | :---: |
| **Basic 64-Bit Arithmetic** | `ADD_F64`, `SUB_F64`, `MUL_F64`, `DIV_F64` | **~155 – 200** |
| **Square Root** | `SQRT_F64` | **~50 – 65** |
| **Transcendentals** | `LOG2_F64`, `EXP2_F64`, `POW_F64` | **~245 – 330** |
| **CORDIC Trigonometrics** | `SIN_F64`, `COS_F64`, `TAN_F64` | **~200 – 260** |
| **TOTAL FOR COMPLETE 64-BIT SUITE** | | **~650 – 855** |

> [!NOTE]
> **Microcode ROM Architecture Requirement:**
> Current microcode usage is **992 / 1,024 words** (32 words headroom in a single 10-bit UPC address space). Implementing the full 64-bit floating-point and transcendental suite requires expanding microcode capacity:
> - **Option A (Recommended - 2,048 Words):** Expand `UPC` address width from 10 bits (`0x3FF`) to 11 bits (`0x7FF`) by allocating a 2nd EBR block on the Lattice MachXO2-2000 (which has 8 EBR blocks total, with only 1 currently dedicated to microcode).
> - **Option B (Microcode Bank Switching / Overlay):** Add a 1-bit bank register switching two 1,024-word pages (Bank 0: 32-bit & integer operations; Bank 1: 64-bit float operations).
> - **Option C (Staged Implementation):** Implement pure conversions and integer operations within current ROM space via microcode compaction, deferring transcendental/CORDIC 64-bit routines until 2K expansion is enabled.

### 5. Hardware Simulation & Verilog RTL
- [ ] **Host Interface Simulation**:
  - Combinatorial Z80 SRAM memory mapping/decoding and strobe qualification model.
  - Autonomous SPI Flash bootloader copy simulation.
- [ ] **Verilog Implementation**:
  - Modular Verilog RTL corresponding to V2 functional blocks, MUXes, AND walls, and write-back registers.
  - Self-checking Verilog testbenches with `$fatal` assertions on errors.
  - Synthesis for Lattice MachXO2 (`LCMXO2-2000HC-4TG100C`) and timing verification at 80 MHz.
