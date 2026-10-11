# Microcode Instruction Reference Manual

Instruction operand formats are classified by their assembly language view (the number of explicit operands in the
assembly statement, rather than mathematical function arity):

- **Nullary** (0 operands): e.g. `RET`, `NOP`, `HALT`
- **Unary** (1 operand): e.g. `POP AL` such that `AL <- TOS`, `PUSH BL`, `NOT AL`
- **Binary** (2 operands): e.g. `ADD AL, BL` such that `AL <- AL + BL` (with implied `src1 = dst`), `CMP AL, BL`,
  `MOV AL, BL`
- **Ternary** (3 operands): e.g. `ADD AL, BL, DL` such that `AL <- BL + DL`, `LDC AL, CONST, 0x02`

The physical registers are 32-bits each (unless stated otherwise):

- AL and AH (Accumulator / Working registers, 64-bit pair AX)
- BL and BH (Operand / Working registers, 64-bit pair BX)
- CL and CH (General / Working registers, 64-bit pair CX)
- DL and DH (Multiplier / Divider registers, 64-bit pair DX)
- FL and FH (Staging / Working registers, 64-bit pair FX)
- EA (12-bit exponent register)
- EB (12-bit exponent register)
- C (8-bit loop / shift counter, opcode parameter register: automatically latched with user opcode lower nibble
  `opcode & 0x0F` upon dispatch)
