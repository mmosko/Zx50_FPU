; ==============================================================================
; CONV_F64_F32: Narrow IEEE-754 Double-Precision Float to Single-Precision Float
;
; Opcode: 0xCB
;
; Inputs:
;   Stack: TOS = IEEE-754 64-bit double-precision float (X)
;
; Outputs:
;   Stack: TOS = IEEE-754 32-bit single-precision float (net -4 bytes on stack)
;   Status flags:
;     ZERO     = 1 if result is +/-0.0
;     SIGN     = sign bit of result (bit 31)
;     OVERFLOW = 1 if exponent overflows float32 range (produces +/-Inf)
;     UNDERFLOW= 1 if exponent underflows float32 range (produces +/-0.0)
;     ERR      = 1 on Stack Underflow (< 8 bytes)
;
; Register Allocation:
;   AX (AL, AH) : 64-bit operand X, then unpacked mantissa, then 32-bit result
;   EA          : Biased exponent (E64 -> E32 via EXP_SUB EA, 896)
;   DH          : Saved sign bit and float64 high word
;   BL          : Scratch for exponent checks, shifting, and NaN packing
;   C           : Used by NORMALIZE_F32 (LZC leading zero count)
;
; Subroutines Called:
;   POP_ONE_64, NORMALIZE_F32
; ==============================================================================

USER_CONV_F64_F32:
    CALL POP_ONE_64             ; AX <- float64 X (TOS), halts on underflow
    MOV DH, AH                  ; DH[31] <- sign bit
    UNPACK AX, EA               ; EA <- E64 (0..2047), AH <- mant_hi, AL <- mant_lo

    ; Check if E64 == 2047 (NaN or +/-Inf)
    CMP EA, 2047
    JZ ZERO, .f64_f32_special  ; If E64 == 2047: special (NaN or +/-Inf)

    EXP_SUB EA, 896             ; EA <- E64 - (1023 - 127) = E64 - 896
    LSR AX, 29                  ; AL[23:0] <- mantissa (bit 23 = hidden bit)
    MOV AH, DH                  ; AH[31] <- sign bit for NORMALIZE_F32
    CALL NORMALIZE_F32          ; Normalizes, checks limits (V=1/U=1), restores sign, PACK AL, EA
    HALT AL

.f64_f32_special:
    ; Check if fraction is 0 (Inf vs NaN)
    MOV BL, AH
    LSL BL, 12                  ; Clear hidden bit 20
    OR BL, AL                   ; Combine with low fraction
    JZ ZERO, .f64_f32_inf       ; If fraction == 0: +/-Infinity

    ; NaN: convert to float32 NaN
    LSR AX, 29                  ; AL[22:0] <- fraction bits
    MOV BL, AL
    LSL BL, 9                   ; Check if truncated fraction is non-zero
    JNZ ZERO, .f64_f32_nan_pack
    OR AL, 1                    ; Guarantee non-zero NaN fraction
    JMP .f64_f32_nan_pack

.f64_f32_inf:
    XOR AL, AL                  ; Zero fraction for +/-Infinity

.f64_f32_nan_pack:
    LSL AL, 9
    LSR AL, 9                   ; Clear bit 23
    LDI BL, 0xFF
    LSL BL, 23                  ; BL <- 0x7F800000 (NaN/Inf exponent)
    OR AL, BL
    MOV BL, DH
    LSR BL, 31
    LSL BL, 31                  ; BL <- sign bit (0x80000000 or 0)
    OR AL, BL                   ; Insert sign
    HALT AL
