; ==============================================================================
; MUL_INT: Unified Integer Multiplication Subsystem (I32, U32, I64, U64)
;
; Implements:
;   - USER_MUL_I32 (Opcode 0xE0) : 32-bit signed multiplication (A * B mod 2^32)
;   - USER_MUL_U32 (Opcode 0xE1) : 32-bit unsigned multiplication with CARRY on OF
;   - USER_MUL_I64 (Opcode 0xE2) : 64-bit signed multiplication (A * B mod 2^64)
;   - USER_MUL_U64 (Opcode 0xE3) : 64-bit unsigned multiplication with CARRY on OF
;
; Inputs:
;   Stack (32-bit): TOS = 32-bit integer B, NOS = 32-bit integer A
;   Stack (64-bit): TOS = 64-bit integer B, NOS = 64-bit integer A
;
; Outputs:
;   Stack (32-bit): TOS = 32-bit product (A * B) mod 2^32
;   Stack (64-bit): TOS = 64-bit product (A * B) mod 2^64
;
; Status Flags:
;   - USER_MUL_I32 : Updated by MUL AL, BL (ZERO, SIGN, OVERFLOW)
;   - USER_MUL_U32 : CARRY set if product >= 2^32 (AH != 0); OVERFLOW cleared to 0;
;                    ZERO and SIGN updated
;   - USER_MUL_I64 : Updated by final ADD (ZERO, SIGN)
;   - USER_MUL_U64 : CARRY set if product >= 2^64 (unsigned overflow);
;                    OVERFLOW cleared to 0 by PUSH AX
;
; Register Allocation:
;   AX (AL, AH) : 32-bit: Operand A (AL) / product low word (AL) / product high word (AH)
;                 64-bit: Operand A (NOS) / 64-bit product {AH, AL}
;   BX (BL, BH) : 32-bit: Operand B (BL)
;                 64-bit: Operand B (TOS)
;   CX (CL, CH) : 64-bit: Scratch copy of operand A (CL = A_lo, CH = A_hi),
;                 CH accumulates cross terms (T2 + T1)
;   DX (DL, DH) : 64-bit U64: DL = overflow tracker, DH = scratch term T1
;   FX (FL, FH) : Preserved / untouched
;
; Subroutines Called:
;   POP_TWO_32, POP_TWO_64
; ==============================================================================

; ------------------------------------------------------------------------------
; 32-Bit Multiplication Section
; ------------------------------------------------------------------------------
USER_MUL_I32:
    CALL POP_TWO_32             ; AL <- A (NOS), BL <- B (TOS)
    MUL AL, BL                  ; {AH, AL} <- A * B (signed Booth hardware)
    JMP MUL_32_PUSH

USER_MUL_U32:
    CALL POP_TWO_32             ; AL <- A (NOS), BL <- B (TOS)
    MULU AL, BL                 ; {AH, AL} <- A * B (unsigned Booth hardware); VF set if AH != 0
    JZ VF, MUL_32_PUSH          ; If VF == 0 (no overflow), skip setting CARRY
    LDI CARRY, 1                ; High 32-bit product non-zero: set CARRY = 1
    LDI VF, 0                   ; In unsigned mode, VF is cleared to 0

MUL_32_PUSH:
    HALT AL                     ; Push low 32 bits of product

; ------------------------------------------------------------------------------
; 64-Bit Multiplication Section
; ------------------------------------------------------------------------------
USER_MUL_I64:
    CALL POP_TWO_64             ; AX <- A (NOS), BX <- B (TOS)
    MOV CX, AX                  ; CX <- A (CL = A_lo, CH = A_hi)
    MULU AL, CH, BL             ; {AH, AL} <- A_hi * B_lo
    MOV CH, AL                  ; CH <- T2 = (A_hi * B_lo)_lo
    MULU AL, CL, BH             ; {AH, AL} <- A_lo * B_hi
    ADD CH, CH, AL              ; CH <- T2 + T1
    MULU AL, CL, BL             ; {AH, AL} <- A_lo * B_lo
    ADD AH, AH, CH              ; AH <- (A_lo * B_lo)_hi + T1 + T2
    HALT AX                     ; Push 64-bit product {AH, AL}

USER_MUL_U64:
    CALL POP_TWO_64             ; AX <- A (NOS), BX <- B (TOS)
    XOR DL, DL                  ; DL <- 0 (overflow accumulator)

    ; Check if both A_hi and B_hi are non-zero:
    OR AH, AH
    JZ ZERO, .mul_u64_cross
    OR DL, BH                   ; If AH != 0 and BH != 0: A * B >= 2^64 (overflow)

.mul_u64_cross:
    MOV CX, AX                  ; CX <- A (CL = A_lo, CH = A_hi)
    MULU AL, CH, BL             ; {AH, AL} <- A_hi * B_lo
    OR DL, AH                   ; Accumulate high word non-zero into DL
    MOV CH, AL                  ; CH <- T2 = (A_hi * B_lo)_lo

    MULU AL, CL, BH             ; {AH, AL} <- A_lo * B_hi
    OR DL, AH                   ; Accumulate high word non-zero into DL
    MOV DH, AL                  ; DH <- T1 = (A_lo * B_hi)_lo

    ADD CH, CH, DH              ; CH <- T2 + T1
    ADC DL, 0                   ; Accumulate carry into DL

    MULU AL, CL, BL             ; {AH, AL} <- A_lo * B_lo
    ADD AH, AH, CH              ; AH <- (A_lo * B_lo)_hi + (T2 + T1)
    ADC DL, 0                   ; Accumulate carry into DL

    OR DL, DL                   ; Test if overflow occurred (clears CARRY & OVERFLOW to 0)
    JZ ZERO, .mul_u64_done
    LDI CARRY, 1                ; Overflow occurred: set CARRY = 1
.mul_u64_done:
    HALT AX                     ; Push 64-bit product {AH, AL} and halt
