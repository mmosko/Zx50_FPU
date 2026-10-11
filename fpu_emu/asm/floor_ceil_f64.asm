; ==============================================================================
; FLOOR_F64 & CEIL_F64: IEEE-754 Double-Precision Rounding Operations
;
; Opcode 0x63: FLOOR_F64 (x -- floor(x))
;   Rounds x to the nearest integer towards -infinity.
;
; Opcode 0x6B: CEIL_F64 (x -- ceil(x))
;   Rounds x to the nearest integer towards +infinity.
;
; Inputs:
;   Stack: TOS = float64 X (64-bit IEEE-754)
;
; Outputs:
;   Stack: TOS = rounded float64 result
;   Status flags:
;     Updated by PACK (ZERO, SIGN, OVERFLOW, UNDERFLOW, INEXACT)
;     or set on underflow if stack < 2 words.
;
; Register Allocation:
;   AX (AL, AH) : TOS operand X, unpacked mantissa, then rounded packed result
;   BX (BL, BH) : Scaled mantissa manipulation / scratch
;   CX (CL, CH) : Truncated mantissa comparison / scratch 64-bit 1
;   DX (DL, DH) : DL = direction & rounding flag (D != S), DH = bit 31 preserves sign
;   FX (FL, FH) : Saved original float64 X
;   EA          : Biased exponent of X (12-bit)
;   EB          : Unbiased exponent (EA - 1023)
;   C           : Shift amount K = 52 - EB (1 <= K <= 52)
;
; Subroutines Called:
;   POP_ONE_64, NORMALIZE_F64
; ==============================================================================

USER_CEIL_F64:
    LDI     DL, 1                      ; DL <- 1 (ceiling mode)
    JMP     COMMON_ROUND_F64

USER_FLOOR_F64:
    LDI     DL, 0                      ; DL <- 0 (floor mode)

COMMON_ROUND_F64:
    CALL    POP_ONE_64                 ; AX <- float64 X (TOS), halts on underflow
    MOV     FX, AX                     ; FX <- original float64 X
    UNPACK  AX, EA                     ; EA <- exponent, AX <- mantissa (bit 52 set), sets ZERO, SIGN
    JZ      ZERO, ROUND_F64_ZERO       ; Return +/-0.0 unchanged

    MOV     DH, FH                     ; DH[31] <- sign of X for NORMALIZE_F64
    JZ      SIGN, .s_done              ; If X is positive (SIGN == 0), DL is already (D != S)
    XOR     DL, 1                      ; If X is negative (SIGN == 1), DL <- D ^ 1 = (D != S)
.s_done:

    EXP_SUB EB, EA, 1023               ; EB <- EA - 1023 (unbiased exponent)
    JNZ     SIGN, ROUND_F64_SMALL      ; If EB < 0 (i.e. EA < 1023, |X| < 1.0)

    CMP     EB, 52
    JZ      CARRY, ROUND_F64_NO_FRAC   ; If EB >= 52 (|X| >= 2^52 or Inf/NaN), return X unchanged

    ; 0 <= EB < 52: number has fractional bits
    LDI     C, 52
    SUB     C, EB                      ; C <- K = 52 - EB (1 <= K <= 52)

    MOV     BX, AX                     ; BX <- original mantissa M
    LSR     BX, C                      ; BX <- floor(M / 2^K)
    MOV     CX, BX
    LSL     CX, C                      ; CX <- floor(M / 2^K) << K = M_truncated
    CMP     AX, CX                     ; Compare original M with M_truncated
    JZ      ZERO, ROUND_F64_NO_FRAC    ; If fractional bits are zero, already integer!

    OR      DL, DL                     ; Test (D != S)
    JZ      ZERO, .round_f64_down      ; If D == S, round towards zero (take M_truncated)

    ; D != S: Round away from zero (BX <- BX + 1)
    XOR     CX, CX
    LDI     CL, 1                      ; CX <- 64-bit 1
    ADD     BX, CX                     ; BX <- floor(M / 2^K) + 1

.round_f64_down:
    LSL     BX, C                      ; BX <- rounded mantissa (scaled back up by 2^K)
    MOV     AX, BX                     ; AX <- rounded mantissa

ROUND_F64_PACK:
    CALL    NORMALIZE_F64              ; Normalizes if carry into bit 53, restores sign, packs into AX
ROUND_F64_EXIT:
    PUSH    AX
    HALT

ROUND_F64_SMALL:
    XOR     AX, AX                     ; AX <- 0.0
    OR      DL, DL                     ; Test (D != S)
    JZ      ZERO, ROUND_F64_PACK       ; If D == S, return signed 0.0

    ; D != S: return signed 1.0
    LDI     EA, 1023
    LDI     AL, 1
    LSL     AX, 52                     ; AX <- 1 << 52 (mantissa for 1.0)
    JMP     ROUND_F64_PACK

ROUND_F64_NO_FRAC:
    OR      FH, FH                     ; Sets SIGN, ZERO=0 from original float
ROUND_F64_ZERO:
    MOV     AX, FX                     ; Restores original float (preserves UNPACK flags for 0.0)
    JMP     ROUND_F64_EXIT
