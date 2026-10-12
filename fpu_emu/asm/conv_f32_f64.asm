; ==============================================================================
; CONV_F32_F64: IEEE-754 Single-to-Double Precision Float Conversion
;
; Opcode 0xC9: CONV_F32_F64 (f32 -- f64)
;   Widening conversion of a 32-bit float to a 64-bit double precision float.
;   Preserves exact numerical values, signs, +/-0.0, +/-Infinity, NaNs, and
;   promotes single-precision subnormals to normalized double-precision floats.
;
; Inputs:
;   Stack: TOS = float32 X (32-bit IEEE-754)
;
; Outputs:
;   Stack: TOS = float64 X (64-bit IEEE-754)
;   Status flags:
;     Updated by PACK / NORMALIZE_F64 (ZERO, SIGN, etc.)
;     or ERR set on stack underflow.
;
; Register Allocation:
;   AX (AL, AH) : 64-bit mantissa accumulator / packed float64 result
;   BL          : Scratch for constructing float64 special exponent (0x7FF00000)
;   DH          : Original float32 copy (DH[31] holds sign bit)
;   EA          : Biased exponent (8-bit f32 -> 11-bit f64)
;
; Subroutines Called:
;   POP_ONE_32, NORMALIZE_F64
; ==============================================================================

USER_CONV_F32_F64:
    CALL    POP_ONE_32                  ; AL <- float32 X (TOS)
    MOV     DH, AL                      ; DH[31] <- sign bit
    UNPACK  AL, EA                      ; EA <- biased exp (0..255), AL <- mantissa, status.SIGN <- sign bit
    JZ      ZERO, .f32_f64_zero         ; If zero (+0.0 / -0.0): return signed 64-bit zero
    CMP     EA, 255                     ; Check for NaN / Infinity
    JZ      ZERO, .f32_f64_special

    ; Check for subnormal float32 (EA == 0, AL != 0)
    CMP     EA, 0
    JZ      ZERO, .f32_f64_subnormal

    ; Normal float32 (1 <= EA <= 254)
    ; Re-bias exponent: EA <- EA - 127 + 1023 = EA + 896
    EXP_ADD EA, 896
    XOR     AH, AH                      ; AH <- 0, AL <- 24-bit mantissa (bit 23 = 1)
    LSL     AX, 29                      ; Shift mantissa into 53-bit position (bit 20 of AH = 1)
    OR      DH, DH                      ; Restore status.SIGN from DH[31]
    PACK    AX, EA                      ; Pack 64-bit float into AX
.f32_f64_push_halt:
    HALT    AX

.f32_f64_zero:
    XOR     AX, AX                      ; AX <- 0
    OR      DH, DH                      ; Restore status.SIGN from DH[31]
    PACK    AX, EA                      ; Pack signed 64-bit zero
    JMP     .f32_f64_push_halt

.f32_f64_subnormal:
    ; Subnormal float32: value is (-1)^S * 2^-126 * (0.frac)
    ; In float64, this is a NORMAL number!
    ; Initial exponent for 2^-126 in float64 bias: -126 + 1023 = 897
    LDI     EA, 897
    XOR     AH, AH
    LSL     AX, 29                      ; Align fraction so bit 23 moves to bit 52 (bit 20 of AH)
    CALL    NORMALIZE_F64               ; Normalizes AX, adjusts EA, restores sign, packs to AX
    JMP     .f32_f64_push_halt

.f32_f64_special:
    ; EA == 255 (NaN or +/-Inf)
    ; Clear bit 23 by shifting left 9, then align fraction to float64 [51:29]
    LSL     AL, 9                       ; Discard bit 23, fraction in AL[31:9]
    XOR     AH, AH
    LSL     AX, 20                      ; Align fraction to AX[51:29]
    LDI     BL, 0x7FF                   ; 2047 (Float64 special exponent [10:0])
    LSL     BL, 20                      ; BL <- 0x7FF00000 (Float64 special exponent)
    OR      AH, BL                      ; Insert exponent into AH[30:20]
    LSR     DH, 31
    LSL     DH, 31                      ; DH <- 0x80000000 if negative, 0 if positive
    OR      AH, DH                      ; Insert sign into AH[31]
    JMP     .f32_f64_push_halt
