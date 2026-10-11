; ==============================================================================
; PUSH_CONST: Mathematical Constant Load Handlers (Opcode range 0xA0..0xAF)
;
; Opcodes:
;   0xA0: PUSH_PI_32        0xA1: PUSH_PI_64
;   0xA2: PUSH_E_32         0xA3: PUSH_E_64
;   0xA4: PUSH_LN2_32       0xA5: PUSH_LN2_64
;   0xA6: PUSH_LOG2E_32     0xA7: PUSH_LOG2E_64
;   0xA8: PUSH_LOG2_10_32   0xA9: PUSH_LOG2_10_64
;   0xAA: PUSH_LOG10_2_32   0xAB: PUSH_LOG10_2_64
;   0xAC: PUSH_SQRT2_32     0xAD: PUSH_SQRT2_64
;   0xAE: PUSH_INV_SQRT2_32 0xAF: PUSH_INV_SQRT2_64
;
; Dynamic table load: The dispatcher primes C with (user_opcode & 0x0F).
; Because opcodes are interleaved (even = f32, odd = f64), shifting C left by 1
; directly yields the exact word offset in the CONST table (0, 2, 4, ..., 30).
;
; Inputs:
;   None (stack unchanged prior to push)
;   C : opcode & 0x0F (initialized by dispatcher)
;
; Outputs:
;   Stack: Pushes 32-bit (FL) or 64-bit (FX) constant loaded from CONST ROM
;
; Register Allocation:
;   C  : Dynamic table slot offset ((opcode & 0x0F) << 1)
;   FL : 32-bit constant loaded via LDC FL, CONST, C
;   FX : 64-bit constant loaded via LDC FX, CONST, C
;   A, B, D : Preserved / untouched
; ==============================================================================

.equ PI_F32, 0
.equ PI_F64, 2
.equ E_F32, 4
.equ E_F64, 6
.equ LN2_F32, 8
.equ LN2_F64, 10
.equ LOG2E_F32, 12
.equ LOG2E_F64, 14
.equ LOG2_10_F32, 16
.equ LOG2_10_F64, 18
.equ LOG10_2_F32, 20
.equ LOG10_2_F64, 22
.equ SQRT2_F32, 24
.equ SQRT2_F64, 26
.equ INV_SQRT2_F32, 28
.equ INV_SQRT2_F64, 30

USER_PUSH_PI_32:
USER_PUSH_E_32:
USER_PUSH_LN2_32:
USER_PUSH_LOG2E_32:
USER_PUSH_LOG2_10_32:
USER_PUSH_LOG10_2_32:
USER_PUSH_SQRT2_32:
USER_PUSH_INV_SQRT2_32:
    LSL     C, 1                ; C <- (opcode & 0x0F) * 2 = 32-bit CONST slot
    LDC     FL, CONST, C        ; Load 32-bit float constant dynamically from CONST table
    PUSH    FL                  ; Push 32-bit constant onto operand stack
    HALT

USER_PUSH_PI_64:
USER_PUSH_E_64:
USER_PUSH_LN2_64:
USER_PUSH_LOG2E_64:
USER_PUSH_LOG2_10_64:
USER_PUSH_LOG10_2_64:
USER_PUSH_SQRT2_64:
USER_PUSH_INV_SQRT2_64:
    LSL     C, 1                ; C <- (opcode & 0x0F) * 2 = 64-bit CONST slot
    LDC     FX, CONST, C        ; Load 64-bit double constant dynamically from CONST table
    PUSH    FX                  ; Push 64-bit constant onto operand stack
    HALT

