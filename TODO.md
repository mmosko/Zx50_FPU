# Zx50 FPU Rev 2 TODO

Target Hardware: Lattice MachXO2 (`LCMXO2-2000HC-4TG100C`) |
Docs: [SystemDesignV2.md](SystemDesignV2.md), [SystemReference.md](SystemReference.md), [ProgrammersGuide.md](ProgrammersGuide.md)

## Current Status

- **Tests:** 2,170 / 2,170 passing (95.02% coverage)
- **Microcode Usage:** **1,274 / 1,536 words** (262 words free in 6-EBR Code ROM budget)

---

## 1. Microcode Footprint Optimizations (Ranked by Opcodes Saved)

| Rank  | Task                                                                                    | Target Files                                                                                                               | Est. Saved | Cumulative Size  |
|:-----:|:----------------------------------------------------------------------------------------|:---------------------------------------------------------------------------------------------------------------------------|:----------:|:----------------:|
|   —   | *Current baseline*                                                                      | `fpu_emu/asm/*.asm`                                                                                                        |     —      | **1,274 words**  |
| **1** | Delegate F32 basic arithmetic (`DIV_F32`, `MUL_F32`, `ADD_F32`, `SUB_F32`) to F64 cores | `div_f32.asm`, `mul_f32.asm`, `add_f32.asm`, `sub_f32.asm`, `align_f32.asm`                                                |  **~75**   |   ~1,199 words   |
| **2** | Unify `SIN_F64`/`COS_F64` quadrant dispatch & compact Cody-Waite reduction              | `trig_f64.asm`                                                                                                             |  **~42**   |   ~1,157 words   |
| **3** | Delegate `FLOOR_F32` & `CEIL_F32` to `ROUND_F64_CORE`                                   | `floor_ceil_f32.asm`, `floor_ceil_f64.asm`                                                                                 |  **~38**   |   ~1,119 words   |
| **4** | Delegate `CONV_F32_I32` to `CONV_F64_I64_CORE` with 32-bit clamp                        | `conv_f32_i32.asm`, `conv_f64_i64.asm`                                                                                     |  **~32**   |   ~1,087 words   |
| **5** | Inline single-caller `*_CORE` wrappers & drop redundant `TRIG_F32` special check        | `exp2_f32.asm`, `log2_f32.asm`, `pow_f32.asm`, `sqrt_f32.asm`, `trig_f32.asm`, `sub_f32.asm`, `mul_f32.asm`, `div_f32.asm` |  **~24**   |   ~1,063 words   |
| **6** | Extract shared `CONV_U32_F64_CORE` / `CONV_I32_F64_CORE` subroutine                     | `conv_int_f64.asm`, `trig_f64.asm`, `exp2_f64.asm`, `log2_f64.asm`                                                         |  **~16**   |   ~1,047 words   |
| **7** | Set `StatusFlag.OVERFLOW` on `EA == max_exp` during hardware `UNPACK`                   | `adder_block.py`, `trig_f64.asm`, `exp2_f64.asm`, `log2_f64.asm`, `sqrt_f64.asm`, `conv_f32_f64.asm`, `conv_f64_f32.asm`   |  **~15**   | **~1,032 words** |

### Task Checklist

- [ ] **Rank 1 (~75 opcodes): Delegate F32 Basic Math to F64 Cores**
    - [ ] Replace `DIV_F32` with `POP_TWO_32` $\to$ `CONV_F32_F64_CORE` $\to$ `DIV_F64_CORE` $\to$ `CONV_F64_F32_CORE`
      (~22 opcodes saved standalone).
    - [ ] Replace `MUL_F32`, `ADD_F32`, `SUB_F32` with F64 delegation wrappers and remove `align_f32.asm` (~53
      additional opcodes saved).
- [ ] **Rank 2 (~42 opcodes): Unify `TRIG_F64` Quadrant Dispatch & Cody-Waite Reduction**
    - [ ] Compute effective quadrant `q_eff = (k + is_cos) & 3` to share polynomial selection (`q_eff & 1`) and sign
      negation (`q_eff & 2`) between `SIN_F64` and `COS_F64` (~26 opcodes).
    - [ ] Replace 32-bit `LDC BL` + `LDC BH` pairs with 64-bit `LDC BX` and fold the 3 Cody-Waite subtraction stages
      into a loop/subroutine (~16 opcodes).
- [ ] **Rank 3 (~38 opcodes): Delegate `FLOOR_F32` & `CEIL_F32` to `ROUND_F64_CORE`**
    - [ ] Extract callable `ROUND_F64_CORE` in `floor_ceil_f64.asm`.
    - [ ] Replace `floor_ceil_f32.asm` body with `POP_ONE_32` $\to$ `CONV_F32_F64_CORE` $\to$ `ROUND_F64_CORE` $\to$
      `CONV_F64_F32_CORE` $\to$ `HALT AL`.
