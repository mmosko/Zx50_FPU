; ==============================================================================
; DIV_F64: IEEE-754 Double-Precision Division: A / B
;
; Inputs:
;   Stack: TOS = float64 B (divisor), NOS = float64 A (dividend)
;
; Outputs:
;   Stack: TOS = float64 (A / B)
;   Status flags:
;     ERR set if B == 0 (division by zero)
;     Updated by NORMALIZE_F64 (ZERO, SIGN, OVERFLOW, UNDERFLOW, INEXACT)
;     or set on underflow if stack < 2 words.
;
; Register Allocation:
;   AX (AL, AH) : Dividend mantissa / quotient accumulator / normalized result
;   BX (BL, BH) : Divisor mantissa
;   CX (CL, CH) : Remainder accumulator R
;   DH          : DH[31] = sign(A) ^ sign(B) (result sign for NORMALIZE_F64)
;   EA          : Exponent of A / result exponent (EA - EB + 1022)
;   EB          : Exponent of B
;   C           : Loop counter (54 iterations)
;
; Subroutines Called:
;   POP_TWO_64, DIV_F64_CORE, NORMALIZE_F64
; ==============================================================================

USER_DIV_F64:
    CALL POP_TWO_64             ; AX <- A (NOS), BX <- B (TOS)
    CALL DIV_F64_CORE           ; AX <- A / B
    JNZ ERR, DIV_F64_HALT       ; If divide-by-zero, abort without pushing
    HALT AX                     ; Push 64-bit result and halt
DIV_F64_HALT:
    HALT

DIV_F64_CORE:
    XOR DH, AH, BH              ; DH[31] = sign(A) ^ sign(B) (result sign)
    UNPACK BX, EB               ; Unpack divisor B: EB <- exp_B, BX <- mant_B
    JZ ZERO, DIV_F64_DIV_ZERO   ; If B == 0: trigger divide-by-zero error
    UNPACK AX, EA               ; Unpack dividend A: EA <- exp_A, AX <- mant_A
    JZ ZERO, DIV_F64_ZERO       ; If A == 0: return zero with computed sign

    EXP_SUB EA, EB              ; EA <- exp_A - exp_B
    EXP_ADD EA, 1022            ; EA <- exp_A - exp_B + 1022 (re-bias for 54-bit quotient)

    MOV CX, AX                  ; CX <- initial remainder R = mant_A
    XOR AX, AX                  ; AX <- initial quotient Q = 0
    LDI C, 54                   ; C <- 54 iterations

DIV_F64_LOOP:
    LSL AX, 1                   ; Q <<= 1
    SUB CX, CX, BX              ; R - B
    JNZ CARRY, .div_restore     ; If borrow (R < B), jump to restore
    OR AL, 1                    ; R >= B: set Q[0] = 1
    JMP .div_next               ; Skip restore
.div_restore:
    ADD CX, CX, BX              ; R < B: restore R = R + B
.div_next:
    LSL CX, 1                   ; R <<= 1
    DJNZ DIV_F64_LOOP           ; Decrement C and loop
    JMP NORMALIZE_F64           ; Tail-call normalize and pack

DIV_F64_ZERO:
    XOR AX, AX                  ; Clear mantissa to 0.0
    JMP NORMALIZE_F64           ; Tail-call pack signed zero

DIV_F64_DIV_ZERO:
    LDI ERR, 1                  ; Assert hardware divide-by-zero error
    RET
