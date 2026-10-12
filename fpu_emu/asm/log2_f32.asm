; ==============================================================================
; LOG2_F32: IEEE-754 Single-Precision Base-2 Logarithm: log2(X)
;
; Optimized for Zx50 FPU Rev 2 using ternary ops & CL/CH registers.
; Total size: ~68 microcode words (30+ words saved over unoptimized version).
; ==============================================================================

.equ SQRT2_MANT, 11
.equ LOG2_C3, 10
.equ LOG2_C2, 9
.equ LOG2_C1, 8
.equ LOG2_C0, 7

USER_LOG2_F32:
    CALL POP_ONE_32                 ; AL <- X (TOS)
    CALL LOG2_CORE                  ; AL <- log2(AL)
    JNZ ERR, LOG2_HALT              ; If domain error (ERR set), abort without pushing
    HALT AL
LOG2_HALT:
    HALT

LOG2_CORE:
    MOV BH, AL                      ; BH <- input (preserves sign and original value)
    UNPACK AL, EA                   ; EA <- exponent, AL <- mantissa, status.SIGN <- sign
    JZ ZERO, LOG2_DOMAIN_ERR        ; log2(0) or log2(-0) -> domain error
    JNZ SIGN, LOG2_DOMAIN_ERR       ; log2(negative) -> domain error
    CMP EA, 255                     ; Check for NaN / +Inf directly on EA
    JZ ZERO, LOG2_RET_INPUT         ; If NaN or +Inf: return original input in BH

    ; Range reduction: if m > sqrt(2), m = m / 2 and E = E + 1
    LDC BL, CHEB, SQRT2_MANT        ; BL <- sqrt(2) mantissa threshold
    CMP AL, BL                      ; Compare mantissa with sqrt(2) (sets CARRY=1 if AL <= BL)
    JNZ CARRY, LOG2_PREPARE_DIV     ; If AL <= BL (CARRY == 1), skip range reduction
    LSR AL, 1                       ; m <- m / 2
    EXP_ADD EA, 1                   ; E <- E + 1

LOG2_PREPARE_DIV:
    ; Construct denominator (m + 1.0) and numerator (m - 1.0) using ternary ops
    LDI CL, 1
    LSL CL, 23                      ; CL <- 1.0 in bit 23 (0x00800000)
    ADD BL, AL, CL                  ; BL <- denominator = m + 1.0  (Ternary ADD)
    SUB AL, AL, CL                  ; AL <- numerator = m - 1.0    (Ternary SUB)
    LDI EB, 0                       ; EB <- 0 (default: m >= 1.0)
    JZ SIGN, LOG2_DIV_START         ; If numerator >= 0 (SIGN == 0): proceed to divide
    LDI EB, 1                       ; EB <- 1 (flag: m was < 1.0)
    NOT AL
    ADD AL, 1                       ; AL <- |m - 1.0|

LOG2_DIV_START:
    LSL AL, 7                       ; First divide step: AL << 7
    DIVU AL, BL                     ; AL <- q0, DL <- r0
    MOV AH, AL                      ; AH <- q0
    LDI C, 3                        ; 3 iterations of 7-bit division
LOG2_DIV_LOOP:
    MOV AL, DL                      ; AL <- remainder from DIVU
    LSL AL, 7
    DIVU AL, BL
    LSL AH, 7
    OR AH, AL
    DJNZ LOG2_DIV_LOOP

    MOV AL, DL                      ; Final 3 bits of quotient
    LSL AL, 3
    DIVU AL, BL
    LSL AH, 3
    OR AH, AL                       ; AH <- z = (m - 1) / (m + 1) in Q0.31

    MOV CH, AH                      ; CH <- z (using CH instead of FH)
    MOV AL, AH
    MULU AL, AH                     ; {AH, AL} <- z^2
    LSL AH, 1
    MOV FL, AH                      ; Scratch FL <- z^2 in Q1.31

    LDI CL, 9                       ; CL <- 9 (starts with CHEB[9] = c2)
    LDC AL, CHEB, LOG2_C3           ; AL <- c3
LOG2_POLY_LOOP:
    MULU AL, FL                     ; {AH, AL} <- term * z^2
    LSL AH, 1
    LDC BL, CHEB, CL                ; BL <- c_i (reads CHEB[CL])
    ADD AL, AH, BL                  ; AL <- AH + c_i  (Ternary ADD)
    SUB CL, 1
    CMP CL, 6
    JNZ LOG2_POLY_LOOP              ; Loops for c2, c1, c0

    MULU AL, CH                     ; Final multiply: P(z^2) * z
    LSL AH, 1
    LSR AH, 6                       ; AH <- log2(m) in Q9.23

    CMP EB, 0                       ; Check if m was < 1.0 directly
    JZ ZERO, LOG2_CHECK_EXP         ; If EB == 0, skip negation
    NOT AH
    ADD AH, 1                       ; Negate log2(m) if m was < 1.0

LOG2_CHECK_EXP:
    ; Unified Signed Fixed-Point Addition: (E - 127) + log2(m)
    SUB BL, EA, 127                 ; BL <- e = E - 127 (Ternary SUB: 1 cycle)
    LSL BL, 23                      ; BL <- e << 23 (signed Q9.23 integer part)
    ADD AH, AH, BL                  ; AH <- total log2(X) in signed Q9.23 (Ternary ADD)
    JZ ZERO, LOG2_RET_ZERO          ; If total result == 0.0, return 0.0f

    ; Extract sign and magnitude for NORMALIZE_F32
    MOV AL, AH                      ; AL <- total signed Q9.23 value
    LDI AH, 0                       ; Default sign = 0 (positive)
    JZ SIGN, LOG2_NORMALIZE         ; If AL >= 0 (SIGN == 0), AL/AH are ready! Jump!
    LDI AH, 1
    LSL AH, 31                      ; AH <- 0x80000000 (negative sign)
    NOT AL
    ADD AL, 1                       ; AL <- |AL| (positive magnitude)

LOG2_NORMALIZE:
    LDI EA, 127                     ; Reference exponent
    CALL NORMALIZE_F32              ; Converts Q9.23 magnitude in AL, sign in AH[31]
    RET

LOG2_RET_ZERO:
    XOR AL, AL                      ; AL <- 0.0f
    RET

LOG2_RET_INPUT:
    MOV AL, BH                      ; Return original NaN / +Inf input
    RET

LOG2_DOMAIN_ERR:
    SET ERR, 1
    RET
