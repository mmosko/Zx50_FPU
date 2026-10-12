; ==============================================================================
; LOG2_F64: IEEE-754 Double-Precision Base-2 Logarithm: log2(X)
;
; Inputs:
;   Stack (64-bit): TOS = 64-bit float X
;
; Outputs:
;   Stack (64-bit): TOS = 64-bit float log2(X)
;   Status flags:
;     ERR set if X <= 0 (domain error) or stack underflow
;     Updated by NORMALIZE_F64 (ZERO, SIGN, INEXACT)
;
; Algorithm:
;   1. POP_ONE_64: Unpack X into EA and mantissa AX.
;   2. If X <= 0 (status.ZERO or status.SIGN set): domain error (ERR = 1), abort.
;   3. If X == +Inf or NaN: return X unmodified.
;   4. Unbiased exponent E = EA - 1023 saved to SCR[8].
;   5. Normalized mantissa M in [1.0, 2.0) packed into AX.
;   6. Range reduction: If M >= sqrt(2) (~1.41421356, AH >= 0x3FF6A09E):
;      M <- M / 2.0 (decrement exponent of M), E <- E + 1.
;      Now M in [sqrt(0.5), sqrt(2)] ~ [0.7071, 1.4142].
;   7. Argument transformation: z = (M - 1.0) / (M + 1.0), z^2 = z * z.
;      Stored in SCR[0] (z) and SCR[2] (z^2). |z| <= 0.17157, z^2 <= 0.02944.
;   8. 11-term backward odd series evaluation for ln(M):
;      S = sum_{k=0}^10 z^(2k) / (2k + 1)
;      Backward loop: S <- S * z^2 + 1.0 / (2k + 1) for k = 10 downto 0.
;   9. ln(M) = 2.0 * z * S.
;  10. log2(M) = ln(M) * log2(e) (using CONST table slot 14: LOG2E_F64).
;  11. If E != 0: log2(X) = float64(E) + log2(M).
;
; Scratchpad Allocation (SCR[0..11]):
;   SCR[0..1]  : 64-bit float z / temp
;   SCR[2..3]  : 64-bit float z^2
;   SCR[4..5]  : 64-bit float S (polynomial accumulator)
;   SCR[6]     : 32-bit int D = (2k + 1)
;   SCR[8]     : 32-bit signed int E (unbiased exponent)
;   SCR[10]    : 32-bit loop counter (11 downto 1)
;
; Subroutines Called:
;   POP_ONE_64, ADD_F64_CORE, SUB_F64_CORE, MUL_F64_CORE, DIV_F64_CORE,
;   NORMALIZE_F64
; ==============================================================================

USER_LOG2_F64:
    CALL POP_ONE_64             ; AX <- X from TOS (halts on underflow)
    CALL LOG2_F64_CORE          ; AX <- log2(X)
    JNZ ERR, LOG2_F64_HALT      ; If domain error (ERR=1), abort without pushing
    HALT AX                     ; Push 64-bit result and halt
LOG2_F64_HALT:
    HALT

LOG2_F64_CORE:
    MOV FX, AX                  ; FX <- original input (preserved for NaN / +Inf)
    UNPACK AX, EA               ; EA <- biased exp, AX <- unpacked mantissa
    JZ ZERO, LOG2_F64_ERR       ; log2(0) -> domain error
    JNZ SIGN, LOG2_F64_ERR      ; log2(negative) -> domain error

    ; Check for NaN / +Inf (EA == 2047)
    EXP_SUB EB, EA, 1023
    EXP_SUB EB, EB, 1023
    EXP_SUB EB, EB, 1
    JZ ZERO, LOG2_F64_RET_INPUT ; If NaN or +Inf, return original input

    ; Calculate unbiased exponent E = EA - 1023
    EXP_SUB EA, 1023
    MOV BL, EA
    STO 8, BL                   ; SCR[8] <- E (signed 32-bit int)

    ; Reconstruct normalized float64 M in [1.0, 2.0) with biased exponent 1023
    XOR DH, DH                  ; Sign is positive
    LDI EA, 1023
    CALL NORMALIZE_F64          ; AX <- M as float64

    ; Range reduction: Compare high word AH with sqrt(2) threshold (0x3FF6A09E)
    LDC BL, CONST, SQRT2_F64_HI
    CMP AH, BL                  ; Compare AH with sqrt(2) threshold
    JNZ CARRY, LOG2_F64_NO_REDUCE ; If AH < BL (CARRY=1): M < sqrt(2), skip reduction

    ; M >= sqrt(2): M <- M / 2.0 (decrement exponent) and E <- E + 1
    LDI BL, 1
    LSL BL, 20
    SUB AH, AH, BL              ; Decrement biased exponent of M from 1023 to 1022
    LD BL, 8
    ADD BL, 1
    STO 8, BL                   ; E <- E + 1

