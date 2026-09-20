/-
Copyright 2026 HeliCorgi
SPDX-License-Identifier: Apache-2.0

Formal scope: arithmetic/label bookkeeping for gluing already-audited causal
slabs. These theorems do not assert that a given physical complex satisfies
the hypotheses; Python incidence audits establish those hypotheses.
-/

namespace QCCG

structure FaceIncidence where
  left : Nat
  right : Nat
deriving Repr, DecidableEq

def gluedIncidence (x : FaceIncidence) : Nat :=
  x.left + x.right

def manifoldCodimOneCount (n : Nat) : Prop :=
  n = 1 ∨ n = 2

theorem interface_incidence_two
    (x : FaceIncidence)
    (hleft : x.left = 1)
    (hright : x.right = 1) :
    gluedIncidence x = 2 := by
  cases hleft
  cases hright
  rfl

theorem interface_remains_manifold_codim_one
    (x : FaceIncidence)
    (hleft : x.left = 1)
    (hright : x.right = 1) :
    manifoldCodimOneCount (gluedIncidence x) := by
  right
  exact interface_incidence_two x hleft hright

theorem left_external_incidence_preserved (n : Nat) :
    n + 0 = n := by
  rfl

theorem right_external_incidence_preserved (n : Nat) :
    0 + n = n := by
  induction n with
  | zero => rfl
  | succ n ih =>
      exact congrArg Nat.succ ih

def adjacentSlices (lo hi : Nat) : Prop :=
  hi = lo + 1

theorem adjacent_layer (n : Nat) :
    adjacentSlices n (n + 1) := by
  rfl

theorem two_consecutive_layers (n : Nat) :
    adjacentSlices n (n + 1) ∧
    adjacentSlices (n + 1) (n + 2) := by
  constructor
  · rfl
  · rfl

theorem interface_not_external_after_gluing
    (x : FaceIncidence)
    (hleft : x.left = 1)
    (hright : x.right = 1) :
    gluedIncidence x ≠ 1 := by
  cases hleft
  cases hright
  decide

end QCCG
