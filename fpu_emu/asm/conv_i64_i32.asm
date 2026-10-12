; ==============================================================================
; CONV_I64_I32: Narrow 64-bit signed integer to 32-bit signed integer
;
; Inputs:
;   Stack: TOS = 64-bit signed integer X {X_hi, X_lo}
;
; Outputs:
;   Stack: TOS = 32-bit signed integer Y = X_lo (net -4 bytes on stack)
;   Status flags:
;     ZERO = 1 if X_lo == 0, else 0
;     SIGN = X_lo[31]
;     CARRY = 0
;     OVERFLOW = 1 if X not in [-2^31, 2^31 - 1], else 0
;     ERR = 1 on Stack Underflow (< 8 bytes)
;
; Register Allocation:
;   AX (AL, AH) : Popped 64-bit operand X {AH=X_hi, AL=X_lo}
;   BL          : Scratch to hold sign-extension of AL and XOR comparison
;   BH, C, D, F : Preserved / untouched
;
; Subroutines Called:
;   POP_ONE_64
; ==============================================================================

USER_CONV_I64_I32:
    CALL POP_ONE_64             ; AL <- X_lo, AH <- X_hi (halts on stack underflow)
    MOV BL, AL                  ; Copy low word
    ASR BL, 31                  ; BL <- (AL < 0) ? 0xFFFFFFFF : 0
    XOR BL, AH                  ; ZF = 1 if BL == AH (no overflow), 0 if overflow
    PUSH AL                     ; Push 32-bit truncated result to TOS
    JNZ ZERO, CONV_I64_I32_VF   ; If ZF == 0 (BL != AH), overflow occurred -> branch
    OR AL, AL                   ; Set ZERO=(AL==0), SIGN=AL[31], CARRY=0, OVERFLOW=0
    HALT
CONV_I64_I32_VF:
    OR AL, AL                   ; Set ZERO=(AL==0), SIGN=AL[31], CARRY=0, OVERFLOW=0
    SET OVERFLOW, 1             ; Assert OVERFLOW=1
    HALT
