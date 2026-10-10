; ==============================================================================
; DIV_U64: 64-bit unsigned integer division: A / B
;
; Inputs:
;   Stack: TOS = 64-bit unsigned integer B (divisor), NOS = 64-bit unsigned integer A (dividend)
;
; Outputs:
;   Stack: TOS = quotient (A / B)
;   Status flags:
;     ERR and OVERFLOW set if B == 0 (division by zero, aborts without pushing)
;     Updated by final operation (ZERO, SIGN)
;     or set on underflow if stack < 4 words (16 bytes).
;
; Register Allocation:
;   AX (AL, AH) : Dividend A (NOS) / Quotient Q (A / B)
;   BX (BL, BH) : Divisor B (TOS)
;   CX (CL, CH) : Remainder R
;   C           : Loop counter (64 iterations)
;
; Subroutines Called:
;   POP_TWO_64
; ==============================================================================

USER_DIV_U64:
    CALL POP_TWO_64             ; AX <- A (NOS), BX <- B (TOS)
    OR.64 BX, BX                ; Test if divisor B == 0
    JZ ZERO, DIV_U64_DIV_ZERO   ; If B == 0, abort with divide-by-zero

    ; Initialize remainder R = 0 in CX
    XOR.64 CX, CX

    ; Set loop counter C = 64 iterations
    LDI C, 64

DIV_U64_LOOP:
    LSL.64 AX, 1                ; Q << 1, CARRY = old Q[63]
    JNZ CARRY, DIV_U64_Q_CARRY

    ; Path 1: Q[63] was 0
    LSL.64 CX, 1                ; R << 1
    SUB.64 CX, CX, BX           ; R = R - B
    JNZ CARRY, DIV_U64_RESTORE1
    OR AL, 1                    ; R >= B: set Q[0] = 1
    DJNZ DIV_U64_LOOP
    JMP DIV_U64_LOOP_DONE
DIV_U64_RESTORE1:
    ADD.64 CX, CX, BX           ; R < B: restore R = R + B
    DJNZ DIV_U64_LOOP
    JMP DIV_U64_LOOP_DONE

DIV_U64_Q_CARRY:
    ; Path 2: Q[63] was 1
    LSL.64 CX, 1                ; R << 1
    OR CL, 1                    ; R = (R << 1) | 1
    SUB.64 CX, CX, BX           ; R = R - B
    JNZ CARRY, DIV_U64_RESTORE2
    OR AL, 1                    ; R >= B: set Q[0] = 1
    DJNZ DIV_U64_LOOP
    JMP DIV_U64_LOOP_DONE
DIV_U64_RESTORE2:
    ADD.64 CX, CX, BX           ; R < B: restore R = R + B
    DJNZ DIV_U64_LOOP

DIV_U64_LOOP_DONE:
    OR.64 AX, AX                ; Set ZERO and SIGN flags based on quotient
    PUSH AX                     ; Push 64-bit quotient {AH, AL} (clears VF and ERR)
    HALT

DIV_U64_DIV_ZERO:
    LDI ERR, 1
    LDI OVERFLOW, 1
    HALT
