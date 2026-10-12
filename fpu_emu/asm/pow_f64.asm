; ==============================================================================
; POW_F64: IEEE-754 Double-Precision Power: Y^X = EXP2_F64(X * LOG2_F64(Y))
;
; Opcode 0x2B: POW_F64 (y, x -- y^x)
;
; Inputs:
;   Stack: TOS = 64-bit IEEE-754 float X (exponent)
;          NOS = 64-bit IEEE-754 float Y (base)
;
; Outputs:
;   Stack: TOS = 64-bit IEEE-754 float Y^X
;
; Status flags:
;   ERR = 1 on Stack Underflow (< 4 words), Y < 0.0, or invalid domain (e.g. 0^negative)
;   OVERFLOW = 1 if result overflows to +inf
;   UNDERFLOW = 1 if result underflows to 0.0
;   ZERO = 1 if result is zero
;
; Subroutines Called:
;   POP_TWO_64, LOG2_F64_CORE, MUL_F64_CORE, EXP2_F64_CORE
;
; Register Allocation:
;   AX: Base Y / log2(Y) / product / result
;   BX: Exponent X
;   Scratchpad:
;     SCR[16..17]: Preserved exponent X
; ==============================================================================

USER_POW_F64:
    CALL POP_TWO_64             ; BX <- X (TOS, exp), AX <- Y (NOS, base)

    ; Test if exp (X) == 0.0 or -0.0 -> Y^0 == 1.0
    MOV DL, BH
    LSL DL, 1                   ; Shift out sign bit of X
    OR DL, BL
    JZ ZERO, POW_F64_RET_ONE

    ; Test if base (Y) == 1.0 -> 1^X == 1.0
    ; 1.0 in float64 is AH = 0x3FF00000, AL = 0
    OR AL, AL
    JNZ ZERO, .pow_f64_not_one
    LDC DL, CONST, ONE_F64_HI
    CMP AH, DL
    JZ ZERO, POW_F64_RET_ONE
.pow_f64_not_one:

    ; Test if base (Y) == 0.0 or -0.0
    MOV DL, AH
    LSL DL, 1                   ; Shift out sign bit of Y
    OR DL, AL
    JZ ZERO, POW_F64_BASE_ZERO

    ; Test if base (Y) < 0.0 -> domain error
    OR AH, AH
    JNZ SIGN, POW_F64_DOMAIN_ERR

    ; Save exp (BX) into SCR[16..17]
    STO 16, BX

    ; AX holds base Y (> 0): compute log2(Y)
    CALL LOG2_F64_CORE          ; AX <- log2(Y)
    JNZ ERR, POW_F64_DOMAIN_ERR ; If log2 domain error, propagate

    ; Load exp (X) from SCR[16..17] into BX
    LD BX, 16

    ; Multiply: AX (log2(Y)) * BX (X)
    CALL MUL_F64_CORE           ; AX <- X * log2(Y)

    ; Compute 2^AX
    CALL EXP2_F64_CORE          ; AX <- 2^(X * log2(Y))

    HALT AX

POW_F64_RET_ONE:
    LDC AX, CONST, ONE_F64
    HALT AX

POW_F64_BASE_ZERO:
    OR BH, BH                   ; Test sign of exp X (BH)
    JNZ SIGN, POW_F64_ZERO_NEG_EXP
    XOR AX, AX                  ; 0^positive = 0.0
    HALT AX

POW_F64_ZERO_NEG_EXP:
    LDC AX, CONST, POS_INF_F64
    SET ERR, 1
    SET VF, 1
    HALT AX

POW_F64_DOMAIN_ERR:
    SET ERR, 1
    HALT
