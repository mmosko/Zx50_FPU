; ==============================================================================
; MUL_F64: IEEE-754 Double-Precision Floating-Point Multiplication (A * B)
;
; Inputs:
;   Stack (64-bit): TOS = 64-bit float B, NOS = 64-bit float A
;
; Outputs:
;   Stack (64-bit): TOS = 64-bit float (A * B)
;   Status flags:
;     Updated by NORMALIZE_F64 (ZERO, SIGN, OVERFLOW, UNDERFLOW, INEXACT)
;     or set on underflow if stack < 2 words.
;
; Register Allocation:
;   AX (AL, AH) : Operand A / partial product accumulator / normalized result
;   BX (BL, BH) : Operand B mantissa
;   CX (CL, CH) : Operand A mantissa copy (CL = A_lo, CH = A_hi)
;   DX (DL, DH) : DH[31] = result sign (sign(A) ^ sign(B)), DL = scratch P0_hi
;   FX (FL, FH) : Cross product accumulator (P1 + P2), later S1 and P3 cross-term
;   EA          : Exponent of A / product exponent (EA + EB - 1023)
;   EB          : Exponent of B
;
; Subroutines Called:
;   POP_TWO_64, MUL_F64_CORE, NORMALIZE_F64
; ==============================================================================

USER_MUL_F64:
    CALL POP_TWO_64             ; AX <- A (NOS), BX <- B (TOS)
    CALL MUL_F64_CORE           ; AX <- A * B
    PUSH AX                     ; Push 64-bit result
    HALT

MUL_F64_CORE:
    XOR DH, AH, BH              ; DH[31] = sign(A) ^ sign(B) (result sign for NORMALIZE_F64)
    UNPACK BX, EB               ; Unpack B: EB <- exp_B, BX <- mant_B
    JZ ZERO, MUL_F64_ZERO       ; If B == 0: return zero with computed sign
    UNPACK AX, EA               ; Unpack A: EA <- exp_A, AX <- mant_A
    JZ ZERO, MUL_F64_ZERO       ; If A == 0: return zero with computed sign

    EXP_ADD EA, EB              ; EA <- exp_A + exp_B
    EXP_SUB EA, 1023            ; EA <- exp_A + exp_B - 1023 (re-bias)

    MOV CX, AX                  ; CX <- mant_A (CL = A_lo, CH = A_hi)
    MULU AL, CL, BL             ; {AH, AL} <- P0 = A_lo * B_lo
    MOV DL, AH                  ; DL <- P0_hi (preserves DH[31])
    MULU AL, CL, BH             ; {AH, AL} <- P1 = A_lo * B_hi
    MOV FX, AX                  ; FX <- P1
    MULU AL, CH, BL             ; {AH, AL} <- P2 = A_hi * B_lo
    ADD FX, FX, AX              ; FX <- P1 + P2 (FL = P1_lo + P2_lo, FH = P1_hi + P2_hi)
    ADD FL, FL, DL              ; FL <- (P1_lo + P2_lo) + P0_hi
    ADC FH, 0                   ; Propagate carry to FH
    MULU AL, CH, BH             ; {AH, AL} <- P3 = A_hi * B_hi
    ADD AL, AL, FH              ; AL <- P3_lo + FH
    ADC AH, 0                   ; AH <- P3_hi + carry
    LSL AX, 12                  ; AX <- AX << 12 (HI shifted to upper mantissa)
    LSR FL, 20                  ; FL <- FL >> 20 (S1_lo shifted to lower 12 bits)
    OR AL, AL, FL               ; AL <- AL | FL (merge lower 12 bits into mantissa)
    JMP NORMALIZE_F64           ; Tail-call normalize and pack

MUL_F64_ZERO:
    XOR AX, AX                  ; Clear mantissa to 0.0
    JMP NORMALIZE_F64           ; Tail-call pack signed zero
