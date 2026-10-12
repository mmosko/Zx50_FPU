; ==============================================================================
; SQRT_F64: IEEE-754 Double-Precision Square Root
;
; Operation:
;   Computes sqrt(X) for IEEE-754 64-bit floating-point numbers using a
;   54-iteration restoring binary shift-and-subtract loop.
;
; Inputs:
;   Stack: TOS = float64 X (radicand)
;
; Outputs:
;   Stack: TOS = float64 sqrt(X) (in-place, net 0 bytes on stack)
;   Status flags:
;     ERR = 1 if X < 0 and X != -0.0 (domain error, aborts without pushing)
;     Updated by NORMALIZE_F64 (ZERO, SIGN, INEXACT)
;
; Register Allocation:
;   AX (AL, AH) : Radicand mantissa in / quotient accumulator / packed result out
;   BX (BL, BH) : Raw input X / shifted radicand M / scratch
;   CX (CL, CH) : Remainder accumulator R
;   DX (DL, DH) : Trial test divisor ((Q << 2) | 1)
;   EA          : Biased exponent / unbiased E / halved exponent / re-biased result exp
;   EB          : Exponent scratch / parity check / Inf check
;   FX          : Constant zero register for ADC
;   C           : Loop counter (54 iterations)
;   DH          : Preserves result sign (0 for positive)
;
; Subroutines Called:
;   POP_ONE_64, SQRT_F64_CORE, NORMALIZE_F64
; ==============================================================================

USER_SQRT_F64:
    CALL POP_ONE_64             ; AX <- X (TOS), halts on underflow
    CALL SQRT_F64_CORE          ; AX <- sqrt(AX)
    JNZ ERR, SQRT_F64_HALT      ; If domain error (ERR set), abort without pushing
    HALT AX                     ; Push 64-bit result and halt
SQRT_F64_HALT:
    HALT

SQRT_F64_CORE:
    MOV BX, AX                  ; BX <- raw input X (preserves sign and value)
    UNPACK AX, EA               ; AX <- mantissa (bit 52 set), EA <- biased exponent
    JZ ZERO, SQRT_F64_RET_BX    ; If X == +/-0.0: return original input
    JNZ SIGN, SQRT_F64_DOMAIN_ERR ; If X < 0: domain error (assert ERR and abort)

    ; Check for NaN or +Inf (EA == 2047): 2047 - 1023 - 1023 - 1 == 0
    EXP_SUB EB, EA, 1023
    EXP_SUB EB, EB, 1023
    EXP_SUB EB, EB, 1
    JZ ZERO, SQRT_F64_RET_BX    ; If NaN or +Inf: return original input

    ; Compute unbiased exponent: E = EA - 1023
    EXP_SUB EA, 1023

    ; Check parity: EB <- EA & 1
    AND EB, EA, 1
    JZ ZERO, SQRT_F64_EVEN_EXP  ; If bit 0 == 0, E is even

    ; Unbiased E is odd: decrement E and double radicand mantissa
    EXP_SUB EA, 1               ; Decrement E so it becomes even
    LSL AX, 1                   ; Scale mantissa: M <- M * 2

SQRT_F64_EVEN_EXP:
    ASR EA, 1                   ; EA <- E / 2
    EXP_ADD EA, 1023            ; EA <- (E / 2) + 1023 (re-biased result exponent)

    ; Radicand mantissa in AX is in [2^52, 2^54).
    ; Align mantissa to bit 62 (shift left by 10 bits):
    LSL AX, 10
    MOV BX, AX                  ; BX <- M (radicand)
    XOR CX, CX                  ; CX <- R = 0 (remainder)
    XOR AX, AX                  ; AX <- Q = 0 (root)
    XOR FX, FX                  ; FX <- 0 (constant zero for ADC)
    LDI C, 54                   ; C <- 54 iterations

SQRT_F64_LOOP:
    ; Shift 2 bits of M (BX) into R (CX)
    LSL CX, 1
    LSL BX, 1
    ADC CX, CX, FX
    LSL CX, 1
    LSL BX, 1
    ADC CX, CX, FX

    ; Form test value: DX = (Q << 2) | 1
    MOV DX, AX
    LSL DX, 2
    OR DL, 1

    ; Trial subtraction: R - test
    SUB CX, CX, DX
    JNZ CARRY, .sqrt_restore

    ; R >= test: bit is 1
    LSL AX, 1
    OR AL, 1
    JMP .sqrt_next

.sqrt_restore:
    ; R < test: restore R
    ADD CX, CX, DX
    LSL AX, 1

.sqrt_next:
    DJNZ SQRT_F64_LOOP

    ; Round to nearest even:
    MOV BL, AL
    AND BL, 1                   ; BL <- round bit
    LSR AX, 1                   ; AX <- 53-bit mantissa (implicit 1 at bit 52)
    OR BL, BL
    JZ ZERO, .sqrt_no_round
    XOR BX, BX
    LDI BL, 1
    ADD AX, AX, BX              ; AX <- AX + 1 (round to nearest)
.sqrt_no_round:
    XOR DH, DH                  ; Result sign is always positive (DH = 0)
    JMP NORMALIZE_F64           ; Normalizes, checks overflow to bit 53, and packs

SQRT_F64_RET_BX:
    MOV AX, BX                  ; AX <- original input
    RET

SQRT_F64_DOMAIN_ERR:
    SET ERR, 1
    RET
