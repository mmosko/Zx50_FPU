; ==============================================================================
; EXP2_F64: IEEE-754 Double-Precision Base-2 Exponential: 2^X
;
; Opcode 0x3B: EXP2_F64 (x -- 2^x)
;
; Mathematical Algorithm:
;   1. Argument Reduction:
;      Let X = k + r where k = round(X) is an integer in [-1074, 1023] and
;      r = X - k is in [-0.5, 0.5].
;      Range reduction uses the floating-point rounding constant:
;        MAGIC = 1.5 * 2^52 = 6755399441055744.0 (0x43380000_00000000)
;        Y = X + MAGIC
;        k = Y.lo (low 32 bits of Y is exact signed integer k)
;        k_float = Y - MAGIC
;        r = X - k_float in [-0.5, 0.5]
;
;   2. Transform to natural exponential:
;      u = r * ln(2)
;      where ln(2) is loaded from CONST ROM slot 10 (LN2_F64).
;      Since |r| <= 0.5, |u| <= 0.5 * ln(2) < 0.3466.
;
;   3. High-Precision Horner Evaluation of e^u (13 terms, < 1 ULP error):
;      S_13 = 0
;      For step = 13 down to 1:
;        S <- (u * (1.0 + S)) / float64(step)
;      e^u = 1.0 + S
;
;   4. Exponent Recombination:
;      2^X = e^u * 2^k
;      Unpack e^u: mantissa in AX, exponent EA in {1022, 1023}.
;      new_EA = EA + k.
;      - If new_EA <= 0: subnormal / underflow.
;        Shift AX right by (1 - new_EA), EA = 0.
;        If shift >= 54 -> underflow to +0.0, set UNDERFLOW.
;      - If new_EA >= 2047: overflow -> +inf, set OVERFLOW.
;      - If 1 <= new_EA < 2047: normal -> pack with new_EA.
;
; Inputs:
;   Stack: TOS = 64-bit IEEE-754 float X
; Outputs:
;   Stack: TOS = 64-bit IEEE-754 float 2^X
; Status flags:
;   ERR = 1 on Stack Underflow (< 2 words)
;   OVERFLOW = 1 if 2^X overflows to +inf
;   UNDERFLOW = 1 if 2^X underflows to +0.0
;
; Scratchpad Allocation (SCR[0..63]):
;   SCR[0..1]  : Saved original float64 X
;   SCR[2..3]  : MAGIC constant (0x43380000_00000000)
;   SCR[4]     : Signed 32-bit integer k
;   SCR[6..7]  : u = r * ln(2)
;   SCR[8..9]  : Running sum S
;   SCR[10]    : Loop counter (step = 13 down to 1)
;   SCR[12..13] : Intermediate numerator u * (1.0 + S)
; ==============================================================================

USER_EXP2_F64:
    CALL POP_ONE_64             ; AX <- X (TOS), halts with ERR=1 if SP < 2
    CALL EXP2_F64_CORE          ; AX <- 2^X
    HALT AX

EXP2_F64_CORE:
    STO 0, AX                   ; SCR[0..1] <- X

    UNPACK AX, EA               ; EA <- biased exp, AX <- mantissa, sets ZERO, SIGN
    JZ ZERO, EXP2_F64_RET_ONE   ; 2^0 == 1.0

    ; Check if EA == 2047 (NaN or +/-inf)
    CMP EA, 2047
    JZ ZERO, EXP2_F64_SPECIAL   ; If EA == 2047: special

    ; Check if |X| >= 2048 (EA >= 1034)
    CMP EA, 1034
    JZ CARRY, EXP2_F64_HUGE      ; If EA >= 1034, out of range

    ; --- Compute Y = X + MAGIC ---
    LD AX, 0                    ; AX <- X
    LDC BX, CONST, MAGIC_F64    ; BX <- MAGIC
    CALL ADD_F64_CORE           ; AX <- Y = X + MAGIC

    ; Extract k = Y.lo (signed 32-bit integer)
    STO 4, AL                   ; SCR[4] <- k
    MOV FL, AL                  ; FL <- k

    ; Check k bounds:
    ; If FL is negative (SIGN=1), it cannot overflow (> 1023)
    OR FL, FL
    JNZ SIGN, .exp2_k_negative

    ; FL >= 0: check if FL > 1023
    LDI BL, 1023
    CMP BL, FL                  ; BL - FL: if FL > 1023, borrow out (CARRY=1)
    JNZ CARRY, EXP2_F64_OVERFLOW
    JMP .exp2_k_in_bounds

.exp2_k_negative:
    ; FL < 0: check if FL < -1074
    ADD CL, FL, 1074            ; CL <- FL + 1074
    JNZ SIGN, EXP2_F64_UNDERFLOW ; If FL + 1074 < 0 -> underflow

.exp2_k_in_bounds:

    ; --- Compute k_float = Y - MAGIC ---
    LDC BX, CONST, MAGIC_F64    ; BX <- MAGIC
    CALL SUB_F64_CORE           ; AX <- k_float = Y - MAGIC

    ; --- Compute r = X - k_float ---
    MOV BX, AX                  ; BX <- k_float
    LD AX, 0                    ; AX <- X
    CALL SUB_F64_CORE           ; AX <- r = X - k_float

    ; If r == 0: e^u = 1.0, skip Horner loop entirely
    MOV BL, AH
    LSL BL, 1                   ; Discard sign bit
    OR BL, AL                   ; Combine with AL
    JZ ZERO, EXP2_F64_R_ZERO

    ; --- Compute u = r * ln(2) ---
    LDC BX, CONST, 10           ; BX <- LN2_F64 (0x3FE62E42FEFA39EF)
    CALL MUL_F64_CORE           ; AX <- u = r * ln(2)
    STO 6, AX                   ; SCR[6..7] <- u

    ; --- Initialize Horner Loop for e^u ---
    XOR AX, AX
    STO 8, AX                   ; SCR[8..9] <- S = 0.0
    LDI BL, 13
    STO 10, BL                  ; SCR[10] <- step = 13

