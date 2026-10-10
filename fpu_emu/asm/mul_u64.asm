; ==============================================================================
; MUL_U64: 64-bit unsigned integer multiplication
;
; Inputs:
;   Stack: TOS = 64-bit unsigned integer B, NOS = 64-bit unsigned integer A
;
; Outputs:
;   Stack: TOS = (A * B) mod 2^64
;   Status flags:
;     CARRY set to 1 if product > 2^64 - 1 (unsigned overflow)
;     OVERFLOW cleared to 0 by PUSH AX
;     or set on underflow if stack < 4 words (16 bytes).
;
; Register Allocation:
;   AX (AL, AH) : Operand A (NOS), later low/high words of product
;   BX (BL, BH) : Operand B (TOS)
;   CX (CL, CH) : Scratch copy of operand A (CL = A_lo, CH = A_hi),
;                 CH accumulates cross terms (T2 + T1)
;   DX (DL, DH) : DL = overflow tracker, DH = scratch (T1)
;   FX (FL, FH) : Preserved / untouched
; ==============================================================================

USER_MUL_U64:
    CALL POP_TWO_64             ; AX <- A (NOS), BX <- B (TOS)
    XOR DL, DL                  ; DL <- 0 (overflow accumulator)

    ; Check if both A_hi and B_hi are non-zero:
    OR AH, AH
    JZ ZERO, MUL_U64_CHECK_T2   ; If AH == 0, A_hi * B_hi is 0
    OR BH, BH
    JZ ZERO, MUL_U64_CHECK_T2   ; If BH == 0, A_hi * B_hi is 0
    LDI DL, 1                   ; Both AH != 0 and BH != 0: A * B >= 2^64 (overflow)

MUL_U64_CHECK_T2:
    MOV CX, AX                  ; CX <- A (CL = A_lo, CH = A_hi)
    MULU AL, CH, BL             ; {AH, AL} <- A_hi * B_lo
    OR AH, AH                   ; Check if high 32 bits of (A_hi * B_lo) non-zero
    JZ ZERO, MUL_U64_NO_T2_OF
    LDI DL, 1                   ; High word non-zero -> overflow
MUL_U64_NO_T2_OF:
    MOV CH, AL                  ; CH <- T2 = (A_hi * B_lo)_lo

    MULU AL, CL, BH             ; {AH, AL} <- A_lo * B_hi
    OR AH, AH                   ; Check if high 32 bits of (A_lo * B_hi) non-zero
    JZ ZERO, MUL_U64_NO_T1_OF
    LDI DL, 1                   ; High word non-zero -> overflow
MUL_U64_NO_T1_OF:
    MOV DH, AL                  ; DH <- T1 = (A_lo * B_hi)_lo

    ADD CH, CH, DH              ; CH <- T2 + T1
    JZ CARRY, MUL_U64_NO_C1_OF
    LDI DL, 1                   ; Carry out of T2 + T1 -> overflow
MUL_U64_NO_C1_OF:

    MULU AL, CL, BL             ; {AH, AL} <- A_lo * B_lo
    ADD AH, AH, CH              ; AH <- (A_lo * B_lo)_hi + (T2 + T1)
    JZ CARRY, MUL_U64_NO_C2_OF
    LDI DL, 1                   ; Carry out of AH + CH -> overflow
MUL_U64_NO_C2_OF:

    PUSH AX                     ; Push 64-bit product {AH, AL} (clears OVERFLOW and ERR)

    OR DL, DL                   ; Test if overflow occurred
    JZ ZERO, MUL_U64_DONE
    LDI CARRY, 1                ; Overflow occurred: set CARRY = 1
MUL_U64_DONE:
    HALT
