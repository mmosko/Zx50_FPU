; ==============================================================================
; DIV_INT: Unified Integer Division Subsystem (DIV_I32, DIV_U32, DIV_I64, DIV_U64)
;
; Operations:
;   USER_DIV_I32 (0xF0) : 32-bit signed integer division (A / B)
;   USER_DIV_U32 (0xF1) : 32-bit unsigned integer division (A / B)
;   USER_DIV_I64 (0xF2) : 64-bit signed integer division (A / B)
;   USER_DIV_U64 (0xF3) : 64-bit unsigned integer division (A / B)
;
; Inputs:
;   32-bit (DIV_I32, DIV_U32):
;     Stack: TOS = 32-bit integer B (divisor), NOS = 32-bit integer A (dividend)
;   64-bit (DIV_I64, DIV_U64):
;     Stack: TOS = 64-bit integer B (divisor), NOS = 64-bit integer A (dividend)
;
; Outputs:
;   32-bit (DIV_I32, DIV_U32):
;     Stack: TOS = 32-bit quotient (A / B) truncated toward zero
;     Status flags:
;       ERR and OVERFLOW set if B == 0 (division by zero, aborts without pushing)
;       Updated by divider / test (ZERO, SIGN)
;       UNDERFLOW set if stack underflow (< 2 words)
;   64-bit (DIV_I64, DIV_U64):
;     Stack: TOS = 64-bit quotient (A / B) truncated toward zero
;     Status flags:
;       ERR and OVERFLOW set if B == 0 (division by zero, aborts without pushing)
;       OVERFLOW set if A == -2^63 and B == -1 (DIV_I64 signed overflow)
;       Updated by quotient magnitude (ZERO, SIGN)
;       UNDERFLOW set if stack underflow (< 4 words)
;
; Register Allocation:
;   32-bit:
;     AL : Dividend A (NOS) / Quotient (A / B)
;     BL : Divisor B (TOS)
;     DL : Remainder (A % B), written by hardware divider
;   64-bit:
;     AX (AL, AH) : Dividend A (NOS) / |A| / Quotient Q (A / B)
;     BX (BL, BH) : Divisor B (TOS) / |B|
;     CX (CL, CH) : Remainder R
;     DL          : Mode & Sign Tracker:
;                     DL[31] = Expected quotient sign (sign(A) ^ sign(B))
;                     DL[0]  = Signed mode flag (1 = signed I64, 0 = unsigned U64)
;     FX (FL, FH) : Scratch register for negation (0 - AX or 0 - BX)
;     C           : Loop counter (64 iterations of restoring division)
;
; Subroutines Called:
;   POP_TWO_32, POP_TWO_64
; ==============================================================================

; ------------------------------------------------------------------------------
; 32-Bit Division Section
; ------------------------------------------------------------------------------
USER_DIV_I32:
    CALL POP_TWO_32             ; AL <- A (NOS), BL <- B (TOS)
    DIV AL, BL                  ; AL <- quotient, DL <- remainder
    JMP DIV_32_PUSH

USER_DIV_U32:
    CALL POP_TWO_32             ; AL <- A (NOS), BL <- B (TOS)
    DIVU AL, BL                 ; AL <- quotient, DL <- remainder

DIV_32_PUSH:
    JNZ ERR, DIV_HALT           ; If divide-by-zero (ERR=1): abort without pushing
    PUSH AL                     ; Push 32-bit quotient
DIV_HALT:
    HALT

; ------------------------------------------------------------------------------
; 64-Bit Division Section
; ------------------------------------------------------------------------------
USER_DIV_I64:
    CALL POP_TWO_64             ; AX <- A (NOS), BX <- B (TOS)
    OR.64 BX, BX                ; Test if divisor B == 0
    JZ ZERO, DIV_64_ZERO        ; Abort on divide-by-zero

    ; DL[31] = sign(A) ^ sign(B), DL[0] = 1 (signed mode flag)
    MOV DL, AH
    XOR DL, BH                  ; DL[31] = expected result sign
    OR DL, 1                    ; DL[0] = 1 (signed mode)

    ; Take |A|: if A < 0, AX = 0 - AX
    OR.64 AX, AX
    JZ SIGN, DIV_64_ABS_A_DONE
    XOR.64 FX, FX
    SUB.64 AX, FX, AX
