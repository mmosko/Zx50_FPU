; ==============================================================================
; CONV_U32_I32 & CONV_I32_U32: In-place checked conversions between U32 and I32
;
; CONV_U32_I32 (0xC6): Range check: sets V=1 if u32 >= 2^31 (bit 31 is 1)
; CONV_I32_U32 (0xC7): Range check: sets V=1 if i32 < 0 (bit 31 is 1)
;
; Inputs:
;   Stack: TOS = 32-bit operand X
;
; Outputs:
;   Stack: TOS = 32-bit operand X (in-place, net 0 bytes on stack)
;   Status flags:
;     ZERO = 1 if X == 0, else 0
;     SIGN = X[31]
;     CARRY = 0
;     OVERFLOW = 1 if X[31] == 1, else 0
;     ERR = 1 on Stack Underflow (< 4 bytes)
;
; Register Allocation:
;   AL          : Popped operand X
;   AH, B, C, D, F : Preserved / untouched
;
; Subroutines Called:
;   POP_ONE_32
; ==============================================================================

USER_CONV_U32_I32:
USER_CONV_I32_U32:
    CALL POP_ONE_32             ; AL <- X (TOS), halts on stack underflow
    PUSH AL                     ; Writeback in-place to TOS
    OR AL, AL                   ; Sets ZERO=(AL==0), SIGN=AL[31], CARRY=0, OVERFLOW=0
    JZ SIGN, CONV_U32_I32_DONE  ; If SIGN == 0 (bit 31 is 0), no overflow -> done
    LDI OVERFLOW, 1             ; If SIGN == 1 (bit 31 is 1), assert OVERFLOW = 1
CONV_U32_I32_DONE:
    HALT
