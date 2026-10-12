; ==============================================================================
; SUB_U64: 64-bit unsigned integer subtraction: A - B
;
; Inputs:
;   Stack: TOS = 64-bit unsigned integer B (subtrahend), NOS = 64-bit unsigned integer A (minuend)
;
; Outputs:
;   Stack: TOS = (A - B) mod 2^64
;   Status flags:
;     Updated by SUB AX, BX (ZERO, SIGN, CARRY)
;     OVERFLOW cleared to 0 by PUSH AX
;     or set on underflow if stack < 4 words.
;
; Register Allocation:
;   AX (AL, AH) : Operand A (NOS), later difference (A - B)
;   BX (BL, BH) : Operand B (TOS)
;   D, F        : Preserved / untouched
;
; Subroutines Called:
;   POP_TWO_64
; ==============================================================================

USER_SUB_U64:
    CALL POP_TWO_64             ; AX <- A (NOS), BX <- B (TOS)
    SUB AX, BX                  ; AX <- A - B (sets CARRY on borrow out)
    LDI VF, 0                   ; Clear VF to 0 in unsigned mode
    HALT AX                     ; Push 64-bit result {AH, AL}