EXP2_F64_HORNER_LOOP:
    ; Term: 1.0 + S
    LD AX, 8                    ; AX <- S
    LDC BX, CONST, ONE_F64      ; BX <- 1.0 float64
    CALL ADD_F64_CORE           ; AX <- 1.0 + S

    ; Multiply: u * (1.0 + S)
    LD BX, 6                    ; BX <- u
    CALL MUL_F64_CORE           ; AX <- u * (1.0 + S)
    STO 12, AX                  ; SCR[12..13] <- intermediate numerator

    ; Convert step (SCR[10]) to float64 in BX
    LD AL, 10                   ; AL <- step
    XOR AH, AH                  ; AH <- 0
    XOR DH, DH                  ; Sign is positive
    LDI EA, 1075                ; Initial biased exponent 1075
    CALL NORMALIZE_F64          ; AX <- float64(step)
    MOV BX, AX                  ; BX <- float64(step)

    ; Divide: (u * (1.0 + S)) / step
    LD AX, 12                   ; AX <- numerator
    CALL DIV_F64_CORE           ; AX <- new S
    STO 8, AX                   ; SCR[8..9] <- S

    ; Decrement loop counter
    LD BL, 10                   ; BL <- step
    SUB BL, 1                   ; BL <- step - 1
    STO 10, BL                  ; Update step
    JNZ ZERO, EXP2_F64_HORNER_LOOP

    ; --- Final addition: e^u = 1.0 + S ---
    LD AX, 8                    ; AX <- S
    LDC BX, CONST, ONE_F64      ; BX <- 1.0 float64
    CALL ADD_F64_CORE           ; AX <- e^u

EXP2_F64_APPLY_EXPONENT:
    ; Unpack e^u: AX <- mantissa (bit 52 set), EA <- biased exponent (1022 or 1023)
    UNPACK AX, EA
    MOV BL, EA                  ; BL <- EA
    LD CL, 4                    ; CL <- signed integer k
    ADD BL, BL, CL              ; BL <- new_EA = EA + k (signed 32-bit addition)

    ; 1. Check if BL <= 0 (subnormal or underflow) FIRST!
    OR BL, BL
    JZ ZERO, EXP2_F64_SUBNORMAL
    JNZ SIGN, EXP2_F64_SUBNORMAL

    ; 2. BL >= 1: check overflow (BL >= 2047)
    CMP BL, 2047                ; BL - 2047: if BL >= 2047 -> CARRY = 0
    JZ CARRY, EXP2_F64_OVERFLOW

    ; Normal float64: 1 <= BL < 2047
    MOV EA, BL                  ; EA <- new_EA
    XOR DH, DH                  ; Result is always positive
    CALL NORMALIZE_F64          ; Pack float64 into AX
    RET

EXP2_F64_SUBNORMAL:
    ; BL <= 0: shift amount = 1 - BL
    LDI CL, 1
    SUB CL, CL, BL              ; CL <- 1 - BL
    CMP CL, 54                  ; If shift >= 54, mantissa underflows completely
    JZ CARRY, EXP2_F64_UNDERFLOW
    LSR AX, CL                  ; AX >>= (1 - BL). Since bit 52 shifts into <= 51, exp & sign are 0
    RET

EXP2_F64_R_ZERO:
    ; When r == 0: e^u = 1.0 packed float64 (0x3FF00000_00000000)
    LDC AX, CONST, ONE_F64
    JMP EXP2_F64_APPLY_EXPONENT

EXP2_F64_RET_ONE:
    ; Return 1.0: 0x3FF00000_00000000
    LDC AX, CONST, ONE_F64
    RET

EXP2_F64_SPECIAL:
    LD AX, 0                    ; AX <- original X
    MOV BL, AH
    LSL BL, 12                  ; Discard sign and exponent bits
    OR BL, AL
    JNZ ZERO, EXP2_F64_RET_NAN  ; Fraction != 0: NaN, return original NaN

    ; It is +/- infinity: check sign bit of AH
    OR AH, AH
    JNZ SIGN, EXP2_F64_UNDERFLOW ; -inf -> return +0.0 (sets UNDERFLOW/ZERO)
    ; +inf -> return +inf
    LD AX, 0
    RET

EXP2_F64_RET_NAN:
    LD AX, 0
    RET

EXP2_F64_HUGE:
    ; Check sign of X: if positive -> overflow, if negative -> underflow
    LD AX, 0
    OR AH, AH
    JNZ SIGN, EXP2_F64_UNDERFLOW
    JMP EXP2_F64_OVERFLOW

EXP2_F64_OVERFLOW:
    ; Set EA = 2047, PACK AX, EA sets OVERFLOW flag and produces +inf
    XOR AL, AL
    LDI AH, 1
    LSL AH, 20                  ; AX <- non-zero mantissa with hidden bit
    LDI EA, 2047                ; EA <- 2047 (overflow)
    XOR DH, DH                  ; Sign is positive
    PACK AX, EA                 ; Sets OVERFLOW flag, AX <- +inf
    RET

EXP2_F64_UNDERFLOW:
    ; Set EA = 0, AX != 0, PACK AX, EA sets UNDERFLOW and ZERO flags and produces +0.0
    XOR AL, AL
    LDI AH, 1
    LSL AH, 20                  ; Non-zero mantissa triggers underflow check in _pack_64
    XOR EA, EA
    XOR DH, DH
    PACK AX, EA                 ; Sets UNDERFLOW and ZERO flags, AX <- +0.0
    RET