LOG2_F64_NO_REDUCE:
    STO 0, AX                   ; SCR[0..1] <- M

    ; Numerator: M - 1.0
    LDC BX, CONST, ONE_F64      ; BX <- 1.0 float64
    CALL SUB_F64_CORE           ; AX <- M - 1.0
    STO 2, AX                   ; SCR[2..3] <- M - 1.0

    ; Denominator: M + 1.0
    LD AX, 0                    ; AX <- M
    LDC BX, CONST, ONE_F64      ; BX <- 1.0 float64
    CALL ADD_F64_CORE           ; AX <- M + 1.0

    ; z = (M - 1.0) / (M + 1.0)
    MOV BX, AX                  ; BX <- denominator
    LD AX, 2                    ; AX <- numerator
    CALL DIV_F64_CORE           ; AX <- z
    STO 0, AX                   ; SCR[0..1] <- z

    ; z^2 = z * z
    MOV BX, AX                  ; BX <- z
    CALL MUL_F64_CORE           ; AX <- z^2
    STO 2, AX                   ; SCR[2..3] <- z^2

    ; Initialize series accumulator S = 0.0 in SCR[4..5]
    XOR AX, AX
    STO 4, AX                   ; SCR[4..5] <- S = 0.0

    ; Initialize odd divisor D = 21 in SCR[6] and loop counter in SCR[10]
    LDI BL, 21
    STO 6, BL                   ; SCR[6] <- D = 21
    LDI BL, 11
    STO 10, BL                  ; SCR[10] <- 11 iterations

LOG2_SERIES_LOOP:
    ; S <- S * z^2
    LD AX, 4                    ; AX <- S
    LD BX, 2                    ; BX <- z^2
    CALL MUL_F64_CORE           ; AX <- S * z^2
    STO 4, AX                   ; SCR[4..5] <- S * z^2

    ; term <- 1.0 / D
    LD AL, 6                    ; AL <- D (unsigned integer 1..21)
    XOR AH, AH
    XOR DH, DH
    LDI EA, 1023
    EXP_ADD EA, 52
    CALL NORMALIZE_F64          ; AX <- float64(D)

    MOV BX, AX                  ; BX <- float64(D)
    LDC AX, CONST, ONE_F64      ; AX <- 1.0 float64
    CALL DIV_F64_CORE           ; AX <- 1.0 / D

    ; S <- S + term
    MOV BX, AX                  ; BX <- term
    LD AX, 4                    ; AX <- S * z^2
    CALL ADD_F64_CORE           ; AX <- S
    STO 4, AX                   ; SCR[4..5] <- S

    ; D <- D - 2
    LD BL, 6
    SUB BL, 2
    STO 6, BL

    ; Loop counter decrement
    LD BL, 10
    SUB BL, 1
    STO 10, BL
    JNZ ZERO, LOG2_SERIES_LOOP

    ; ln(M) = 2.0 * z * S
    LD AX, 4                    ; AX <- S
    LD BX, 0                    ; BX <- z
    CALL MUL_F64_CORE           ; AX <- z * S

    ; Multiply by 2.0 by incrementing exponent
    UNPACK AX, EA
    EXP_ADD EA, 1
    CALL NORMALIZE_F64          ; AX <- ln(M)

    ; log2(M) = ln(M) * log2(e) (CONST slot 14)
    LDC BX, CONST, 14           ; BX <- LOG2E_F64
    CALL MUL_F64_CORE           ; AX <- log2(M)

    ; Check if E == 0
    LD BL, 8
    OR BL, BL
    JZ ZERO, LOG2_F64_DONE      ; If E == 0, log2(X) = log2(M)

    ; Save log2(M) to SCR[0..1]
    STO 0, AX

    ; Convert signed integer E (in BL) to float64 in AX
    XOR DH, DH
    OR BL, BL
    JZ SIGN, .e_positive
    NOT BL
    ADD BL, 1
    LDI DH, 1
    LSL DH, 31                  ; DH[31] = negative sign
.e_positive:
    MOV AL, BL
    XOR AH, AH
    LDI EA, 1023
    EXP_ADD EA, 52
    CALL NORMALIZE_F64          ; AX <- float64(E)

    ; log2(X) = float64(E) + log2(M)
    LD BX, 0                    ; BX <- log2(M)
    CALL ADD_F64_CORE           ; AX <- float64(E) + log2(M)

LOG2_F64_DONE:
    RET

LOG2_F64_RET_INPUT:
    MOV AX, FX                  ; Return original NaN or +Inf
    RET

LOG2_F64_ERR:
    LDI ERR, 1                  ; Assert domain error
    RET