- [ ] **Rank 4 (~32 opcodes): Delegate `CONV_F32_I32` to `CONV_F64_I64_CORE`**
    - [ ] Extract callable `CONV_F64_I64_CORE` in `conv_f64_i64.asm`.
    - [ ] Implement `USER_CONV_F32_I32` via `CONV_F32_F64_CORE` $\to$ `CONV_F64_I64_CORE` followed by 32-bit signed
      range check and clamp.
- [ ] **Rank 5 (~24 opcodes): Inline Single-Caller `*_CORE` Wrappers & Clean Up `TRIG_F32`**
    - [ ] Inline `EXP2_CORE`, `LOG2_CORE`, `POW_F32_CORE`, `SQRT_F32_CORE`, `SUB_F32_CORE`, `MUL_F32_CORE`,
      `DIV_F32_CORE` into their `USER_*` entry points (~15 opcodes).
    - [ ] Remove duplicate pre-conversion NaN/Inf check in `trig_f32.asm` and delegate special handling to
      `TRIG_F64_CORE` (~9 opcodes).
- [ ] **Rank 6 (~16 opcodes): Shared Integer-to-Float64 Conversion Subroutine**
    - [ ] Add `CONV_U32_F64_CORE` and `CONV_I32_F64_CORE` in `conv_int_f64.asm`.
    - [ ] Replace inline `AL -> float64(AX)` sequences in `trig_f64.asm`, `exp2_f64.asm`, and `log2_f64.asm`.
- [ ] **Rank 7 (~15 opcodes): Hardware `UNPACK` NaN/Infinity Flag**
    - [ ] Assert `StatusFlag.OVERFLOW` in `AdderBlock._unpack` when `exp == 0xFF` (F32) or `exp == 0x7FF` (F64).
    - [ ] Replace `CMP EA, 2047` / `CMP EA, 255` and manual exponent extraction in float routines with
      `JNZ OVERFLOW, .special`.

---

## 2. Opcode Jump Table & Entry Point Compaction (Saves 192 Jump Table Entries / 32 LUT4s)

- [ ] **Invalid Opcode Trap at `.org 0x0000`**
    - [ ] Add `TRAP_INVALID_OPCODE: SET ERR, 1; HALT` at microcode address `0x0000`.
    - [ ] Map all unassigned `UserOpcode` values to `0x000`.
- [ ] **Entry Point Bitwidth Compaction (`fpu_asm --opt-entry`)**
    - [ ] Partition assembled microcode into entry preambles (`0x000..0x0FF`) and execution bodies (`0x100+`) so jump
      table targets fit in 8 bits (`[7:0]`).
- [ ] **4-Zone `UserOpcode` Encoding Reorganization**
    - [ ] **Zone 0 (`0x00..0x3F`, `0b00xx_yyyy`)**: Parameterized ops (`CP_MEMx_TOS`, `CP_TOS_MEMx`, `PUSH_CONST_32`,
      `PUSH_CONST_64`) using `opcode[3:0]` $\to$ `reg_c` and a 4-entry mux.
    - [ ] **Zone 1 (`0x40..0x7F`, `0b01xx_xxxx`)**: Hardware control ops (`CLEAR_STACK`, `RESET`, `SET_BATCH`,
      `SET_IMMEDIATE`, `SET_BLOCKING`, `SET_NONBLOCKING`, `EXEC_BATCH`, `PUSH_STACK`).
    - [ ] **Zone 2 (`0x80..0xBF`, `0b10zz_zzzz`)**: Sequential computational microcode indexed by a $64 \times 8$-bit
      Distributed ROM.
    - [ ] **Zone 3 (`0xC0..0xFF`, `0b11xx_xxxx`)**: Reserved / invalid opcodes trapping to `0x000`.
- [ ] **Jump Table Artifact Generation (`tools/build_flash.py`)**
    - [ ] Emit compact jump table defines in `src/fpu_rom_map.vh`.
    - [ ] Emit 64-entry simulation ROM image `sim/opcode_table.hex`.
    - [ ] Emit updated `USER_OPCODE_MAP` in `fpu_emu/rom/fpu_rom_map.py` and update `Dispatcher`.

---

## 3. Verilog RTL & Synthesis

- [ ] **Datapath & Control Modules (`src/`)**
    - [ ] Implement V2 functional blocks (`adder_block`, `shifter_block`, `logic_block`, `memory_block`,
      `control_block`).
    - [ ] Implement register file, `HA`/`HB`/`LA`/`LB` input MUXes, AND walls, and write-back mux.
    - [ ] Implement Z80 host bus interface, hardware control opcodes, and autonomous SPI flash $\to$ EBR bootloader
      directly in Verilog.
- [ ] **Verification & Synthesis (`sim/`, `syn/`)**
    - [ ] Create self-checking Verilog testbenches for each module and top-level integration (using `$fatal` on
      assertion failure).
    - [ ] Synthesize for Lattice MachXO2 (`LCMXO2-2000HC-4TG100C`) and verify resource utilization ($\le 7$ EBRs) and 80
      MHz timing closure.
