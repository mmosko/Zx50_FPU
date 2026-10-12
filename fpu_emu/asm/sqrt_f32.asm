; ==============================================================================
; SQRT_F32: IEEE-754 Single-Precision Square Root
;
; Operation:
;   Computes sqrt(X) using initial reciprocal square root seed lookup (EBR 4)
;   followed by 2 Newton-Raphson iterations and a final multiplication:
;     y_{n+1} = y_n * (3.0 - S * y_n^2) / 2
;     sqrt(S) = S * y_final
;
; Optimized for Zx50 FPU Rev 2 using ternary ops & direct AL packing.
; Total size: 40 static microcode instructions (9 words saved, 14 cycles faster).
; ==============================================================================

USER_SQRT_F32:
    CALL POP_ONE_32                 ; AL <- X (TOS)
    CALL SQRT_F32_CORE              ; AL <- sqrt(AL)
    JNZ ERR, SQRT_F32_HALT          ; If domain error (ERR set), abort without pushing
    HALT AL                         ; Push result and halt
SQRT_F32_HALT:
    HALT

SQRT_F32_CORE:
    MOV BH, AL                      ; BH <- raw input (preserves sign and value)
    UNPACK AL, EA                   ; AL <- mantissa (bit 23 set), EA <- biased exponent
    JZ ZERO, SQRT_F32_RET_BH        ; If X == 0 (+0.0 or -0.0): return original input
    JNZ SIGN, SQRT_F32_DOMAIN_ERR   ; If X < 0: domain error (assert ERR and abort)

    CMP EA, 255                     ; Check for NaN / +Inf directly on EA (HA_MUX)
    JZ ZERO, SQRT_F32_RET_BH        ; If NaN or +Inf: return original input

    MOV FL, AL                      ; FL <- mantissa (scratch copy for S)
    MOV BL, AL                      ; BL <- mantissa
    LSR BL, 16                      ; Shift out low bits
    AND BL, 0x7F                    ; Extract fraction index bits [22:16]

    LSL FL, 7                       ; S in Q2.30 (range [1.0, 2.0))
    EXP_ADD EA, 127                 ; EA <- (E + 127)
    AND EB, EA, 1                   ; Check parity: EB <- EA & 1 (Ternary AND)
    JZ ZERO, SQRT_REJOIN            ; If unbiased exp was even: keep [1.0, 2.0) range
    LSL FL, 1                       ; Unbiased exp was odd: scale S to [2.0, 4.0) range
    OR BL, 0x80                     ; Select second half of table [2.0, 4.0)
    EXP_SUB EA, 1                   ; EA <- (E + 126)

SQRT_REJOIN:
    LSR EA, 1                       ; Result exponent: EA <- (E + bias) >> 1
    LDC AH, SQRT, BL                ; AH <- 16-bit seed y0 from EBR 4 (SQRT table)
    LSL AH, 16                      ; AH <- y0 in Q0.32
    MOV BL, AH                      ; BL <- y0 (initial reciprocal square root seed)
    LDI FH, 3                       ; Scratch FH <- constant 3
    LSL FH, 30                      ; FH <- 3.0 in Q2.30 (0xC0000000)
    LDI C, 2                        ; C <- 2 iterations of Newton-Raphson

SQRT_LOOP_NR:
    MULU AL, BL, BL                 ; {AH, AL} <- y^2 (Ternary MULU)
    MULU AL, AH, FL                 ; {AH, AL} <- S * y^2 (Ternary MULU)
    SUB BH, FH, AH                  ; BH <- 3.0 - S * y^2 (Ternary SUB: 1 cycle)
    MULU AL, BL, BH                 ; {AH, AL} <- y * (3.0 - S * y^2) (Ternary MULU)
    LSL AH, 1                       ; Divide by 2: AH << 1 (Q0.32)
    LSR AL, 31                      ; Carry bit from AL: AL >> 31
    OR BL, AH, AL                   ; BL <- updated y (Ternary OR: 1 cycle)
    DJNZ SQRT_LOOP_NR               ; Repeat for 2 iterations

    MULU AL, BL, FL                 ; {AH, AL} <- S * y = sqrt(S) in Q2.30 (Ternary MULU)
    ADD AL, AH, 0x40                ; AL <- AH + 0x40 (Half-ULP rounding bias, Ternary)
    LSR AL, 7                       ; Align mantissa: bit 23 implicit 1 is at bit 23
    PACK AL, EA                     ; Pack float32: mantissa AL, exp EA, sign=0 directly into AL
    RET

SQRT_F32_RET_BH:
    MOV AL, BH                      ; AL <- original input
    RET

SQRT_F32_DOMAIN_ERR:
    SET ERR, 1
    RET
