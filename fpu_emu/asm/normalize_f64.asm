; ==============================================================================
; NORMALIZE_F64: Subroutine to normalize and pack an IEEE-754 float64 result
;
; Inputs:
;   AX (64-bit) : Unnormalized mantissa {AH, AL} (unpacked bit 20 of AH is implicit 1)
;   EA (12-bit) : Biased exponent
;   DH (32-bit) : Bit 31 contains desired sign of the result
;
; Outputs:
;   AX (64-bit) : Normalized, packed IEEE-754 float64 result
;   Status flags:
;     Updated by PACK (ZERO, SIGN, OVERFLOW, UNDERFLOW, INEXACT)
;
; Register Allocation:
;   AX (AL, AH) : Mantissa in / packed float64 out
;   EA          : Biased exponent in, updated during normalization
;   DH          : Bit 31 preserves sign, restored to status.SIGN via OR DH, DH
;   C           : Leading zero count (computed by LZC) / left shift amount
;   BL          : Scratch shift count for right shift (NORMALIZE_F64_RIGHT)
;   Status flags:
;     CARRY, ZERO updated during CMP/SUB comparisons
;
; Algorithm:
;   1. LZC AX determines leading zeros of 64-bit mantissa into C.
;   2. If mantissa == 0 (exact cancellation): zero result (XOR AX, AX).
;   3. Normalized position for float64 has implicit leading 1 at bit 52 (bit 20 of AH),
;      which corresponds to 63 - 52 = 11 leading zeros.
;   4. If C < 11: mantissa addition overflowed into bit 53.
;      Shift right by (11 - C), increment exponent EA by (11 - C).
;   5. If C == 11: already normalized.
;   6. If C > 11: subtraction cancellation.
;      Shift left by (C - 11), decrement exponent EA by (C - 11).
;   7. Restore sign bit to status.SIGN via OR DH, DH.
;   8. PACK AX, EA packs mantissa, exponent, and sign into AX.
; ==============================================================================

NORMALIZE_F64:
    LZC AX                              ; C <- leading zero count (0..64)
    JZ ZERO, NORMALIZE_F64_ZERO         ; If AX == 0 (exact cancellation): return zero
    CMP C, 11
    JNZ CARRY, NORMALIZE_F64_RIGHT      ; If C < 11: addition overflow, shift right
    JZ ZERO, NORMALIZE_F64_DONE         ; If C == 11: already normalized

    ; Subtraction cancellation: shift left by (C - 11)
    SUB C, 11                           ; C <- C - 11 (shift distance)
    LSL AX, C                           ; AX <- AX << C
    EXP_SUB EA, C                       ; EA <- EA - C
    JMP NORMALIZE_F64_DONE

NORMALIZE_F64_RIGHT:
    ; Addition overflow: shift right by (11 - C) via ternary SUB
    SUB BL, 11, C                       ; BL <- 11 - C (shift distance)
    LSR AX, BL                          ; AX <- AX >> BL
    EXP_ADD EA, BL                      ; EA <- EA + BL
    JMP NORMALIZE_F64_DONE

NORMALIZE_F64_ZERO:
    XOR AX, AX                          ; Clear mantissa to 0.0

NORMALIZE_F64_DONE:
    OR DH, DH                           ; Restores status.SIGN from bit 31 of DH
    PACK AX, EA                         ; Pack sign, EA, and mantissa into AX
    RET