DIV_64_ABS_A_DONE:

    ; Take |B|: if B < 0, BX = 0 - BX
    OR.64 BX, BX
    JZ SIGN, DIV_64_ABS_B_DONE
    XOR.64 FX, FX
    SUB.64 BX, FX, BX
DIV_64_ABS_B_DONE:
    JMP DIV_64_CORE

USER_DIV_U64:
    CALL POP_TWO_64             ; AX <- A (NOS), BX <- B (TOS)
    OR.64 BX, BX                ; Test if divisor B == 0
    JZ ZERO, DIV_64_ZERO        ; Abort on divide-by-zero
    LDI DL, 0                   ; DL[31] = 0 (positive sign), DL[0] = 0 (unsigned mode)

DIV_64_CORE:
    XOR.64 CX, CX               ; Initialize remainder R = 0 in CX
    LDI C, 64                   ; Set loop counter C = 64 iterations

DIV_64_LOOP:
    LSL.64 AX, 1                ; Q << 1, CARRY = old Q[63]
    JNZ CARRY, DIV_64_Q_CARRY

    ; Path 1: Q[63] was 0
    LSL.64 CX, 1                ; R << 1
    SUB.64 CX, CX, BX           ; R = R - B
    JNZ CARRY, DIV_64_RESTORE
    OR AL, 1                    ; R >= B: set Q[0] = 1
    DJNZ DIV_64_LOOP
    JMP DIV_64_DONE

DIV_64_Q_CARRY:
    ; Path 2: Q[63] was 1
    LSL.64 CX, 1                ; R << 1
    OR CL, 1                    ; R = (R << 1) | 1
    SUB.64 CX, CX, BX           ; R = R - B
    JNZ CARRY, DIV_64_RESTORE
    OR AL, 1                    ; R >= B: set Q[0] = 1
    DJNZ DIV_64_LOOP
    JMP DIV_64_DONE

DIV_64_RESTORE:
    ADD.64 CX, CX, BX           ; R < B: restore R = R + B
    DJNZ DIV_64_LOOP
    ; When DJNZ completes (C == 0), falls through directly to DIV_64_DONE!

DIV_64_DONE:
    AND BL, DL, 1               ; Check signed mode flag in DL[0]
    JZ ZERO, DIV_64_PUSH_U64    ; If unsigned mode (DL[0] == 0): skip sign checks

    ; Signed Mode (DIV_I64):
    OR DL, DL                   ; Test expected result sign in DL[31]
    JNZ SIGN, DIV_64_NEGATE     ; Negate if result should be negative

    ; Expected positive result:
    ; Check for signed overflow (-2^63 / -1):
    ; If positive expected but bit 63 is set, overflow occurred!
    OR.64 AX, AX                ; Check if bit 63 is set
    JZ SIGN, DIV_64_PUSH_POS    ; Valid positive signed result
    PUSH AX                     ; Overflow (-2^63 / -1): push AX then set OVERFLOW
    LDI OVERFLOW, 1
    HALT

DIV_64_PUSH_U64:
    OR.64 AX, AX                ; Set ZERO and SIGN flags for U64 quotient
DIV_64_PUSH_POS:
    PUSH AX                     ; Push 64-bit quotient {AH, AL}
    HALT

DIV_64_NEGATE:
    XOR.64 FX, FX
    SUB.64 AX, FX, AX           ; AX = 0 - AX
    PUSH AX                     ; Push 64-bit quotient {AH, AL}
    HALT

DIV_64_ZERO:
    LDI ERR, 1
    LDI OVERFLOW, 1
    HALT