- SP (8-bit hardware math stack pointer)
- OSP (5-bit batch operation stack pointer)
- UPC (10-bit microcode program counter, addressing 1,024 words in CODE_ROM)
- STATUS (8-bit status flags register: [7: BSY, 6: ERR, 5: S, 4: C, 3: V, 2: U, 1: D, 0: Z]; refer
  to [ProgrammersGuide.md](ProgrammersGuide.md#2-status-register-status70) for complete bitfield definitions, system vs.
  ALU flag separation, and Z80 polling idioms)

In the assembly, pseudo-registers AX, BX, CX, DX, and FX denote 64-bit operations (e.g., `ADD dst_64, src2_64` such as
`ADD AX, BX`).

The operation arguments may be any of these. We use `IMM` to mean the immediate value in an
instruction, which we treat like its own register (it actually is -- the machine word is broken into
the instruction register and the immediate register).

```text
+---------+----+----+----+----+----+----+----+----+----+----+----+----+----+-----+
| arg     | AL | AH | BL | BH | CL | CH | DL | DH | FL | FH | EA | EB | C  | IMM | 
+---------+----+----+----+----+----+----+----+----+----+----+----+----+----+-----+
| dst     | X  | X  | X  | X  | X  | X  | X  | X  | X  | X  | X  | X  | X  |     |
| src1    | X  | X  | X  | X  | X  | X  | X  | X  | X  | X  | X  | X  | X  | X   |
| src2    | X  | X  | X  | X  | X  | X  | X  | X  | X  | X  | X  | X  | X  | X   |
+---------+----+----+----+----+----+----+----+----+----+----+----+----+----+-----+
|         |   AX    |   BX    |    CX   |    DX   |   FX    |    |    |    |     |
+---------+---------+---------+---------+---------+---------+----+----+----+-----+
| dst_64  |    X    |    X    |     X   |     X   |    X    |    |    |    |     |
| src1_64 |    X    |    X    |     X   |     X   |    X    |    |    |    |     |
| src2_64 |    X    |    X    |     X   |     X   |    X    |    |    |    |     |
+---------+---------+---------+---------+---------+---------+----+----+----+-----+
```

## 1. Summary of the Microcode Instruction Set

The following table summarizes the complete microcode instruction set, organized by functional block and sorted
alphabetically by mnemonic within each block. Blocks sharing physical execution resources and AND-wall logic are
co-located:

- **Arithmetic (`0b000` & `0b001`)**: Shared adder, Booth multiplier, and restoring divider resources.
- **Memory (`0b100` & `0b101`)**: Shared math stack, scratchpad RAM, and shadow status registers.

### Status Flag Notation

- **`X`**: Flag is modified according to the result of the operation.
- **`0`**: Flag is explicitly reset / cleared to 0.
- **`1`**: Flag is explicitly set to 1.
- **`•`**: Flag is unaffected / preserved.
- **`0*` / `X*`**: Flag is conditionally updated on exception traps (e.g. stack overflow/underflow).

### Instruction Set Summary Table

| Block                            | Mnemonic  | Operands                   | W | Clock Cycles |  Opcode (Hex / Bin)  |  BSY  |   ERR   |   S   |   C   |   V   | U | DF | Z | Operation Performed                                                 |
|:---------------------------------|:----------|:---------------------------|:-:|:------------:|:--------------------:|:-----:|:-------:|:-----:|:-----:|:-----:|:-:|:--:|:-:|:--------------------------------------------------------------------|
| **Math**<br>`0b000`<br>`0b001`   | `ADC`     | `dst, src2`                | 0 |      1       | `0x01` (`0b000_001`) |   •   |    •    |   X   |   X   |   X   | • | •  | X | `dst <- dst + src2 + C`                                             |
|                                  | `ADC`     | `dst, src1, src2`          | 0 |      1       | `0x01` (`0b000_001`) |   •   |    •    |   X   |   X   |   X   | • | •  | X | `dst <- src1 + src2 + C`                                            |
|                                  | `ADC`     | `dst_64, src2_64`          | 1 |      2       | `0x01` (`0b000_001`) |   •   |    •    |   X   |   X   |   X   | • | •  | X | `dst_64 <- dst_64 + src2_64 + C` (64-bit)                           |
|                                  | `ADC`     | `dst_64, src1_64, src2_64` | 1 |      2       | `0x01` (`0b000_001`) |   •   |    •    |   X   |   X   |   X   | • | •  | X | `dst_64 <- src1_64 + src2_64 + C` (64-bit)                          |
|                                  | `ADD`     | `dst, src2`                | 0 |      1       | `0x00` (`0b000_000`) |   •   |    •    |   X   |   X   |   X   | • | •  | X | `dst <- dst + src2`                                                 |
|                                  | `ADD`     | `dst, src1, src2`          | 0 |      1       | `0x00` (`0b000_000`) |   •   |    •    |   X   |   X   |   X   | • | •  | X | `dst <- src1 + src2`                                                |
|                                  | `ADD`     | `dst_64, src2_64`          | 1 |      2       | `0x00` (`0b000_000`) |   •   |    •    |   X   |   X   |   X   | • | •  | X | `dst_64 <- dst_64 + src2_64` (64-bit)                               |
|                                  | `ADD`     | `dst_64, src1_64, src2_64` | 1 |      2       | `0x00` (`0b000_000`) |   •   |    •    |   X   |   X   |   X   | • | •  | X | `dst_64 <- src1_64 + src2_64` (64-bit)                              |
|                                  | `CMP`     | `src1, src2`               | 0 |      1       | `0x04` (`0b000_100`) |   •   |    •    |   X   |   X   |   X   | • | •  | X | `src1 - src2` (discards result)                                     |
|                                  | `CMP`     | `src1_64, src2_64`         | 1 |      2       | `0x04` (`0b000_100`) |   •   |    •    |   X   |   X   |   X   | • | •  | X | `src1_64 - src2_64` (64-bit compare)                                |
|                                  | `DIV`     | `dst, src2`                | 0 |      32      | `0x0B` (`0b001_011`) |   •   |    X    |   X   |   0   |   X   | • | •  | X | `dst <- dst / src2, DL <- rem` (ERR & V on div 0)                   |
|                                  | `DIV`     | `dst, src1, src2`          | 0 |      32      | `0x0B` (`0b001_011`) |   •   |    X    |   X   |   0   |   X   | • | •  | X | `dst <- src1 / src2, DL <- rem` (ERR & V on div 0)                  |
|                                  | `DIV`     | `dst_64, src2_64`          | 1 |      64      | `0x0B` (`0b001_011`) |   •   |    X    |   X   |   0   |   X   | • | •  | X | `dst_64 <- dst_64 / src2_64, DX <- rem` (64-bit)                    |
|                                  | `DIV`     | `dst_64, src1_64, src2_64` | 1 |      64      | `0x0B` (`0b001_011`) |   •   |    X    |   X   |   0   |   X   | • | •  | X | `dst_64 <- src1_64 / src2_64, DX <- rem` (64-bit)                   |
|                                  | `DIVU`    | `dst, src2`                | 0 |      32      | `0x0F` (`0b001_111`) |   •   |    X    |   X   |   0   |   X   | • | •  | X | `dst <- dst / src2, DL <- rem` (unsigned, ERR & V on div 0)         |
|                                  | `DIVU`    | `dst, src1, src2`          | 0 |      32      | `0x0F` (`0b001_111`) |   •   |    X    |   X   |   0   |   X   | • | •  | X | `dst <- src1 / src2, DL <- rem` (unsigned, ERR & V on div 0)        |
|                                  | `DIVU`    | `dst_64, src2_64`          | 1 |      64      | `0x0F` (`0b001_111`) |   •   |    X    |   X   |   0   |   X   | • | •  | X | `dst_64 <- dst_64 / src2_64, DX <- rem` (64-bit)                    |
|                                  | `DIVU`    | `dst_64, src1_64, src2_64` | 1 |      64      | `0x0F` (`0b001_111`) |   •   |    X    |   X   |   0   |   X   | • | •  | X | `dst_64 <- src1_64 / src2_64, DX <- rem` (64-bit)                   |
|                                  | `EXP_ADD` | `dst, src2`                | 0 |      1       | `0x05` (`0b000_101`) |   •   |    •    |   X   |   0   |   X   | X | •  | X | `dst <- dst + src2` (12-bit exp; V if > 1023, U if < -1022)         |
|                                  | `EXP_SUB` | `dst, src2`                | 0 |      1       | `0x06` (`0b000_110`) |   •   |    •    |   X   |   0   |   X   | X | •  | X | `dst <- dst - src2` (12-bit exp; V if > 1023, U if < -1022)         |
|                                  | `MUL`     | `dst, src2`                | 0 |      16      | `0x0A` (`0b001_010`) |   •   |    •    |   X   |   0   |   X   | • | •  | X | `dst <- dst * src2` (signed Booth mul)                              |
|                                  | `MUL`     | `dst, src1, src2`          | 0 |      16      | `0x0A` (`0b001_010`) |   •   |    •    |   X   |   0   |   X   | • | •  | X | `dst <- src1 * src2`                                                |
|                                  | `MUL`     | `dst_64, src2_64`          | 1 |      64      | `0x0A` (`0b001_010`) |   •   |    •    |   X   |   0   |   X   | • | •  | X | `dst_64 <- dst_64 * src2_64` (64-bit)                               |
|                                  | `MUL`     | `dst_64, src1_64, src2_64` | 1 |      64      | `0x0A` (`0b001_010`) |   •   |    •    |   X   |   0   |   X   | • | •  | X | `dst_64 <- src1_64 * src2_64` (64-bit)                              |
|                                  | `MULU`    | `dst, src2`                | 0 |      16      | `0x0E` (`0b001_110`) |   •   |    •    |   X   |   0   |   X   | • | •  | X | `{AH, AL} <- dst * src2` (unsigned Booth mul, V if AH != 0)         |
|                                  | `MULU`    | `dst, src1, src2`          | 0 |      16      | `0x0E` (`0b001_110`) |   •   |    •    |   X   |   0   |   X   | • | •  | X | `{AH, AL} <- src1 * src2`                                           |
|                                  | `MULU`    | `dst_64, src2_64`          | 1 |      64      | `0x0E` (`0b001_110`) |   •   |    •    |   X   |   0   |   X   | • | •  | X | `{DX, dst_64} <- dst_64 * src2_64` (64-bit unsigned, V if DX != 0)  |
|                                  | `MULU`    | `dst_64, src1_64, src2_64` | 1 |      64      | `0x0E` (`0b001_110`) |   •   |    •    |   X   |   0   |   X   | • | •  | X | `{DX, dst_64} <- src1_64 * src2_64` (64-bit unsigned, V if DX != 0) |
|                                  | `PACK`    | `dst, src1`                | 0 |      1       | `0x08` (`0b001_000`) |   •   |    •    |   X   |   •   |   X   | X | •  | X | `dst <- pack(sign, exp=src1, mantissa=dst)` (IEEE float)            |
|                                  | `PACK`    | `dst, src1, src2`          | 0 |      1       | `0x08` (`0b001_000`) |   •   |    •    |   X   |   •   |   X   | X | •  | X | `dst <- pack(sign, exp=src1, mantissa=src2)` (IEEE float)           |
|                                  | `PACK`    | `dst_64, src1`             | 1 |      2       | `0x08` (`0b001_000`) |   •   |    •    |   X   |   •   |   X   | X | •  | X | `dst_64 <- pack(sign, exp=src1, mantissa=dst_64)` (IEEE double)     |
|                                  | `PACK`    | `dst_64, src1, src2_64`    | 1 |      2       | `0x08` (`0b001_000`) |   •   |    •    |   X   |   •   |   X   | X | •  | X | `dst_64 <- pack(sign, exp=src1, mantissa=src2_64)` (IEEE double)    |
|                                  | `SBB`     | `dst, src2`                | 0 |      1       | `0x03` (`0b000_011`) |   •   |    •    |   X   |   X   |   X   | • | •  | X | `dst <- dst - src2 - C`                                             |
|                                  | `SBB`     | `dst, src1, src2`          | 0 |      1       | `0x03` (`0b000_011`) |   •   |    •    |   X   |   X   |   X   | • | •  | X | `dst <- src1 - src2 - C`                                            |
|                                  | `SBB`     | `dst_64, src2_64`          | 1 |      2       | `0x03` (`0b000_011`) |   •   |    •    |   X   |   X   |   X   | • | •  | X | `dst_64 <- dst_64 - src2_64 - C` (64-bit)                           |
|                                  | `SBB`     | `dst_64, src1_64, src2_64` | 1 |      2       | `0x03` (`0b000_011`) |   •   |    •    |   X   |   X   |   X   | • | •  | X | `dst_64 <- src1_64 - src2_64 - C` (64-bit)                          |
|                                  | `SUB`     | `dst, src2`                | 0 |      1       | `0x02` (`0b000_010`) |   •   |    •    |   X   |   X   |   X   | • | •  | X | `dst <- dst - src2`                                                 |
|                                  | `SUB`     | `dst, src1, src2`          | 0 |      1       | `0x02` (`0b000_010`) |   •   |    •    |   X   |   X   |   X   | • | •  | X | `dst <- src1 - src2`                                                |
|                                  | `SUB`     | `dst_64, src2_64`          | 1 |      2       | `0x02` (`0b000_010`) |   •   |    •    |   X   |   X   |   X   | • | •  | X | `dst_64 <- dst_64 - src2_64` (64-bit)                               |
|                                  | `SUB`     | `dst_64, src1_64, src2_64` | 1 |      2       | `0x02` (`0b000_010`) |   •   |    •    |   X   |   X   |   X   | • | •  | X | `dst_64 <- src1_64 - src2_64` (64-bit)                              |
|                                  | `UNPACK`  | `dst, src1`                | 0 |      1       | `0x09` (`0b001_001`) |   •   |    •    |   X   |   •   |   •   | • | X  | X | `src1 <- dst.exp, dst <- dst.mantissa`; DF=`sA ^ sB`                |
|                                  | `UNPACK`  | `dst, src1, src2`          | 0 |      1       | `0x09` (`0b001_001`) |   •   |    •    |   X   |   •   |   •   | • | X  | X | `src1 <- src2.exp, dst <- src2.mantissa`; DF=`sA ^ sB`              |
|                                  | `UNPACK`  | `dst_64, src1`             | 1 |      2       | `0x09` (`0b001_001`) |   •   |    •    |   X   |   •   |   •   | • | X  | X | `src1 <- dst_64.exp, dst_64 <- dst_64.mantissa` (64-bit double)     |
|                                  | `UNPACK`  | `dst_64, src1, src2_64`    | 1 |      2       | `0x09` (`0b001_001`) |   •   |    •    |   X   |   •   |   •   | • | X  | X | `src1 <- src2_64.exp, dst_64 <- src2_64.mantissa` (64-bit double)   |
| **Logic**<br>`0b010`             | `AND`     | `dst, src2`                | 0 |      1       | `0x10` (`0b010_000`) |   •   |    •    |   X   | **0** | **0** | • | •  | X | `dst <- dst & src2` (**clears C and V**)                            |
|                                  | `AND`     | `dst, src1, src2`          | 0 |      1       | `0x10` (`0b010_000`) |   •   |    •    |   X   | **0** | **0** | • | •  | X | `dst <- src1 & src2` (**clears C and V**)                           |
|                                  | `AND`     | `dst_64, src2_64`          | 1 |      2       | `0x10` (`0b010_000`) |   •   |    •    |   X   | **0** | **0** | • | •  | X | `dst_64 <- dst_64 & src2_64` (**clears C and V**)                   |
|                                  | `AND`     | `dst_64, src1_64, src2_64` | 1 |      2       | `0x10` (`0b010_000`) |   •   |    •    |   X   | **0** | **0** | • | •  | X | `dst_64 <- src1_64 & src2_64` (**clears C and V**)                  |
|                                  | `FABS`    | `dst`                      | 0 |      1       | `0x13` (`0b010_011`) |   •   |    •    |   0   |   •   |   •   | • | •  | X | `dst[31] <- 0` (clears S)                                           |
|                                  | `FABS`    | `dst, src1`                | 0 |      1       | `0x13` (`0b010_011`) |   •   |    •    |   0   |   •   |   •   | • | •  | X | `dst <- abs(src1)` (clears S, src1 unmodified)                     |
|                                  | `FABS`    | `dst_64`                   | 1 |      2       | `0x13` (`0b010_011`) |   •   |    •    |   0   |   •   |   •   | • | •  | X | `dst_64_H[31] <- 0` (clears S)                                      |
|                                  | `FABS`    | `dst_64, src1_64`          | 1 |      2       | `0x13` (`0b010_011`) |   •   |    •    |   0   |   •   |   •   | • | •  | X | `dst_64 <- abs(src1_64)` (clears S, src1_64 unmodified)            |
|                                  | `FCHS`    | `dst`                      | 0 |      1       | `0x14` (`0b010_100`) |   •   |    •    |   X   |   •   |   •   | • | •  | X | `dst[31] <- ~dst[31]` (inverts S)                                   |
|                                  | `FCHS`    | `dst, src1`                | 0 |      1       | `0x14` (`0b010_100`) |   •   |    •    |   X   |   •   |   •   | • | •  | X | `dst <- neg(src1)` (inverts S, src1 unmodified)                     |
|                                  | `FCHS`    | `dst_64`                   | 1 |      2       | `0x14` (`0b010_100`) |   •   |    •    |   X   |   •   |   •   | • | •  | X | `dst_64_H[31] <- ~dst_64_H[31]` (inverts S)                         |
|                                  | `FCHS`    | `dst_64, src1_64`          | 1 |      2       | `0x14` (`0b010_100`) |   •   |    •    |   X   |   •   |   •   | • | •  | X | `dst_64 <- neg(src1_64)` (inverts S, src1_64 unmodified)            |
|                                  | `NOT`     | `dst`                      | 0 |      1       | `0x15` (`0b010_101`) |   •   |    •    |   X   | **0** | **0** | • | •  | X | `dst <- ~dst` (**clears C and V**)                                  |
|                                  | `NOT`     | `dst, src1`                | 0 |      1       | `0x15` (`0b010_101`) |   •   |    •    |   X   | **0** | **0** | • | •  | X | `dst <- ~src1` (**clears C and V**, src1 unmodified)                |
|                                  | `NOT`     | `dst_64`                   | 1 |      2       | `0x15` (`0b010_101`) |   •   |    •    |   X   | **0** | **0** | • | •  | X | `dst_64 <- ~dst_64` (**clears C and V**)                            |
|                                  | `NOT`     | `dst_64, src1_64`          | 1 |      2       | `0x15` (`0b010_101`) |   •   |    •    |   X   | **0** | **0** | • | •  | X | `dst_64 <- ~src1_64` (**clears C and V**, src1_64 unmodified)       |
|                                  | `OR`      | `dst, src2`                | 0 |      1       | `0x11` (`0b010_001`) |   •   |    •    |   X   | **0** | **0** | • | •  | X | `dst <- dst \| src2` (**clears C and V**)                           |
|                                  | `OR`      | `dst, src1, src2`          | 0 |      1       | `0x11` (`0b010_001`) |   •   |    •    |   X   | **0** | **0** | • | •  | X | `dst <- src1 \| src2` (**clears C and V**)                          |
|                                  | `OR`      | `dst_64, src2_64`          | 1 |      2       | `0x11` (`0b010_001`) |   •   |    •    |   X   | **0** | **0** | • | •  | X | `dst_64 <- dst_64 \| src2_64` (**clears C and V**)                  |
|                                  | `OR`      | `dst_64, src1_64, src2_64` | 1 |      2       | `0x11` (`0b010_001`) |   •   |    •    |   X   | **0** | **0** | • | •  | X | `dst_64 <- src1_64 \| src2_64` (**clears C and V**)                 |
|                                  | `XOR`     | `dst, src2`                | 0 |      1       | `0x12` (`0b010_010`) |   •   |    •    |   X   | **0** | **0** | • | •  | X | `dst <- dst ^ src2` (**clears C and V**)                            |
|                                  | `XOR`     | `dst, src1, src2`          | 0 |      1       | `0x12` (`0b010_010`) |   •   |    •    |   X   | **0** | **0** | • | •  | X | `dst <- src1 ^ src2` (**clears C and V**)                           |
|                                  | `XOR`     | `dst_64, src2_64`          | 1 |      2       | `0x12` (`0b010_010`) |   •   |    •    |   X   | **0** | **0** | • | •  | X | `dst_64 <- dst_64 ^ src2_64` (**clears C and V**)                   |
|                                  | `XOR`     | `dst_64, src1_64, src2_64` | 1 |      2       | `0x12` (`0b010_010`) |   •   |    •    |   X   | **0** | **0** | • | •  | X | `dst_64 <- src1_64 ^ src2_64` (**clears C and V**)                  |
| **Control**<br>`0b011`           | `CALL`    | `addr`                     | 0 |      2       | `0x1C` (`0b011_100`) |   •   |    •    |   •   |   •   |   •   | • | •  | • | `CALL_STACK[CSP++] <- UPC + 1; UPC <- addr`                         |
|                                  | `DJNZ`    | `addr`                     | 0 |    2 / 1     | `0x1B` (`0b011_011`) |   •   |    •    |   •   |   •   |   •   | • | •  | X | `C <- C - 1; if (C != 0) UPC <- addr` (sets ZF)                     |
|                                  | `HALT`    | —                          | 0 |      1       | `0x1F` (`0b011_111`) | **0** |    •    |   •   |   •   |   •   | • | •  | • | `STATUS.BSY <- 0; pulse EXEC_DONE`                                  |
|                                  | `JMP`     | `addr`                     | 0 |      2       | `0x18` (`0b011_000`) |   •   |    •    |   •   |   •   |   •   | • | •  | • | `UPC <- addr` (unconditional jump)                                  |
|                                  | `JNZ`     | `[flag,] addr`             | 0 |    2 / 1     | `0x19` (`0b011_001`) |   •   |    •    |   •   |   •   |   •   | • | •  | • | `if (!cond) UPC <- addr` (default: `!ZF`)                           |
|                                  | `JZ`      | `[flag,] addr`             | 0 |    2 / 1     | `0x1A` (`0b011_010`) |   •   |    •    |   •   |   •   |   •   | • | •  | • | `if (cond) UPC <- addr` (default: `ZF`)                             |
|                                  | `NOP`     | —                          | 0 |      1       | `0x1E` (`0b011_110`) |   •   |    •    |   •   |   •   |   •   | • | •  | • | No operation (pipeline bubble)                                      |
|                                  | `RET`     | —                          | 0 |      2       | `0x1D` (`0b011_101`) |   •   |    •    |   •   |   •   |   •   | • | •  | • | `UPC <- CALL_STACK[--CSP]`                                          |
| **Memory**<br>`0b100`<br>`0b101` | `LD`      | `dst, addr`                | 0 |      1       | `0x24` (`0b100_100`) |   •   |    •    |   •   |   •   |   •   | • | •  | • | `dst <- DATA_RAM[0x080 \| (addr & 0x3F)]`                           |
|                                  | `LD`      | `dst, [src1]`              | 0 |      1       | `0x24` (`0b100_100`) |   •   |    •    |   •   |   •   |   •   | • | •  | • | `dst <- DATA_RAM[0x080 \| (src1 & 0x3F)]`                           |
|                                  | `LD`      | `dst_64, addr`             | 1 |      2       | `0x24` (`0b100_100`) |   •   |    •    |   •   |   •   |   •   | • | •  | • | 64-bit load from scratchpad                                         |
|                                  | `LDC`     | `dst, tbl, addr`           | 0 |      1       | `0x22` (`0b100_010`) |   •   |    •    |   •   |   •   |   •   | • | •  | • | `dst <- DATA_RAM[TBL_BASE \| addr]` (constant/LUT)                  |
|                                  | `LDC`     | `dst_64, tbl, addr`        | 1 |      2       | `0x22` (`0b100_010`) |   •   |    •    |   •   |   •   |   •   | • | •  | • | 64-bit load from constant/LUT table                                 |
|                                  | `LDI`     | `dst, imm`                 | 0 |      1       | `0x23` (`0b100_011`) |   •   |    •    |   •   |   •   |   •   | • | •  | • | `dst <- imm` (zero-extended 10-bit imm)                             |
|                                  | `LDI`     | `dst_64, imm`              | 1 |      2       | `0x23` (`0b100_011`) |   •   |    •    |   •   |   •   |   •   | • | •  | • | `dst_64_L <- imm; dst_64_H <- 0`                                    |
|                                  | `LDI`     | `flag, val`                | 0 |      1       | `0x23` (`0b100_011`) |   X   |    X    |   X   |   X   |   X   | X | X  | X | `STATUS[flag] <- val & 1` (updates selected flag)                   |
|                                  | `LDU`     | `dst, addr`                | 0 |      1       | `0x28` (`0b101_000`) |   •   |    •    |   •   |   •   |   •   | • | •  | • | `dst <- DATA_RAM[0x0C0 \| (addr & 0x3F)]` (user RAM)                |
|                                  | `LDU`     | `dst_64, addr`             | 1 |      2       | `0x28` (`0b101_000`) |   •   |    •    |   •   |   •   |   •   | • | •  | • | 64-bit load from user scratchpad                                    |
|                                  | `MOV`     | `dst, src2`                | 0 |      1       | `0x26` (`0b100_110`) |   •   |    •    |   •   |   •   |   •   | • | •  | • | `dst <- src2`                                                       |
|                                  | `MOV`     | `dst_64, src2_64`          | 1 |      2       | `0x26` (`0b100_110`) |   •   |    •    |   •   |   •   |   •   | • | •  | • | `dst_64 <- src2_64` (64-bit copy)                                   |
|                                  | `POP`     | `dst`                      | 0 |      1       | `0x21` (`0b100_001`) |   •   | **X\*** |   •   |   •   |   •   | • | •  | • | `dst <- TOS, SP <- SP - 1` (\*sets ERR on underflow)                |
|                                  | `POP`     | `dst_64`                   | 1 |      2       | `0x21` (`0b100_001`) |   •   | **X\*** |   •   |   •   |   •   | • | •  | • | `dst_64 <- TOS, SP <- SP - 2` (\*sets ERR on underflow)             |
|                                  | `PUSH`    | `src2`                     | 0 |      1       | `0x20` (`0b100_000`) |   •   | **X\*** |   •   |   •   |   •   | • | •  | • | `TOS <- src2, SP <- SP + 1` (\*sets ERR on overflow)                |
|                                  | `PUSH`    | `src2_64`                  | 1 |      2       | `0x20` (`0b100_000`) |   •   | **X\*** |   •   |   •   |   •   | • | •  | • | `TOS <- src2_64, SP <- SP + 2` (\*sets ERR on overflow)             |
|                                  | `SRES`    | —                          | 0 |      1       | `0x2F` (`0b101_111`) |   •   |    •    |   X   |   X   |   X   | X | X  | X | `STATUS <- SHADOW_STATUS` (restores ALU flags with mask `0x3F`)     |
|                                  | `SSAV`    | —                          | 0 |      1       | `0x2E` (`0b101_110`) |   •   |    •    |   •   |   •   |   •   | • | •  | • | `SHADOW_STATUS <- STATUS` (saves flags)                             |
|                                  | `STO`     | `addr, src2`               | 0 |      1       | `0x25` (`0b100_101`) |   •   |    •    |   •   |   •   |   •   | • | •  | • | `DATA_RAM[0x080 \| (addr & 0x3F)] <- src2`                          |
|                                  | `STO`     | `[src1], src2`             | 0 |      1       | `0x25` (`0b100_101`) |   •   |    •    |   •   |   •   |   •   | • | •  | • | `DATA_RAM[0x080 \| (src1 & 0x3F)] <- src2`                          |
|                                  | `STO`     | `addr, src2_64`            | 1 |      2       | `0x25` (`0b100_101`) |   •   |    •    |   •   |   •   |   •   | • | •  | • | 64-bit store to scratchpad                                          |
|                                  | `STU`     | `addr, src2`               | 0 |      1       | `0x29` (`0b101_001`) |   •   |    •    |   •   |   •   |   •   | • | •  | • | `DATA_RAM[0x0C0 \| (addr & 0x3F)] <- src2` (user RAM)               |
|                                  | `STU`     | `addr, src2_64`            | 1 |      2       | `0x29` (`0b101_001`) |   •   |    •    |   •   |   •   |   •   | • | •  | • | 64-bit store to user scratchpad                                     |
|                                  | `SWAP`    | `dst, src2`                | 0 |      2       | `0x27` (`0b100_111`) |   •   |    •    |   •   |   •   |   •   | • | •  | • | `dst <-> src2` (via staging register `F_`)                          |
|                                  | `SWAP`    | `dst_64, src2_64`          | 1 |      4       | `0x27` (`0b100_111`) |   •   |    •    |   •   |   •   |   •   | • | •  | • | 64-bit exchange `dst_64 <-> src2_64`                                |
| **Shifter**<br>`0b110`           | `ASL`     | `dst[, src1]`              | 0 |      1       | `0x32` (`0b110_010`) |   •   |    •    |   X   |   X   |   X   | • | •  | X | `dst <- dst << (src1 \| C)` (V set if sign changed)                 |
|                                  | `ASL`     | `dst_64[, src1]`           | 1 |      2       | `0x32` (`0b110_010`) |   •   |    •    |   X   |   X   |   X   | • | •  | X | 64-bit arithmetic shift left                                        |
|                                  | `ASR`     | `dst[, src1]`              | 0 |      1       | `0x33` (`0b110_011`) |   •   |    •    |   X   |   X   |   •   | • | •  | X | `dst <- dst >> (src1 \| C)` (sign-extended)                         |
|                                  | `ASR`     | `dst_64[, src1]`           | 1 |      2       | `0x33` (`0b110_011`) |   •   |    •    |   X   |   X   |   •   | • | •  | X | 64-bit arithmetic shift right                                       |
|                                  | `LSL`     | `dst[, src1]`              | 0 |      1       | `0x30` (`0b110_000`) |   •   |    •    |   X   |   X   |   •   | • | •  | X | `dst <- dst << (src1 \| C)` (C = last bit out)                      |
|                                  | `LSL`     | `dst_64[, src1]`           | 1 |      2       | `0x30` (`0b110_000`) |   •   |    •    |   X   |   X   |   •   | • | •  | X | 64-bit logical shift left                                           |
|                                  | `LSR`     | `dst[, src1]`              | 0 |      1       | `0x31` (`0b110_001`) |   •   |    •    | **0** |   X   |   •   | • | •  | X | `dst <- dst >> (src1 \| C)` (clears S)                              |
|                                  | `LSR`     | `dst_64[, src1]`           | 1 |      2       | `0x31` (`0b110_001`) |   •   |    •    | **0** |   X   |   •   | • | •  | X | 64-bit logical shift right                                          |
|                                  | `LZC`     | `dst, src2`                | 0 |      1       | `0x36` (`0b110_110`) |   •   |    •    |   •   |   •   |   •   | • | •  | X | `dst <- count_leading_zeros(src2)` (ZF if 0)                        |
|                                  | `LZC`     | `dst_64, src2_64`          | 1 |      2       | `0x36` (`0b110_110`) |   •   |    •    |   •   |   •   |   •   | • | •  | X | 64-bit leading zero count                                           |

---

## 2. Detailed Instruction Reference

### Block 0 & 1 (0b000 / 0b001): Arithmetic / Adder Block

```
================================================================================
ADD dst, src2 / ADD dst_64, src2_64 — ADD REGISTER TO ACCUMULATOR (BINARY)
ADD dst, src1, src2 / ADD dst_64, src1_64, src2_64 — ADD REGISTER TO REGISTER (TERNARY)
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  X  |  X  |  -  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if result is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of result is 1; reset to 0 otherwise.
* **`C`**: Set to 1 if unsigned carry out occurred ($sum > 2^{32}-1$ or $2^{64}-1$); reset to 0 otherwise.
* **`V`**: Set to 1 if signed two's-complement overflow occurred; reset to 0 otherwise.
* **`U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
if W == 0:
    dst [31:0] <- (src1 or dst) [31:0] + src2 [31:0]
    UPC        <- UPC + 1
else:
    Cycle 1: dst_64_L [31:0] <- (src1_64_L or dst_64_L) [31:0] + src2_64_L [31:0], latch Carry_out
    Cycle 2: dst_64_H [31:0] <- (src1_64_H or dst_64_H) [31:0] + src2_64_H [31:0] + Carry_in
    UPC       <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 000000`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = dst` (or `src1`
in 3-operand form), `HB_MUX = src2`.

#### Description

Adds the contents of `src2` to accumulator `dst` (or `dst_64`), or adds `src1` and `src2` writing to `dst` in ternary
form (`ADD dst, src1, src2` / `ADD dst_64, src1_64, src2_64`), using `alu_adder32` with carry chain. When `W = 1`, the
operation executes across two
consecutive cycles, adding the low halves in cycle 1 and the high halves with carry in cycle 2.

#### Concrete Numeric Example

```text
Suppose AL = 0x7FFFFFFF, BL = 0x00000001 (W = 0).
After execution of ADD AL, BL:
  AL + BL = 0x7FFFFFFF + 0x00000001 = 0x80000000
  Bit 31 = 1: sets SIGN (S) to 1
  No unsigned carry (0x80000000 <= 0xFFFFFFFF): sets CARRY (C) to 0
  Non-zero result: sets ZERO (Z) to 0
  Positive + Positive = Negative: sets OVERFLOW (V) to 1
```

---

```
================================================================================
ADC dst, src2 / ADC dst_64, src2_64 — ADD WITH CARRY TO ACCUMULATOR (BINARY)
ADC dst, src1, src2 / ADC dst_64, src1_64, src2_64 — ADD WITH CARRY REGISTER TO REGISTER (TERNARY)
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  X  |  X  |  -  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if result is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of result is 1; reset to 0 otherwise.
* **`C`**: Set to 1 if unsigned carry out occurred; reset to 0 otherwise.
* **`V`**: Set to 1 if signed two's-complement overflow occurred; reset to 0 otherwise.
* **`U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
if W == 0:
    dst [31:0] <- (src1 or dst) [31:0] + src2 [31:0] + STATUS.C
    UPC        <- UPC + 1
else:
    Cycle 1: dst_64_L [31:0] <- (src1_64_L or dst_64_L) [31:0] + src2_64_L [31:0] + STATUS.C, latch Carry_out
    Cycle 2: dst_64_H [31:0] <- (src1_64_H or dst_64_H) [31:0] + src2_64_H [31:0] + Carry_in
    UPC       <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 000001`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = dst` (or `src1`),
`HB_MUX = src2`.

#### Description

Adds the contents of `src2` and the carry flag `C` to accumulator `dst` (or `dst_64`), or adds `src1 + src2 + C` writing
to `dst` in
ternary form (`ADC dst, src1, src2` / `ADC dst_64, src1_64, src2_64`). Used primarily for multi-word synthesis beyond 64
bits.

#### Concrete Numeric Example

```text
Suppose AL = 0x00000001, BL = 0x00000002, STATUS.C = 1.
After execution of ADC AL, BL:
  AL + BL + C = 1 + 2 + 1 = 0x00000004
  Bit 31 = 0: sets SIGN (S) to 0
  No carry: sets CARRY (C) to 0
  Non-zero result: sets ZERO (Z) to 0
  No signed overflow: sets OVERFLOW (V) to 0
```

---

```
================================================================================
SUB dst, src2 / SUB dst_64, src2_64 — SUBTRACT REGISTER FROM ACCUMULATOR (BINARY)
SUB dst, src1, src2 / SUB dst_64, src1_64, src2_64 — SUBTRACT REGISTER FROM REGISTER (TERNARY)
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  X  |  X  |  -  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if result is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of result is 1; reset to 0 otherwise.
* **`C`**: Set to 1 if borrow occurred ($dst < src2$ or $src1 < src2$ unsigned); reset to 0 otherwise.
* **`V`**: Set to 1 if signed two's-complement overflow occurred; reset to 0 otherwise.
* **`U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
if W == 0:
    dst [31:0] <- (src1 or dst) [31:0] - src2 [31:0]
    UPC        <- UPC + 1
else:
    Cycle 1: dst_64_L [31:0] <- (src1_64_L or dst_64_L) [31:0] - src2_64_L [31:0], latch Borrow_out
    Cycle 2: dst_64_H [31:0] <- (src1_64_H or dst_64_H) [31:0] - src2_64_H [31:0] - Borrow_in
    UPC       <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 000010`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = dst` (or `src1`),
`HB_MUX = src2`.

#### Description

Subtracts `src2` from `dst` (or computes $src1 - src2$ into `dst` in ternary form `SUB dst, src1, src2` /
`SUB dst_64, src1_64, src2_64`). Evaluated
as $(src1\text{ or }dst) + \overline{src2} + 1$ using `alu_adder32` with subtract control asserted. In 64-bit mode
(`W = 1`), subtraction proceeds across 2 cycles.

#### Concrete Numeric Example

```text
Suppose AL = 0x00000005, BL = 0x00000008.
After execution of SUB AL, BL:
  AL - BL = 5 - 8 = -3 = 0xFFFFFFFD
  Bit 31 = 1: sets SIGN (S) to 1
  Borrow occurred (5 < 8): sets CARRY (C) to 1
  Non-zero result: sets ZERO (Z) to 0
  No signed overflow: sets OVERFLOW (V) to 0
```

---

```
================================================================================
SBB dst, src2 / SBB dst_64, src2_64 — SUBTRACT WITH BORROW FROM ACCUMULATOR (BINARY)
SBB dst, src1, src2 / SBB dst_64, src1_64, src2_64 — SUBTRACT WITH BORROW REGISTER FROM REGISTER (TERNARY)
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  X  |  X  |  -  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if result is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of result is 1; reset to 0 otherwise.
* **`C`**: Set to 1 if borrow occurred; reset to 0 otherwise.
* **`V`**: Set to 1 if signed two's-complement overflow occurred; reset to 0 otherwise.
* **`U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
if W == 0:
    dst [31:0] <- (src1 or dst) [31:0] - src2 [31:0] - STATUS.C
    UPC        <- UPC + 1
else:
    Cycle 1: dst_64_L [31:0] <- (src1_64_L or dst_64_L) [31:0] - src2_64_L [31:0] - STATUS.C, latch Borrow_out
    Cycle 2: dst_64_H [31:0] <- (src1_64_H or dst_64_H) [31:0] - src2_64_H [31:0] - Borrow_in
    UPC       <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 000011`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = dst` (or `src1`),
`HB_MUX = src2`.

#### Description

Subtracts `src2` and incoming borrow `C` from accumulator `dst` (or computes $src1 - src2 - C$ into `dst` in ternary
form `SBB dst, src1, src2` / `SBB dst_64, src1_64, src2_64`).

#### Concrete Numeric Example

```text
Suppose AL = 0x00000005, BL = 0x00000002, STATUS.C = 1.
After execution of SBB AL, BL:
  AL - BL - C = 5 - 2 - 1 = 0x00000002
  Bit 31 = 0: sets SIGN (S) to 0
  No borrow: sets CARRY (C) to 0
  Non-zero result: sets ZERO (Z) to 0
  No signed overflow: sets OVERFLOW (V) to 0
```

---

```
================================================================================
CMP src1, src2 / CMP src1_64, src2_64 — COMPARE TWO REGISTERS
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  X  |  X  |  -  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if $src1 == src2$; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of $(src1 - src2)$ is 1; reset to 0 otherwise.
* **`C`**: Set to 1 if borrow occurred ($src1 < src2$ unsigned); reset to 0 otherwise.
* **`V`**: Set to 1 if signed two's-complement overflow occurred; reset to 0 otherwise.
* **`U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
if W == 0:
    Discard (src1 - src2) -> RES_SEL = NONE (no register write)
    Update STATUS flags: sets ZF and SF (and CF, VF)
    UPC <- UPC + 1
else:
    Cycle 1: Discard (src1_L - src2_L), latch Borrow_out
    Cycle 2: Discard (src1_H - src2_H - Borrow_in)
    Update STATUS flags for 64-bit comparison
    UPC <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 000100`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = 0b1111` (`NONE`),
`HA_MUX = src1`, `HB_MUX = src2`.

#### Description

Compares `src1` with `src2` by computing $src1 - src2$ on `alu_adder32` and updating status flags `Z` and `S` (along
with `C` and `V`). No register is written (`EXEC_WB` pulses with `RES_SEL = NONE`).

#### Concrete Numeric Example

```text
Suppose AL = 0x00000010, BL = 0x00000010.
After execution of CMP AL, BL:
  AL - BL = 0x00000000
  Result is zero: sets ZERO (Z) to 1
  Bit 31 = 0: sets SIGN (S) to 0
  No borrow (16 >= 16): sets CARRY (C) to 0
  No overflow: sets OVERFLOW (V) to 0
  AL remains 0x00000010 unchanged.
```

---

```
================================================================================
EXP_ADD dst, src2 / EXP_ADD EA, src2 — EXPONENT 12-BIT ADDITION (BINARY)
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  -  |  X  |  X  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if 12-bit result is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if bit 11 (sign bit of 12-bit signed exponent) is 1; reset to 0 otherwise.
* **`C`**: Unaffected.
* **`V`**: Set to 1 if exponent overflow occurred ($EA + src2 > +1023$); reset to 0 otherwise.
* **`U`**: Set to 1 if exponent underflow occurred ($EA + src2 < -1022$); reset to 0 otherwise.
* **`ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
dst [11:0] <- (dst [11:0] + src2 [11:0]) & 0x0FFF
UPC        <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 000101`. `W = 0` (always 1 cycle). `RES_SEL = dst`, `HA_MUX = dst`, `HB_MUX = src2` (`EB` or `IMM`).

#### Description

Performs 12-bit signed addition on the exponent registers using `alu_exp12`. Automatically checks IEEE exponent limits
($\pm 1023$ / $\pm 1022$), asserting `VF` on overflow and `UF` on underflow.

#### Concrete Numeric Example

```text
Suppose EA = 1000, EB = 50.
After execution of EXP_ADD EA, EB:
  EA + EB = 1050 > +1023
  EA becomes 1050
  Overflow detected: sets OVERFLOW (V) to 1
  Underflow clear: sets UNDERFLOW (U) to 0
  Non-zero result: sets ZERO (Z) to 0, SIGN (S) to 0
```

---

```
================================================================================
EXP_SUB dst, src2 / EXP_SUB EA, src2 — EXPONENT 12-BIT SUBTRACTION (BINARY)
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  -  |  X  |  X  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if 12-bit result is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if bit 11 is 1; reset to 0 otherwise.
* **`C`**: Unaffected.
* **`V`**: Set to 1 if exponent overflow occurred ($EA - src2 > +1023$); reset to 0 otherwise.
* **`U`**: Set to 1 if exponent underflow occurred ($EA - src2 < -1022$); reset to 0 otherwise.
* **`ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
dst [11:0] <- (dst [11:0] - src2 [11:0]) & 0x0FFF
UPC        <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 000110`. `W = 0` (always 1 cycle). `RES_SEL = dst`, `HA_MUX = dst`, `HB_MUX = src2` (`EB` or `IMM`).

#### Description

Performs 12-bit signed subtraction on the exponent registers using `alu_exp12`. Asserts `VF` on overflow and `UF` on
underflow.

#### Concrete Numeric Example

```text
Suppose EA = -1000, EB = 50.
After execution of EXP_SUB EA, EB:
  EA - EB = -1050 < -1022
  Underflow detected: sets UNDERFLOW (U) to 1
  Overflow clear: sets OVERFLOW (V) to 0
  Bit 11 = 1: sets SIGN (S) to 1
```

---

### Block 1 (0b001): Hardware Multiply / Divide / Math Block

```
================================================================================
PACK dst, src1 / PACK dst_64, src1 — PACK IEEE-754 FLOATING-POINT NUMBER (BINARY)
PACK dst, src1, src2 / PACK dst_64, src1, src2_64 — PACK IEEE-754 FLOATING-POINT NUMBER (TERNARY)
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  -  |  X  |  X  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if packed float is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if sign bit of packed float is 1; reset to 0 otherwise.
* **`C`**: Unaffected.
* **`V`**: Set to 1 if exponent overflowed to $\pm\infty$ ($src1 \ge \text{MAX\_EXP}$); reset to 0 otherwise.
* **`U`**: Set to 1 if exponent underflowed ($src1 \le 0$); reset to 0 otherwise.
* **`ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
if W == 0:  # Float32
    dst [31:0] <- { STATUS.S, src1 [7:0], (src2 or dst) [22:0] }
    UPC        <- UPC + 1
else:       # Float64
    {dst_64_H [31:0], dst_64_L [31:0]} <- { STATUS.S, src1 [10:0], (src2_64_H or dst_64_H) [19:0], (src2_64_L or dst_64_L) [31:0] }
    UPC                                <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 001000`. `W = 0` (Float32, 1 cycle) or `W = 1` (Float64, 2 cycles). `RES_SEL = dst`, `HA_MUX = src1` (exponent
register `EA` or `EB`), `HB_MUX = dst` (binary form) or `src2` / `src2_64` (ternary form for mantissa).

#### Description

Assembles an IEEE-754 floating-point value from its components: sign bit from `STATUS.S`, biased exponent from `src1`
(`EA` or `EB`), and normalized mantissa from `src2` / `src2_64` (in ternary form) or `dst` / `dst_64` (in binary form,
e.g. `AL` or `dst_64`), stripping the implicit hidden bit. Asserts `VF` on
exponent overflow (saturating to infinity) or `UF` on exponent underflow (flushing to signed zero).

#### Concrete Numeric Example

```text
Suppose STATUS.S = 0, EA = 127 (0x7F, unbiased 0), AL mantissa = 0x00000000 (representing 1.0).
After execution of PACK AL, EA (W = 0, binary form):
  AL = {0, 0x7F, 23'd0} = 0x3F800000 (+1.0f)
  Sign = 0: sets SIGN (S) to 0
  Non-zero float: sets ZERO (Z) to 0
  Valid exponent range: sets OVERFLOW (V) to 0, UNDERFLOW (U) to 0

Suppose STATUS.S = 0, EA = 127, BL mantissa = 0x00000000.
After execution of PACK AL, EA, BL (W = 0, ternary form):
  AL = {0, 0x7F, 23'd0} = 0x3F800000 (+1.0f)
  BL remains unchanged.
```

---

```
================================================================================
UNPACK dst, src1 / UNPACK dst_64, src1 — UNPACK IEEE-754 FLOATING-POINT NUMBER (BINARY)
UNPACK dst, src1, src2 / UNPACK dst_64, src1, src2_64 — UNPACK IEEE-754 FLOATING-POINT NUMBER (TERNARY)
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  -  |  -  |  -  |  X  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if input float is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if float sign bit is 1; reset to 0 otherwise.
* **`DF`**: Set to `STATUS.S ^ input.sign` (computes operand sign difference for add/sub alignment).
* **`C`, `V`, `U`, `ERR`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
if W == 0:  # Float32
    src1 [11:0] <- zero_extend((src2 or dst) [30:23])
    dst [31:0]  <- { 8'b0, 1'b1, (src2 or dst) [22:0] }  # restore hidden bit
    STATUS.D    <- STATUS.S ^ (src2 or dst) [31]
    STATUS.S    <- (src2 or dst) [31]
    UPC         <- UPC + 1
else:       # Float64
    src1 [11:0]     <- zero_extend((src2_64_H or dst_64_H) [30:20])
    dst_64_H [31:0] <- { 11'b0, 1'b1, (src2_64_H or dst_64_H) [19:0] }
    dst_64_L [31:0] <- (src2_64_L or dst_64_L) [31:0]
    STATUS.D        <- STATUS.S ^ (src2_64_H or dst_64_H) [31]
    STATUS.S        <- (src2_64_H or dst_64_H) [31]
    UPC             <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 001001`. `W = 0` (Float32) or `W = 1` (Float64). `RES_SEL = dst`, `HA_MUX = src1` (exponent register `EA` or
`EB`), `HB_MUX = dst` (binary form) or `src2` / `src2_64` (ternary form for input float).

#### Description

Splits an IEEE-754 floating-point number into its constituent fields: extracts biased exponent into `src1` (`EA` or
`EB`), inserts the hidden bit into `dst` (or `dst_64`) mantissa, updates `STATUS.S` with operand sign, and calculates
`DIFF_SIGN`
(`STATUS.D = sign_A ^ sign_B`) to steer downstream addition/subtraction.

In binary form (`dst, src1` / `dst_64, src1`), the input float is read from `dst` and overwritten in place by the
normalized mantissa. In ternary form (`dst, src1, src2` / `dst_64, src1, src2_64`), the input float is read from `src2`
(or `src2_64`), leaving `src2` unchanged while writing the mantissa to `dst` and the exponent to `src1`.

#### Concrete Numeric Example

```text
Suppose AL = 0x3F800000 (+1.0f), STATUS.S = 1 (previous operand was negative).
After execution of UNPACK AL, EA (W = 0, binary form):
  EA <- 0x007F (127)
  AL <- 0x00800000 (normalized mantissa with hidden bit 23 set)
  Sign bit of AL is 0: sets SIGN (S) to 0
  DIFF_SIGN: 1 ^ 0 = 1: sets DIFF_SIGN (D) to 1 (different signs)
  Non-zero float: sets ZERO (Z) to 0

Suppose BL = 0x3F800000 (+1.0f), STATUS.S = 1.
After execution of UNPACK AL, EA, BL (W = 0, ternary form):
  EA <- 0x007F (127)
  AL <- 0x00800000 (normalized mantissa with hidden bit 23 set)
  BL remains 0x3F800000 (unchanged)
  Sign bit of BL is 0: sets SIGN (S) to 0
  DIFF_SIGN: 1 ^ 0 = 1: sets DIFF_SIGN (D) to 1
  Non-zero float: sets ZERO (Z) to 0
```

---

```
================================================================================
MUL dst, src2 / MUL dst_64, src2_64 — SIGNED MULTIPLY (BINARY)
MUL dst, src1, src2 / MUL dst_64, src1_64, src2_64 — SIGNED MULTIPLY (TERNARY)
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  0  |  X  |  -  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if entire product is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of product is 1; reset to 0 otherwise.
* **`C`**: Always cleared to 0.
* **`V`**: Set to 1 if product exceeds single-word capacity ($AH \neq 0$ for 32-bit, or when high half is not sign
  extension of low half); reset to 0 otherwise.
* **`U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
if W == 0:  # Hardware Booth Multiplier Core (16 cycles)
    {AH [31:0], AL [31:0]} <- (src1 or dst) [31:0] * src2 [31:0]  (signed)
    UPC                    <- UPC + 1
else:       # 64-bit multiply (64 cycles via microcode)
    dst_64 [63:0]          <- (src1_64 or dst_64) [63:0] * src2_64 [63:0]  (signed)
    UPC                    <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 001010`. `W = 0` (32-bit $\times$ 32-bit $\to$ 64-bit product, 16 cycles) or `W = 1` (64-bit $\times$
64-bit $\to$ 64-bit product, 64 cycles). `RES_SEL = dst`,
`HA_MUX = dst` (or `src1` in 3-operand form), `HB_MUX = src2`.

#### Description

Performs signed Radix-4 Booth multiplication using the shared multiplier core co-located with the arithmetic block.
Supports
binary (`dst, src2` / `dst_64, src2_64`) and ternary (`dst, src1, src2` / `dst_64, src1_64, src2_64`) forms. The
engine computes 2 bits per cycle over 16 clock cycles, placing the full 64-bit product into `{AH, AL}` (or `dst_64` for
64-bit).

- Cycle 15: Writes low word to `AL` (or low half of `dst_64`).
- Cycle 16: Writes high word to `AH` (or high half of `dst_64`) and commits status flags `Z, S, C=0, V`.

#### Concrete Numeric Example

```text
Suppose AL = 0x00010000 (65536), BL = 0x00020000 (131072), W = 0.
After execution of MUL AL, BL (16 cycles):
  Product = 65536 * 131072 = 8,589,934,592 = 0x00000002_00000000
  AH = 0x00000002, AL = 0x00000000
  Upper half AH != 0: sets OVERFLOW (V) to 1
  Full 64-bit product is non-zero: sets ZERO (Z) to 0
  MSB of product (bit 63) = 0: sets SIGN (S) to 0
  Carry flag: cleared to 0
```

---

```
================================================================================
DIV dst, src2 / DIV dst_64, src2_64 — SIGNED INTEGER DIVISION (BINARY)
DIV dst, src1, src2 / DIV dst_64, src1_64, src2_64 — SIGNED INTEGER DIVISION (TERNARY)
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  X  |  X  |  -  |  X  |  -  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if quotient is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of quotient is 1; reset to 0 otherwise.
* **`ERR`**: Set to 1 on division by zero ($src2 = 0$).
* **`V`**: Set to 1 on division by zero ($src2 = 0$) or signed overflow (`0x80000000 / -1`).
* **`C`, `U`, `DF`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
if src2 == 0:
    STATUS.ERR <- 1
    STATUS.V   <- 1
    UPC        <- UPC + 1
elif W == 0:  # 32-bit divide (32 cycles)
    dst [31:0] <- (src1 or dst) [31:0] / src2 [31:0]  (signed quotient)
    DL [31:0]  <- (src1 or dst) [31:0] % src2 [31:0]  (remainder)
    UPC        <- UPC + 1
else:         # 64-bit divide (64 cycles via microcode)
    dst_64 [63:0] <- (src1_64 or dst_64) [63:0] / src2_64 [63:0]  (signed quotient)
    DX [63:0]     <- (src1_64 or dst_64) [63:0] % src2_64 [63:0]  (remainder)
    UPC           <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 001011`. `W = 0` (32-bit, 32 cycles) or `W = 1` (64-bit, 64 cycles). `RES_SEL = dst`, `HA_MUX = dst` (or
`src1` in 3-operand form),
`HB_MUX = src2`.

#### Description

Performs signed integer division of `dst` (or `src1` in ternary form) by `src2` using a multi-cycle non-restoring
divider engine co-located in the
arithmetic block. Supports binary and ternary forms for both 32-bit and 64-bit operands. Produces both signed quotient
(written to `dst`) and signed remainder (latched into `DL` or `DX`). If
`src2 == 0`, the operation aborts without modifying `dst` or `DL`/`DX`, asserting `ERR = 1` and `V = 1`.

- Cycle 31: Writes quotient to `dst`.
- Cycle 32: Writes remainder to `DL` (or `DX`) and commits status flags.

#### Concrete Numeric Example

```text
Suppose AL = 0x00000017 (23), BL = 0x00000005 (5), W = 0.
After execution of DIV AL, BL (32 cycles):
  Quotient: 23 / 5 = 4 -> AL = 0x00000004
  Remainder: 23 % 5 = 3 -> DL = 0x00000003
  Non-zero quotient: sets ZERO (Z) to 0
  Positive quotient: sets SIGN (S) to 0
  Valid division: sets OVERFLOW (V) to 0, ERR to 0
```

---

```
================================================================================
MULU dst, src2 / MULU dst_64, src2_64 — UNSIGNED MULTIPLY (BINARY)
MULU dst, src1, src2 / MULU dst_64, src1_64, src2_64 — UNSIGNED MULTIPLY (TERNARY)
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  0  |  X  |  -  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if entire 64-bit product is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of product (bit 63) is 1; reset to 0 otherwise.
* **`C`**: Always cleared to 0.
* **`V`**: Set to 1 if product exceeds single-word capacity ($AH \neq 0$ for 32-bit, or $DX \neq 0$ for 64-bit); reset
  to 0 otherwise.
* **`U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
if W == 0:  # Hardware Booth Multiplier Core (16 cycles)
    {AH [31:0], AL [31:0]}     <- (src1 or dst) [31:0] * src2 [31:0]  (unsigned)
    UPC                        <- UPC + 1
else:       # 64-bit unsigned multiply (64 cycles via microcode)
    {DX [63:0], dst_64 [63:0]} <- (src1_64 or dst_64) [63:0] * src2_64 [63:0]  (unsigned)
    UPC                        <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 001110`. `W = 0` (32-bit $\times$ 32-bit $\to$ 64-bit product, 16 cycles) or `W = 1` (64-bit $\times$
64-bit $\to$ 128-bit product, 64 cycles). `RES_SEL = dst`,
`HA_MUX = dst` (or `src1` in 3-operand form), `HB_MUX = src2`.

#### Description

Performs unsigned Radix-4 Booth multiplication using the shared multiplier core. Supports binary and ternary forms for
both 32-bit and 64-bit operands. Operates across 16 cycles (or 64 cycles for 64-bit), writing low
word product to `dst` in cycle 15, high word to `AH`/`DX` in cycle 16, and committing status flags. `VF` is asserted if
high half is non-zero.

#### Concrete Numeric Example

```text
Suppose AL = 0x80000000, BL = 0x00000002, W = 0.
After execution of MULU AL, BL (16 cycles):
  Product = 0x80000000 * 2 = 0x00000001_00000000
  AH = 0x00000001, AL = 0x00000000
  Upper half AH != 0: sets OVERFLOW (V) to 1
  Full 64-bit product non-zero: sets ZERO (Z) to 0
  MSB (bit 63) = 0: sets SIGN (S) to 0
  Carry flag: cleared to 0
```

---

```
================================================================================
DIVU dst, src2 / DIVU dst_64, src2_64 — UNSIGNED INTEGER DIVISION (BINARY)
DIVU dst, src1, src2 / DIVU dst_64, src1_64, src2_64 — UNSIGNED INTEGER DIVISION (TERNARY)
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  X  |  X  |  -  |  X  |  -  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if quotient is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of quotient is 1; reset to 0 otherwise.
* **`ERR`**: Set to 1 on divide-by-zero ($src2 == 0$); reset to 0 otherwise.
* **`V`**: Set to 1 on divide-by-zero ($src2 == 0$); reset to 0 otherwise.
* **`C`, `U`, `DF`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
if src2 == 0:
    STATUS.ERR <- 1
    STATUS.V   <- 1
    UPC        <- UPC + 1
elif W == 0:  # 32-bit divide (32 cycles)
    dst [31:0] <- (src1 or dst) [31:0] / src2 [31:0]  (unsigned quotient)
    DL [31:0]  <- (src1 or dst) [31:0] % src2 [31:0]  (unsigned remainder)
    UPC        <- UPC + 1
else:         # 64-bit divide (64 cycles via microcode)
    dst_64 [63:0] <- (src1_64 or dst_64) [63:0] / src2_64 [63:0]  (unsigned quotient)
    DX [63:0]     <- (src1_64 or dst_64) [63:0] % src2_64 [63:0]  (unsigned remainder)
    UPC           <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 001111`. `W = 0` (32-bit, 32 cycles) or `W = 1` (64-bit, 64 cycles). `RES_SEL = dst`, `HA_MUX = dst` (or
`src1` in 3-operand form),
`HB_MUX = src2`.

#### Description

Performs unsigned integer division of `dst` (or `src1` in ternary form) by `src2` using the non-restoring divider
engine. Supports binary and ternary forms for both 32-bit and 64-bit operands. Produces unsigned quotient
in `dst` and unsigned remainder in `DL` (or `DX` when `W=1`). If `src2 == 0`, aborts without modifying `dst` or `DL`/
`DX`, setting `ERR = 1`
and `V = 1`.

- Cycle 31: Writes quotient to `dst`.
- Cycle 32: Writes remainder to `DL` (or `DX`) and commits status flags.

#### Concrete Numeric Example

```text
Suppose AL = 0x00000017 (23), BL = 0x00000005 (5), W = 0.
After execution of DIVU AL, BL (32 cycles):
  Quotient: 23 / 5 = 4 -> AL = 0x00000004
  Remainder: 23 % 5 = 3 -> DL = 0x00000003
  Non-zero quotient: sets ZERO (Z) to 0
  Positive quotient: sets SIGN (S) to 0
  Valid division: sets OVERFLOW (V) to 0, ERR to 0
```

---

### Block 2 (0b010): Logic Block

```
================================================================================
AND dst, src2 / AND dst_64, src2_64 — BITWISE LOGICAL AND (BINARY)
AND dst, src1, src2 / AND dst_64, src1_64, src2_64 — BITWISE LOGICAL AND (TERNARY)
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  0  |  0  |  -  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if result is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of result is 1; reset to 0 otherwise.
* **`C`**: Cleared to 0.
* **`V`**: Cleared to 0.
* **`U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
if W == 0:
    dst [31:0] <- (src1 or dst) [31:0] & src2 [31:0]
    UPC        <- UPC + 1
else:
    Cycle 1: dst_64_L [31:0] <- (src1_64_L or dst_64_L) [31:0] & src2_64_L [31:0]
    Cycle 2: dst_64_H [31:0] <- (src1_64_H or dst_64_H) [31:0] & src2_64_H [31:0]
    UPC                      <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 010000`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = dst` (or `src1`
in 3-operand form),
`HB_MUX = src2`.

#### Description

Performs bitwise logical AND between `(src1 or dst)` and `src2` (or `(src1_64 or dst_64)` and `src2_64` in 64-bit mode).
Supports binary and ternary forms. Always resets `C` and `V` to 0.

#### Concrete Numeric Example

```text
Suppose AL = 0x0000FFFF, BL = 0x00FF00FF.
After execution of AND AL, BL:
  AL <- 0x000000FF
  Bit 31 = 0: sets SIGN (S) to 0
  Non-zero result: sets ZERO (Z) to 0
  Clears CARRY (C) to 0, OVERFLOW (V) to 0
```

---

```
================================================================================
OR dst, src2 / OR dst_64, src2_64 — BITWISE LOGICAL OR (BINARY)
OR dst, src1, src2 / OR dst_64, src1_64, src2_64 — BITWISE LOGICAL OR (TERNARY)
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  0  |  0  |  -  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if result is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of result is 1; reset to 0 otherwise.
* **`C`**: Cleared to 0.
* **`V`**: Cleared to 0.
* **`U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
if W == 0:
    dst [31:0] <- (src1 or dst) [31:0] | src2 [31:0]
    UPC        <- UPC + 1
else:
    Cycle 1: dst_64_L [31:0] <- (src1_64_L or dst_64_L) [31:0] | src2_64_L [31:0]
    Cycle 2: dst_64_H [31:0] <- (src1_64_H or dst_64_H) [31:0] | src2_64_H [31:0]
    UPC                      <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 010001`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = dst` (or `src1`
in 3-operand form),
`HB_MUX = src2`.

#### Description

Performs bitwise logical OR between `(src1 or dst)` and `src2` (or `(src1_64 or dst_64)` and `src2_64` in 64-bit mode).
Supports binary and ternary forms. Resets `C` and `V` to 0.

#### Concrete Numeric Example

```text
Suppose AL = 0x12000000, BL = 0x00000034.
After execution of OR AL, BL:
  AL <- 0x12000034
  Bit 31 = 0: sets SIGN (S) to 0
  Non-zero result: sets ZERO (Z) to 0
  Clears CARRY (C) to 0, OVERFLOW (V) to 0
```

---

```
================================================================================
XOR dst, src2 / XOR dst_64, src2_64 — BITWISE LOGICAL EXCLUSIVE OR (BINARY)
XOR dst, src1, src2 / XOR dst_64, src1_64, src2_64 — BITWISE LOGICAL EXCLUSIVE OR (TERNARY)
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  0  |  0  |  -  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if result is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of result is 1; reset to 0 otherwise.
* **`C`**: Cleared to 0.
* **`V`**: Cleared to 0.
* **`U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
if W == 0:
    dst [31:0] <- (src1 or dst) [31:0] ^ src2 [31:0]
    UPC        <- UPC + 1
else:
    Cycle 1: dst_64_L [31:0] <- (src1_64_L or dst_64_L) [31:0] ^ src2_64_L [31:0]
    Cycle 2: dst_64_H [31:0] <- (src1_64_H or dst_64_H) [31:0] ^ src2_64_H [31:0]
    UPC                      <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 010010`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = dst` (or `src1`
in 3-operand form),
`HB_MUX = src2`.

#### Description

Performs bitwise logical XOR between `(src1 or dst)` and `src2` (or `(src1_64 or dst_64)` and `src2_64` in 64-bit mode).
Supports binary and ternary forms. Clearing a register (`XOR AL, AL`) produces zero and
asserts `ZF = 1`. Resets `C` and `V` to 0.

#### Concrete Numeric Example

```text
Suppose AL = 0xAAAAAAAA, BL = 0xAAAAAAAA.
After execution of XOR AL, BL:
  AL <- 0x00000000
  Result is zero: sets ZERO (Z) to 1
  Bit 31 = 0: sets SIGN (S) to 0
  Clears CARRY (C) to 0, OVERFLOW (V) to 0
```

---

```
================================================================================
FABS dst / FABS dst_64 — FLOATING-POINT ABSOLUTE VALUE (UNARY)
FABS dst, src1 / FABS dst_64, src1_64 — FLOATING-POINT ABSOLUTE VALUE (BINARY)
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  0  |  -  |  -  |  -  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if float magnitude is zero; reset to 0 otherwise.
* **`S`**: Always cleared to 0 (positive).
* **`C`, `V`, `U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
if W == 0:  # Float32
    dst [30:0]    <- (src1 or dst) [30:0]
    dst [31]      <- 1'b0  # Clear float32 sign bit
    UPC           <- UPC + 1
else:       # Float64
    Cycle 1: dst_64_L [31:0] <- (src1_64_L or dst_64_L) [31:0]
    Cycle 2: dst_64_H [30:0] <- (src1_64_H or dst_64_H) [30:0]
             dst_64_H [31]   <- 1'b0  # Clear float64 sign bit
    UPC                      <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 010011`. `W = 0` (Float32, 1 cycle) or `W = 1` (Float64, 2 cycles). `RES_SEL = dst`, `HA_MUX = dst` (unary) or `src1` (binary),
`HB_MUX = n/a`.

#### Description

Clears the sign bit (bit 31 of `dst` for 32-bit, or bit 31 of `dst_64_H` for 64-bit), producing the positive absolute
value of the floating-point operand. Always clears `STATUS.S` to 0.

Supports unary (`FABS dst` / `FABS dst_64`) where the sign is cleared in place, and binary (`FABS dst, src1` / `FABS dst_64, src1_64`) where the absolute value of `src1` (or `src1_64`) is stored into `dst` (or `dst_64`), leaving `src1` (or `src1_64`) unmodified.

#### Concrete Numeric Example

```text
Suppose AL = 0xBF800000 (-1.0f).
After execution of FABS AL (unary form):
  AL becomes 0x3F800000 (+1.0f)
  Sign cleared: sets SIGN (S) to 0
  Non-zero magnitude: sets ZERO (Z) to 0

Suppose BL = 0xBF800000 (-1.0f).
After execution of FABS AL, BL (binary form):
  AL <- 0x3F800000 (+1.0f)
  BL remains 0xBF800000 (unmodified)
  Sign cleared: sets SIGN (S) to 0
  Non-zero magnitude: sets ZERO (Z) to 0
```

---

```
================================================================================
FCHS dst / FCHS dst_64 — FLOATING-POINT CHANGE SIGN (NEGATE) (UNARY)
FCHS dst, src1 / FCHS dst_64, src1_64 — FLOATING-POINT CHANGE SIGN (NEGATE) (BINARY)
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`S`**: Inverted: `STATUS.S <- ~((src1 or dst)[31])`.
* **`Z`, `C`, `V`, `U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
if W == 0:  # Float32
    dst [30:0]    <- (src1 or dst) [30:0]
    dst [31]      <- ~(src1 or dst) [31]  # Invert float32 sign bit
    STATUS.S      <- dst [31]
    UPC           <- UPC + 1
else:       # Float64
    Cycle 1: dst_64_L [31:0] <- (src1_64_L or dst_64_L) [31:0]
    Cycle 2: dst_64_H [30:0] <- (src1_64_H or dst_64_H) [30:0]
             dst_64_H [31]   <- ~(src1_64_H or dst_64_H) [31]  # Invert float64 sign bit
    STATUS.S                 <- dst_64_H [31]
    UPC                      <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 010100`. `W = 0` (Float32, 1 cycle) or `W = 1` (Float64, 2 cycles). `RES_SEL = dst`, `HA_MUX = dst` (unary) or `src1` (binary),
`HB_MUX = n/a`.

#### Description

Inverts the sign bit of a floating-point operand and updates the sign flag `STATUS.S`.

Supports unary (`FCHS dst` / `FCHS dst_64`) where the sign is inverted in place, and binary (`FCHS dst, src1` / `FCHS dst_64, src1_64`) where the negated value of `src1` (or `src1_64`) is stored into `dst` (or `dst_64`), leaving `src1` (or `src1_64`) unmodified.

#### Concrete Numeric Example

```text
Suppose AL = 0x3F800000 (+1.0f).
After execution of FCHS AL (unary form):
  AL becomes 0xBF800000 (-1.0f)
  Sign inverted: sets SIGN (S) to 1

Suppose BL = 0x3F800000 (+1.0f).
After execution of FCHS AL, BL (binary form):
  AL <- 0xBF800000 (-1.0f)
  BL remains 0x3F800000 (unmodified)
  Sign inverted: sets SIGN (S) to 1
```

---

```
================================================================================
NOT dst / NOT dst_64 — BITWISE LOGICAL COMPLEMENT (UNARY)
NOT dst, src1 / NOT dst_64, src1_64 — BITWISE LOGICAL COMPLEMENT (BINARY)
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  0  |  0  |  -  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if inverted result is zero (operand was all 1s); reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of inverted result is 1; reset to 0 otherwise.
* **`C`**: Cleared to 0.
* **`V`**: Cleared to 0.
* **`U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
if W == 0:
    dst [31:0] <- ~(src1 or dst) [31:0]
    UPC        <- UPC + 1
else:
    Cycle 1: dst_64_L [31:0] <- ~(src1_64_L or dst_64_L) [31:0]
    Cycle 2: dst_64_H [31:0] <- ~(src1_64_H or dst_64_H) [31:0]
    UPC                     <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 010101`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = dst` (unary) or `src1` (binary),
`HB_MUX = n/a`.

#### Description

Performs one's-complement bitwise inversion on all bits of the operand. Resets `C` and `V` to 0.

Supports unary (`NOT dst` / `NOT dst_64`) where `dst` (or `dst_64`) is inverted in place, and binary (`NOT dst, src1` / `NOT dst_64, src1_64`) where `~src1` (or `~src1_64`) is written to `dst` (or `dst_64`), leaving `src1` (or `src1_64`) unmodified.

#### Concrete Numeric Example

```text
Suppose AL = 0x00000000.
After execution of NOT AL (unary form):
  AL <- 0xFFFFFFFF
  Bit 31 = 1: sets SIGN (S) to 1
  Non-zero result: sets ZERO (Z) to 0

Suppose BL = 0x00000000.
After execution of NOT AL, BL (binary form):
  AL <- 0xFFFFFFFF
  BL remains 0x00000000 (unmodified)
  Bit 31 = 1: sets SIGN (S) to 1
  Non-zero result: sets ZERO (Z) to 0
```

---

### Block 6 (0b110): Shifter / LZC Block

```
================================================================================
LSL dst[, src1] / LSL dst_64[, src1] — LOGICAL SHIFT LEFT
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  X  |  -  |  -  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if shifted result is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of shifted result is 1; reset to 0 otherwise.
* **`C`**: Set to the last bit shifted out (MSB of operand); reset to 0 if shift count is 0.
* **`V`, `U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
count = src1[5:0] if src1 provided else C[5:0]
if W == 0:
    STATUS.C   <- (count > 0) ? dst [32 - count] : STATUS.C
    dst [31:0] <- dst [31:0] << count
    UPC        <- UPC + 1
else:
    STATUS.C      <- (count > 0) ? dst_64_H [64 - count - 32] : STATUS.C
    dst_64 [63:0] <- dst_64 [63:0] << count
    UPC           <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 110000`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 1 cycle barrel shifter). `RES_SEL = dst`,
`HA_MUX = src1` (or `C`), `HB_MUX = dst`.

#### Description

Performs logical shift left by the specified count using a single-cycle barrel shifter. Zeros are shifted into the least
significant bit positions. The carry flag captures the last bit shifted out.

#### Concrete Numeric Example

```text
Suppose AL = 0x80000001, C = 1 (count = 1).
After execution of LSL AL:
  AL <- 0x00000002
  Bit 31 shifted out: sets CARRY (C) to 1
  Bit 31 of result = 0: sets SIGN (S) to 0
  Non-zero result: sets ZERO (Z) to 0
```

---

```
================================================================================
LSR dst[, src1] / LSR dst_64[, src1] — LOGICAL SHIFT RIGHT
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  0  |  X  |  -  |  -  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if shifted result is zero; reset to 0 otherwise.
* **`S`**: Cleared to 0 (since zeros are shifted into the MSB).
* **`C`**: Set to the last bit shifted out (LSB of operand); reset to 0 if shift count is 0.
* **`V`, `U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
count = src1[5:0] if src1 provided else C[5:0]
if W == 0:
    STATUS.C   <- (count > 0) ? dst [count - 1] : STATUS.C
    dst [31:0] <- dst [31:0] >> count  (zero-fill MSB)
    UPC        <- UPC + 1
else:
    STATUS.C      <- (count > 0) ? dst_64 [count - 1] : STATUS.C
    dst_64 [63:0] <- dst_64 [63:0] >> count
    UPC           <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 110001`. `W = 0` (32-bit) or `W = 1` (64-bit). `RES_SEL = dst`, `HA_MUX = src1` (or `C`), `HB_MUX = dst`.

#### Description

Performs logical shift right by the specified count using the barrel shifter, inserting zeros into the most significant
bits. The carry flag captures the last bit shifted out.

#### Concrete Numeric Example

```text
Suppose AL = 0x00000005, C = 1 (count = 1).
After execution of LSR AL:
  AL <- 0x00000002
  Bit 0 shifted out (1): sets CARRY (C) to 1
  MSB is 0: sets SIGN (S) to 0
  Non-zero result: sets ZERO (Z) to 0
```

---

```
================================================================================
ASL dst[, src1] / ASL dst_64[, src1] — ARITHMETIC SHIFT LEFT
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  X  |  X  |  -  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if shifted result is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of shifted result is 1; reset to 0 otherwise.
* **`C`**: Set to the last bit shifted out; reset to 0 if shift count is 0.
* **`V`**: Set to 1 if the sign bit changed at any point during the shift; reset to 0 otherwise.
* **`U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
count = src1[5:0] if src1 provided else C[5:0]
if W == 0:
    STATUS.C   <- (count > 0) ? dst [32 - count] : STATUS.C
    STATUS.V   <- sign bit changed during shift
    dst [31:0] <- dst [31:0] << count
    UPC        <- UPC + 1
else:
    STATUS.C      <- (count > 0) ? dst_64_H [64 - count - 32] : STATUS.C
    STATUS.V      <- sign bit changed during shift
    dst_64 [63:0] <- dst_64 [63:0] << count
    UPC           <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 110010`. `W = 0` (32-bit) or `W = 1` (64-bit). `RES_SEL = dst`, `HA_MUX = src1` (or `C`), `HB_MUX = dst`.

#### Description

Performs arithmetic shift left by the specified count using the barrel shifter. Zeros are shifted into the least
significant bit positions. The carry flag captures the last bit shifted out. Overflow (`V`) is set if the sign bit of
the operand changed at any point during the shift, indicating arithmetic overflow for signed numbers.

#### Concrete Numeric Example

```text
Suppose AL = 0x40000000 (+1,073,741,824), C = 1 (count = 1).
After execution of ASL AL:
  AL <- 0x80000000 (-2,147,483,648)
  Sign bit changed from 0 to 1: sets OVERFLOW (V) to 1
  Bit 31 of result = 1: sets SIGN (S) to 1
  Non-zero result: sets ZERO (Z) to 0
```

---

```
================================================================================
ASR dst[, src1] / ASR dst_64[, src1] — ARITHMETIC SHIFT RIGHT
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  X  |  X  |  -  |  -  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if shifted result is zero; reset to 0 otherwise.
* **`S`**: Set to 1 if MSB of shifted result is 1 (preserves sign bit); reset to 0 otherwise.
* **`C`**: Set to the last bit shifted out (LSB of operand); reset to 0 if shift count is 0.
* **`V`, `U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
count = src1[5:0] if src1 provided else C[5:0]
if W == 0:
    STATUS.C   <- (count > 0) ? dst [count - 1] : STATUS.C
    dst [31:0] <- dst [31:0] >>> count  (sign-extended into MSB)
    UPC        <- UPC + 1
else:
    STATUS.C      <- (count > 0) ? dst_64 [count - 1] : STATUS.C
    dst_64 [63:0] <- dst_64 [63:0] >>> count
    UPC           <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 110011`. `W = 0` (32-bit) or `W = 1` (64-bit). `RES_SEL = dst`, `HA_MUX = src1` (or `C`), `HB_MUX = dst`.

#### Description

Performs arithmetic shift right by the specified count using the barrel shifter, duplicating the sign bit into the most
significant bit positions. The carry flag captures the last bit shifted out.

#### Concrete Numeric Example

```text
Suppose AL = 0xFFFFFFF8 (-8), C = 1 (count = 1).
After execution of ASR AL:
  AL <- 0xFFFFFFFC (-4)
  Bit 0 shifted out (0): clears CARRY (C) to 0
  MSB is 1: sets SIGN (S) to 1
  Non-zero result: sets ZERO (Z) to 0
```

---

```
================================================================================
LZC dst, src2 / LZC dst_64, src2_64 — LEADING ZERO COUNT
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if `src2 == 0` (all leading zeros: count is 32 or 64); reset to 0 otherwise.
* **`S`, `C`, `V`, `U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
if W == 0:
    dst [31:0]    <- count_leading_zeros(src2 [31:0])  # 0 to 32
    STATUS.Z      <- (src2 [31:0] == 0)
    UPC           <- UPC + 1
else:
    dst_64 [63:0] <- count_leading_zeros(src2_64 [63:0])  # 0 to 64
    STATUS.Z      <- (src2_64 [63:0] == 0)
    UPC           <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 110110`. `W = 0` (32-bit) or `W = 1` (64-bit). `RES_SEL = dst` (typically `C` register), `HA_MUX = n/a`,
`HB_MUX = src2`.

#### Description

Counts the number of consecutive leading zero bits starting from the most significant bit of `src2` using dedicated LUT
tree logic. Typically written directly to counter `C` for floating-point normalization shifts.

#### Concrete Numeric Example

```text
Suppose AL = 0x00080000 (bit 19 set, bits 31..20 are zeros -> 12 leading zeros), W = 0.
After execution of LZC C, AL:
  C <- 12 (0x0C)
  Source is non-zero: sets ZERO (Z) to 0
```

---

### Block 4 (0b100): Memory Stack & Scratchpad Block

```
================================================================================
PUSH src2 / PUSH src2_64 — PUSH REGISTER ONTO OPERAND STACK
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  X  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`ERR`**: Set to 1 on stack overflow ($OSP + 4 > 32$ for 32-bit or $> 32$ for 64-bit); preserved otherwise.
* **ALU Flags (`S`, `C`, `V`, `U`, `DF`, `Z`)**: Preserved / Unaffected (memory operations only set system error flag
  `ERR`; refer to [ProgrammersGuide.md](ProgrammersGuide.md#2-status-register-status70)).

#### Register Transfer & Datapath Flow

```text
if W == 0:  # 32-bit push (4 bytes)
    if OSP + 4 > 32:
        STATUS.ERR <- 1
    else:
        STACK_RAM [OSP .. OSP+3] <- src2 [31:0]
        OSP                      <- OSP + 4
        TOS                      <- src2 [31:0]
    UPC <- UPC + 1
else:       # 64-bit push (8 bytes)
    if OSP + 8 > 32:
        STATUS.ERR <- 1
    else:
        STACK_RAM [OSP .. OSP+7] <- { src2_64_H [31:0], src2_64_L [31:0] }
        OSP                      <- OSP + 8
        TOS                      <- src2_64_L [31:0]
    UPC <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 100000`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = NONE (0b1111)`, `HA_MUX = NONE`,
`HB_MUX = src2`.

#### Description

Pushes register `src2` (or `src2_64`) onto the 32-byte operand stack, updates internal `TOS` cache register, and
advances `OSP[4:0]`.
No general-purpose register is written (`RES_SEL = NONE`). If pushing exceeds the physical depth, the `ERR` flag
is asserted without clobbering arithmetic flags `VF` or `UF`.

#### Concrete Numeric Example

```text
Suppose OSP = 0x00, AL = 0x12345678, W = 0.
After execution of PUSH AL:
  STACK_RAM[0..3] <- 0x12345678
  TOS <- 0x12345678
  OSP <- 0x04
  No overflow: ERR = 0 (ALU flags unchanged)
```

---

```
================================================================================
POP dst / POP dst_64 — POP REGISTER FROM OPERAND STACK
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  X  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`ERR`**: Set to 1 on stack underflow ($OSP < 4$ for 32-bit or $< 8$ for 64-bit); preserved otherwise.
* **ALU Flags (`S`, `C`, `V`, `U`, `DF`, `Z`)**: Preserved / Unaffected (memory operations only set system error flag
  `ERR`; refer to [ProgrammersGuide.md](ProgrammersGuide.md#2-status-register-status70)).

#### Register Transfer & Datapath Flow

```text
if W == 0:  # 32-bit pop
    if OSP < 4:
        STATUS.ERR <- 1
    else:
        OSP         <- OSP - 4
        dst [31:0]  <- STACK_RAM [OSP .. OSP+3]
        TOS         <- (OSP >= 4) ? STACK_RAM [OSP-4 .. OSP-1] : 0
    UPC <- UPC + 1
else:       # 64-bit pop
    if OSP < 8:
        STATUS.ERR <- 1
    else:
        OSP                    <- OSP - 8
        {dst_64_H, dst_64_L}   <- STACK_RAM [OSP .. OSP+7]
        TOS                    <- dst_64_L
    UPC <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 100001`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = NONE`,
`HB_MUX = TOS`.

#### Description

Pops the top value from the operand stack into `dst` (or `dst_64`) and decrements `OSP`. If popping from an empty stack
($OSP < 4$),
`UF` and `ERR` flags are raised.

#### Concrete Numeric Example

```text
Suppose OSP = 0x04, STACK_RAM[0..3] = 0x12345678, W = 0.
After execution of POP BL:
  BL <- 0x12345678
  OSP <- 0x00
  No underflow: UNDERFLOW (U) = 0, ERR = 0
```

---

```
================================================================================
LDC dst, tbl, addr / LDC dst_64, tbl, addr — LOAD FROM CONSTANT / LUT ROM
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **Flags**: None affected.

#### Register Transfer & Datapath Flow

```text
effective_offset <- (HA_MUX == IMM) ? INSTR[9:0] : HA_MUX_REG

case tbl of
    CONST (0b000):  # DATA_RAM base 0x100 (words 256..319)
        if W == 0:
            dst [31:0]      <- DATA_RAM [0x100 | (effective_offset & 0x03F)]
        else:
            dst_64_L [31:0] <- DATA_RAM [0x100 | (effective_offset & 0x03E)]
            dst_64_H [31:0] <- DATA_RAM [0x101 | (effective_offset & 0x03E)]
    TRIG  (0b001):  # DATA_RAM base 0x200 (words 512..639)
        dst [31:0]          <- DATA_RAM [0x200 | (effective_offset & 0x07F)]
    CHEB  (0b010):  # DATA_RAM base 0x280 (words 640..767)
        dst [31:0]          <- DATA_RAM [0x280 | (effective_offset & 0x07F)]
    RECIP (0b011):  # DATA_RAM base 0x300 (words 768..1023), low 16-bit slice
        dst [15:0]          <- DATA_RAM [0x300 | (effective_offset & 0x0FF)] [15:0]
        dst [31:16]         <- 0
    SQRT  (0b100):  # DATA_RAM base 0x300 (words 768..1023), high 16-bit slice
        dst [15:0]          <- DATA_RAM [0x300 | (effective_offset & 0x0FF)] [31:16]
        dst [31:16]         <- 0

UPC <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 100010`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles).

- `RES_SEL = dst` (4 bits): Destination register (`AL`, `AH`, `BL`, etc.).
- `tbl`: Table selector translated by assembler (`CONST=0b000`, `TRIG=0b001`, `CHEB=0b010`, `RECIP=0b011`,
  `SQRT=0b100`).
- `HA_MUX = addr` (3 bits via `src1`): Selects address source:
    - `HA_MUX = IMM (4)`: Address supplied as immediate constant in `INSTR[9:0]`.
    - `HA_MUX = C (5)` or `AL (0)` / `BL (6)`: Address supplied dynamically from register at runtime.
- `HB_MUX = NONE`.

#### Description

Loads a constant or lookup table entry from the unified `DATA_RAM` ROM space (EBR 0–3, `0x100`–`0x3FF`) into destination
register `dst`.

- **Zero-Cost Bitwise OR Addressing**: Table bases are power-of-two aligned (`0x100`, `0x200`, `0x280`, `0x300`),
  eliminating adders and carry chains on the memory address path.
- **Interleaved Seed Tables (`0x300`–`0x3FF`)**: Reciprocal and Square Root seeds share 256 words at base `0x300`:
    - `RECIP` (`tbl=3`): Slices low 16 bits `[15:0]` and zero-extends into `dst[31:0]`.
    - `SQRT` (`tbl=4`): Slices high 16 bits `[31:16]` and zero-extends into `dst[31:0]`.
- **Dynamic Register Addressing**: In addition to static immediate table offsets, `addr` can be routed from any `HA_MUX`
  register (such as counter `C`), enabling single-cycle dynamic seed table indexing during `SQRT` and `DIV` execution.

#### Concrete Numeric Examples

```text
Example 1: Loading static constant (pi)
LDC AL, CONST, PI_F32
  Machine encoding: OPCODE=LDC, DST=AL, SRC=CONST (0), SRC1=IMM, IMM=PI_F32 (0)
  Reads 32-bit IEEE-754 float (+3.1415927) from DATA_RAM base 0x100 | 0 into AL.
  AL <- 0x40490FDB
  Flags are unaffected.

Example 2: Loading dynamic SQRT seed using runtime index in C
LDC AH, SQRT, C
  Suppose C = 0x4A (mantissa fraction and exponent parity index).
  Machine encoding: OPCODE=LDC, DST=AH, SRC=SQRT (4), SRC1=C
  Reads 32-bit word from DATA_RAM at address 0x300 | 0x4A = 0x34A and slices [31:16] into AH.
  AH <- zero_extend(DATA_RAM[0x34A][31:16])
  Flags are unaffected.
```

---

```
================================================================================
LDI dst, imm / LDI dst_64, imm — LOAD IMMEDIATE INTO REGISTER
LDI flag, val — LOAD IMMEDIATE BIT INTO STATUS FLAG
================================================================================
```

#### Status Flags Affected

When loading into a register (`dst != NONE`):

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **Flags**: None affected when `dst != NONE`.

When loading into a status flag (`dst == NONE`):

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  | mod | mod | mod | mod | mod | mod | mod |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **Flags**: Exactly the flag selected by `FLAG_COND` is modified to `val & 1` (`0` or `1`). All other flags are
  unaffected.

#### Register Transfer & Datapath Flow

```text
if dst != NONE:
    if W == 0:
        dst [31:0]      <- zero_extend(INSTR[9:0])
    else:
        dst_64_L [31:0] <- zero_extend(INSTR[9:0])
        dst_64_H [31:0] <- 0
    STATUS              <- unaffected
    UPC                 <- UPC + 1
else:
    STATUS[flag]        <- INSTR[0]
    UPC                 <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 100011`. `W = 0` (1 cycle) or `W = 1` (2 cycles).

- **Register Form**: `RES_SEL = dst`, `HA_MUX = NONE`, `HB_MUX = IMM`, `IMM = imm[9:0]`.
- **Flag Form**: `RES_SEL = NONE (0b1111)`, `HA_MUX = NONE`, `HB_MUX = IMM`, `FLAG_COND = flag[2:0]`,
  `IMM = val (0 or 1)`.

#### Description

1. **Register Load (`LDI dst, imm` / `LDI dst_64, imm`)**: Loads a 10-bit unsigned immediate constant (`INSTR[9:0]`)
   into `dst` via
   `HB_MUX = IMM`. If `W=1` (64-bit), the immediate is loaded into the low-half register (`dst_64_L`) and zero is loaded
   into
   the high-half register (`dst_64_H`).
2. **Flag Load (`LDI flag, val`)**: When `dst` is `NONE`, the instruction operates as a universal flag manipulation
   operation. It routes `status_wr_sel = 1 << flag` and `res_status = (val & 1) << flag` through the datapath writeback
   multiplexer, setting or clearing the chosen flag in a single cycle without altering any other register or status
   flag. Commonly used to assert or clear `ERR`, `ZERO`, `CARRY`, etc.

#### Concrete Numeric Examples

```text
Example 1: Loading register
LDI EA, 127
  EA <- 127
  Flags unaffected.

Example 2: Setting error flag
LDI ERR, 1
  Machine encoding: OPCODE=LDI, DST=NONE, HB_MUX=IMM, FLAG_COND=ERR (6), IMM=1
  STATUS[ERR] <- 1
  All other status flags unaffected.

Example 3: Clearing zero flag
LDI ZERO, 0
  Machine encoding: OPCODE=LDI, DST=NONE, HB_MUX=IMM, FLAG_COND=ZERO (0), IMM=0
  STATUS[ZERO] <- 0
  All other status flags unaffected.
```

---

```
================================================================================
LD dst, addr / LD dst, [src1] / LD dst_64, addr — LOAD FROM SCRATCHPAD MEMORY
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **Flags**: None affected.

#### Register Transfer & Datapath Flow

```text
addr_val = (HA_MUX == IMM) ? addr [5:0] : src1 [5:0]

if W == 0:
    dst [31:0] <- SCRATCHPAD [addr_val]
    UPC        <- UPC + 1
else:
    // 64-bit load requires an even base memory address (addr_val % 2 == 0)
    dst_64_L   <- SCRATCHPAD [addr_val]
    dst_64_H   <- SCRATCHPAD [addr_val | 1]
    UPC        <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 100100`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`. `HB_MUX = NONE`.

- **Immediate Direct (`LD dst, addr` / `LD dst_64, addr`)**: `HA_MUX = IMM (0b1101)`, `imm[9:0] = addr` (`0..63`).
- **Indirect Register (`LD dst, [src1]`)**: `HA_MUX = src1` (`AL..FH`, `EA`, `EB`, or `C`), `imm[9:0] = 0`.

#### Description

Loads 32 or 64 bits from the internal scratchpad memory (mapped to `DATA_RAM` base `0x080`, words 128..191,
`SCR[0..63]`) into `dst` (or `dst_64`).

Addressing can be specified in two forms:

1. **Direct Immediate Addressing (`LD dst, addr` / `LD dst_64, addr`)**: The address is specified directly as an
   immediate literal `addr` in
   `0..63`.
2. **Indirect Register Addressing (`LD dst, [src1]`)**: The address is sourced from register `src1` (`AL..FH`, `EA`,
   `EB`, or `C`) via `HA_MUX`, with bits `[5:0]` selecting the scratchpad slot.

For 64-bit operations (`W = 1`), the effective address must be an even base address (`addr_val % 2 == 0`, bit 0 is 0);
`dst_64_L` is loaded from `addr_val` and `dst_64_H` from `addr_val | 1`.

#### Concrete Numeric Example

**Direct Immediate Addressing:**

```text
Suppose SCRATCHPAD[0x04] = 0xCAFEBABE.
After execution of LD AL, 0x04:
  AL <- 0xCAFEBABE
  Flags are unaffected.
```

**Indirect Register Addressing:**

```text
Suppose C = 0x04 and SCRATCHPAD[0x04] = 0xCAFEBABE.
After execution of LD AL, [C]:
  AL <- 0xCAFEBABE
  Flags are unaffected.
```

---

```
================================================================================
STO addr, src2 / STO [src1], src2 / STO addr, src2_64 — STORE TO SCRATCHPAD MEMORY
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **Flags**: None affected.

#### Register Transfer & Datapath Flow

```text
addr_val = (HA_MUX == IMM) ? addr [5:0] : src1 [5:0]

if W == 0:
    SCRATCHPAD [addr_val]     <- src2 [31:0]
    UPC                       <- UPC + 1
else:
    // 64-bit store requires an even base memory address (addr_val % 2 == 0)
    SCRATCHPAD [addr_val]     <- src2_64_L [31:0]
    SCRATCHPAD [addr_val | 1] <- src2_64_H [31:0]
    UPC                       <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 100101`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = NONE (0b1111)`. `HB_MUX = src2`.

- **Immediate Direct (`STO addr, src2` / `STO addr, src2_64`)**: `HA_MUX = IMM (0b1101)`, `imm[9:0] = addr` (`0..63`).
- **Indirect Register (`STO [src1], src2`)**: `HA_MUX = src1` (`AL..FH`, `EA`, `EB`, or `C`), `imm[9:0] = 0`.

#### Description

Stores 32 or 64 bits from register `src2` (or `src2_64`) into internal scratchpad memory (mapped to `DATA_RAM` base
`0x080`, words
128..191, `SCR[0..63]`). Does not write to any general-purpose register (`RES_SEL = NONE`).

Addressing can be specified in two forms:

1. **Direct Immediate Addressing (`STO addr, src2` / `STO addr, src2_64`)**: The scratchpad target address is specified
   directly as an
   immediate literal `addr` in `0..63`.
2. **Indirect Register Addressing (`STO [src1], src2`)**: The scratchpad target address is sourced from register `src1`
   (`AL..FH`, `EA`, `EB`, or `C`) via `HA_MUX`, with bits `[5:0]` selecting the scratchpad slot.

For 64-bit operations (`W = 1`), the effective address must be an even base address (`addr_val % 2 == 0`, bit 0 is 0);
`src2_64_L` is stored into `addr_val` and `src2_64_H` into `addr_val | 1`.

#### Concrete Numeric Example

**Direct Immediate Addressing:**

```text
Suppose AL = 0xDEADBEEF.
After execution of STO 0x08, AL:
  SCRATCHPAD[0x08] <- 0xDEADBEEF
  Flags are unaffected.
```

**Indirect Register Addressing:**

```text
Suppose C = 0x08 and AL = 0xDEADBEEF.
After execution of STO [C], AL:
  SCRATCHPAD[0x08] <- 0xDEADBEEF
  Flags are unaffected.
```

---

```
================================================================================
MOV dst, src2 / MOV dst_64, src2_64 — REGISTER-TO-REGISTER MOVE
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **Flags**: None affected.

#### Register Transfer & Datapath Flow

```text
if W == 0:
    dst [31:0]    <- src2 [31:0]
    UPC           <- UPC + 1
else:
    dst_64 [63:0] <- src2_64 [63:0]
    UPC           <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 100110`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 1 cycle via dual writeback). `RES_SEL = dst`,
`HA_MUX = NONE`, `HB_MUX = src2`.

#### Description

Performs register-to-register assignment from `src2` (or `src2_64`) to `dst` (or `dst_64`) across the internal data bus
without changing any status flags.

#### Concrete Numeric Example

```text
Suppose BL = 0x11223344.
After execution of MOV AL, BL:
  AL <- 0x11223344
  Flags are unaffected.
```

---

```
================================================================================
SWAP dst, src2 / SWAP dst_64, src2_64 — REGISTER EXCHANGE
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **Flags**: None affected.

#### Register Transfer & Datapath Flow

```text
if W == 0:
    temp        <- dst
    dst [31:0]  <- src2 [31:0]
    src2 [31:0] <- temp
    UPC         <- UPC + 1
else:
    temp           <- dst_64
    dst_64 [63:0]  <- src2_64 [63:0]
    src2_64 [63:0] <- temp
    UPC            <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 100111`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 1 cycle). `RES_SEL = dst`, `HA_MUX = dst`,
`HB_MUX = src2`.

#### Description

Exchanges the contents of registers `dst` and `src2` (or `dst_64` and `src2_64`) using the internal staging register in
a single cycle.

#### Concrete Numeric Example

```text
Suppose AL = 0xAAAAAAAA, BL = 0x55555555.
After execution of SWAP AL, BL:
  AL <- 0x55555555
  BL <- 0xAAAAAAAA
  Flags are unaffected.
```

---

### Block 5 (0b101): Memory User Buffer & Status Shadow Block

```
================================================================================
LDU dst, addr / LDU dst_64, addr — LOAD FROM HOST USER BUFFER
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **Flags**: None affected.

#### Register Transfer & Datapath Flow

```text
if W == 0:
    dst [31:0] <- USER_BUFFER [addr [5:0]]
    UPC        <- UPC + 1
else:
    {dst_64_H, dst_64_L} <- { USER_BUFFER [addr+1], USER_BUFFER [addr] }
    UPC                  <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 101000`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = dst`, `HA_MUX = IMM`,
`HB_MUX = NONE`.

#### Description

Loads a word from the host-accessible user buffer (mapped to `DATA_RAM` base `0x0C0`, words 192..207, `USR[0..15]`) into
`dst` (or `dst_64`).

#### Concrete Numeric Example

```text
Suppose USER_BUFFER[0x00] = 0x12345678.
After execution of LDU AL, 0x00:
  AL <- 0x12345678
  Flags are unaffected.
```

---

```
================================================================================
STU addr, src2 / STU addr, src2_64 — STORE TO HOST USER BUFFER
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **Flags**: None affected.

#### Register Transfer & Datapath Flow

```text
if W == 0:
    USER_BUFFER [addr [5:0]] <- src2 [31:0]
    UPC                      <- UPC + 1
else:
    { USER_BUFFER [addr+1], USER_BUFFER [addr] } <- { src2_64_H [31:0], src2_64_L [31:0] }
    UPC                      <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 101001`. `W = 0` (32-bit, 1 cycle) or `W = 1` (64-bit, 2 cycles). `RES_SEL = NONE (0b1111)`, `HA_MUX = IMM`,
`HB_MUX = src2`.

#### Description

Stores `src2` (or `src2_64`) into the host-accessible user buffer (mapped to `DATA_RAM` base `0x0C0`, words 192..207,
`USR[0..15]`) at
`addr`. Does not write to any general-purpose register (`RES_SEL = NONE`).

#### Concrete Numeric Example

```text
Suppose AL = 0xAABBCCDD.
After execution of STU 0x00, AL:
  USER_BUFFER[0x00] <- 0xAABBCCDD
  Flags are unaffected.
```

---

```
================================================================================
SSAV — SAVE STATUS REGISTER TO SHADOW
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **Flags**: None affected.

#### Register Transfer & Datapath Flow

```text
STATUS_SHADOW [7:0] <- STATUS [7:0]
UPC                 <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 101110`. `W = 0` (1 cycle). `RES_SEL = NONE (0b1111)`, `HA_MUX = NONE`, `HB_MUX = NONE`.

#### Description

Saves the current 8-bit STATUS register into an internal shadow register (`status_shadow`). This allows microcode
subroutines to preserve status flags before executing helper operations and restore them later with `SRES`. Does not
alter any register or status flag (`RES_SEL = NONE`).

#### Concrete Numeric Example

```text
Suppose STATUS = 0x11 (ZERO=1, CARRY=1).
After execution of SSAV:
  STATUS_SHADOW <- 0x11
  STATUS remains 0x11 unchanged.
```

---

```
================================================================================
SRES — RESTORE STATUS REGISTER FROM SHADOW
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  | mod | mod | mod | mod | mod | mod |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`S, C, V, U, DF, Z`**: Restored from `STATUS_SHADOW`.
* **`BSY` (bit 7), `ERR` (bit 6)**: System flags protected / unaffected (mask `0x3F` prevents overwriting operational
  engine and error flags).

#### Register Transfer & Datapath Flow

```text
STATUS <- (STATUS & ~0x3F) | (STATUS_SHADOW & 0x3F)
UPC    <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 101111`. `W = 0` (1 cycle). `RES_SEL = NONE (0b1111)`, `HA_MUX = NONE`, `HB_MUX = NONE`.

#### Description

Restores ALU status flags from the internal shadow register using write mask `0x3F` (`0b0011_1111`). Flags `SIGN`,
`CARRY`, `OVERFLOW`, `UNDERFLOW`, `DIFF_SIGN`, and `ZERO` are restored to their shadowed states. System interface flags
`BUSY`
(bit 7) and `ERR` (bit 6) are masked out to preserve execution state. No register is written (`RES_SEL = NONE`).

#### Concrete Numeric Example

```text
Suppose STATUS_SHADOW = 0x11 (ZERO=1, CARRY=1), current STATUS = 0xC0 (BUSY=1, ERR=1).
After execution of SRES:
  Restored with mask 0x3F:
  STATUS <- (0xC0 & ~0x3F) | (0x11 & 0x3F) = 0xC0 | 0x11 = 0xD1 (BUSY=1, ERR=1, CARRY=1, ZERO=1)
  BUSY and ERR remain unchanged.
```

---

### Block 3 (0b011): Control Block

```
================================================================================
JMP addr — UNCONDITIONAL JUMP
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **Flags**: None affected.

#### Register Transfer & Datapath Flow

```text
UPC [9:0] <- INSTR [9:0]  (addr)
```

#### Instruction Word Format

`OPCODE = 011000`. `W = 0` (1 cycle). `RES_SEL = UPC`, `HA_MUX = IMM`, `HB_MUX = n/a`.

#### Description

Forces microprogram control to jump unconditionally to the microcode target address specified in `INSTR[9:0]`.

#### Concrete Numeric Example

```text
Suppose current UPC = 0x015, INSTR[9:0] = 0x040.
After execution of JMP 0x040:
  UPC <- 0x040
  Flags are unaffected.
```

---

================================================================================
JNZ [flag,] addr — JUMP IF NOT ZERO / JUMP IF FLAG SET
================================================================================

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **Flags**: None affected[cite: 7].

The condition operand `flag` can be `ZERO` (default if omitted), `ERR`, `UF`, `VF`, `CF`, `SF`, `DF`, or `BSY`[cite: 7].

#### Register Transfer & Datapath Flow

```text
if flag is omitted or flag == ZERO:
    branch_taken = (STATUS.Z == 0)     # Jump if result is NOT zero (ZF == 0)
else:
    branch_taken = (STATUS[flag] == 1) # Jump if flag bit value is 1 (SET)

if branch_taken:
    UPC [9:0] <- INSTR [9:0]  (addr)
else:
    UPC [9:0] <- UPC [9:0] + 1
```

#### Instruction Word Format

`OPCODE = 011001` (`0x19`). `W = 0` (1 cycle). `RES_SEL = UPC`, `HA_MUX = IMM`, `HB_MUX = NONE`,
`FLAG_COND = flag`[cite: 7].

#### Description

Evaluates a conditional branch to `addr` based on the default `ZERO` flag or an explicit status flag[cite: 7].

> **Condition Evaluation Rules:**
> - **Arithmetic Result (`ZERO` / default):** `JNZ` branches when the result was **Non-Zero** (`ZF == 0`)[cite: 7].
> - **Explicit Status Flags (`SIGN`, `CARRY`, `ERR`, etc.):** `JNZ` branches when the target flag bit **equals 1 (
    SET)**[cite: 7].
>   - `JNZ SIGN, addr` $\rightarrow$ Branches if `SIGN == 1` (Negative)[cite: 7].
>   - `JNZ CARRY, addr` $\rightarrow$ Branches if `CARRY == 1` (Carry/Borrow occurred)[cite: 7].
>   - `JNZ ERR, addr` $\rightarrow$ Branches if `ERR == 1` (Error trapped)[cite: 7].

#### Examples

```text
JNZ 0x032        ; Branches if ZF == 0 (result is non-zero)
JNZ SIGN, 0x010   ; Branches if SF == 1 (number is negative)
JNZ ERR, trap    ; Branches if ERR == 1 (exception occurred)
```

---

================================================================================
JZ [flag,] addr — JUMP IF ZERO / JUMP IF FLAG CLEAR
================================================================================

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **Flags**: None affected[cite: 7].

The condition operand `flag` can be `ZERO` (default if omitted), `ERR`, `UF`, `VF`, `CF`, `SF`, `DF`, or `BSY`[cite: 7].

#### Register Transfer & Datapath Flow

```text
if flag is omitted or flag == ZERO:
    branch_taken = (STATUS.Z == 1)     # Jump if result is ZERO (ZF == 1)
else:
    branch_taken = (STATUS[flag] == 0) # Jump if flag bit value is 0 (CLEAR)

if branch_taken:
    UPC [9:0] <- INSTR [9:0]  (addr)
else:
    UPC [9:0] <- UPC [9:0] + 1
```

#### Instruction Word Format

`OPCODE = 011010` (`0x1A`). `W = 0` (1 cycle). `RES_SEL = UPC`, `HA_MUX = IMM`, `HB_MUX = NONE`,
`FLAG_COND = flag`[cite: 7].

#### Description

Evaluates a conditional branch to `addr` based on the default `ZERO` flag or an explicit status flag[cite: 7].

> **Condition Evaluation Rules:**
> - **Arithmetic Result (`ZERO` / default):** `JZ` branches when the result was **Zero** (`ZF == 1`)[cite: 7].
> - **Explicit Status Flags (`SIGN`, `CARRY`, `ERR`, etc.):** `JZ` branches when the target flag bit **equals 0 (
    CLEAR)**[cite: 7].
>   - `JZ SIGN, addr` $\rightarrow$ Branches if `SIGN == 0` (Positive or zero)[cite: 7].
>   - `JZ CARRY, addr` $\rightarrow$ Branches if `CARRY == 0` (No carry/borrow)[cite: 7].
>   - `JZ ERR, addr` $\rightarrow$ Branches if `ERR == 0` (No error)[cite: 7].

#### Examples

```text
JZ 0x050         ; Branches if ZF == 1 (result is zero)
JZ SIGN, 0x020   ; Branches if SF == 0 (number is positive/zero)
JZ CARRY, 0x015  ; Branches if CF == 0 (no carry out)
```

---

```
================================================================================
DJNZ addr — DECREMENT COUNTER C AND JUMP IF NOT ZERO
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  X  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`Z`**: Set to 1 if updated counter `C == 0`; reset to 0 otherwise.
* **`S`, `C`, `V`, `U`, `ERR`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
C [31:0] <- C [31:0] - 1
STATUS.Z <- (C [31:0] == 0)
if STATUS.Z == 0:
    UPC [9:0] <- INSTR [9:0]  (addr)
else:
    UPC [9:0] <- UPC [9:0] + 1
```

#### Instruction Word Format

`OPCODE = 011011`. `W = 0` (1 cycle). `RES_SEL = UPC`, `HA_MUX = IMM`, `HB_MUX = n/a`.

#### Description

Decrements the loop counter register `C` by 1 and updates `STATUS.Z`. If `C` has not reached zero (`STATUS.Z == 0`),
branches to `addr`. When `C` reaches zero, branches are skipped and execution falls through to `UPC + 1`.

#### Concrete Numeric Example

```text
Suppose C = 3, current UPC = 0x020, INSTR[9:0] = 0x01A.
After execution of DJNZ 0x01A:
  C becomes 2
  C != 0: sets ZERO (Z) to 0
  Branch taken: UPC <- 0x01A
```

---

```
================================================================================
CALL addr — SUBROUTINE CALL
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **Flags**: None affected.

#### Register Transfer & Datapath Flow

```text
CALL_STACK[CSP] [9:0] <- UPC [9:0] + 1
CSP [3:0]             <- CSP [3:0] + 1
UPC [9:0]             <- INSTR [9:0]  (addr)
```

#### Instruction Word Format

`OPCODE = 011100`. `W = 0` (1 cycle). `RES_SEL = UPC`, `HA_MUX = IMM`, `HB_MUX = n/a`.

#### Description

Pushes the address of the next sequential instruction (`UPC + 1`) onto the 16-entry call stack, increments `CSP`, and
jumps to subroutine `addr`. Supports up to 16 nested call levels.

#### Concrete Numeric Example

```text
Suppose current UPC = 0x025, CSP = 0, INSTR[9:0] = 0x080.
After execution of CALL 0x080:
  CALL_STACK[0] <- 0x026
  CSP <- 1
  UPC <- 0x080
  Flags are unaffected.
```

---

```
================================================================================
RET — SUBROUTINE RETURN
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **Flags**: None affected.

#### Register Transfer & Datapath Flow

```text
CSP [3:0] <- CSP [3:0] - 1
UPC [9:0] <- CALL_STACK[CSP] [9:0]
```

#### Instruction Word Format

`OPCODE = 011101`. `W = 0` (1 cycle). `RES_SEL = UPC`, `HA_MUX = n/a`, `HB_MUX = n/a`.

#### Description

Decrements `CSP` and restores microprogram execution flow to the return address popped from the call stack.

#### Concrete Numeric Example

```text
Suppose CSP = 1, CALL_STACK[0] = 0x026.
After execution of RET:
  CSP <- 0
  UPC <- 0x026
  Flags are unaffected.
```

---

```
================================================================================
NOP — NO OPERATION (PIPELINE BUBBLE)
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  -  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **Flags**: All flags unaffected.

#### Register Transfer & Datapath Flow

```text
EXEC_WB     <- 1'b0
STATUS_WREN <- 8'h00
RES_SEL     <- 4'hF (NONE)
EXEC_DONE   <- 1'b1
UPC [9:0]   <- UPC + 1
```

#### Instruction Word Format

`OPCODE = 011110`. `W = 0` (1 cycle). `RES_SEL = NONE`, `HA_MUX = n/a`, `HB_MUX = n/a`.

#### Description

Performs no operation. Used as a 1-cycle pipeline bubble / flush slot on branch mispredictions or when delaying for
multi-cycle memory alignment. Advances `UPC` without modifying any registers or flags.

#### Concrete Numeric Example

```text
After execution of NOP:
  Registers and STATUS remain unchanged.
  UPC advances by 1.
```

---

```
================================================================================
HALT — NORMAL EXECUTION TERMINATION
================================================================================
```

#### Status Flags Affected

```text
  BSY   ERR    S     C     V     U    DF     Z
+-----+-----+-----+-----+-----+-----+-----+-----+
|  0  |  -  |  -  |  -  |  -  |  -  |  -  |  -  |
+-----+-----+-----+-----+-----+-----+-----+-----+
```

* **`BSY`**: Cleared to 0 (operation completed successfully).
* **`ERR`, `Z`, `S`, `C`, `V`, `U`, `D`**: Unaffected.

#### Register Transfer & Datapath Flow

```text
STATUS.BSY <- 1'b0
EXEC_DONE  <- 1'b1  (pulse)
UPC [9:0]  <- 10'd0 (idle loop)
```

#### Instruction Word Format

`OPCODE = 011111`. `W = 0` (1 cycle). `RES_SEL = UPC`, `HA_MUX = n/a`, `HB_MUX = n/a`.

#### Description

Halts the microprogram normally by resetting `STATUS.BSY = 0`, pulses `EXEC_DONE` to notify host or dispatcher that
execution completed successfully, and vectors `UPC` back to the dispatch/idle state.

#### Concrete Numeric Example

```text
After execution of HALT:
  STATUS.BSY <- 0
  EXEC_DONE pulses for 1 cycle.
  UPC vectors to 0x000 (idle state).
```