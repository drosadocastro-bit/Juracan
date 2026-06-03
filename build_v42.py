"""
Build V42 — The Intercontinental Juggernaut.

Synthesis from main_v39.py (gold baseline, 729.9 ELO):
  - Keeps V39's global target evaluation (no hard spatial gates).
  - Applies a SOFT spatial discount to the opportunity bonuses
    (Vulture, Crash, Elimination) inside _best_move_for_source().
  - The discount is gentle (floor at 0.15) so the bot can still
    project power across the entire board ("Intercontinental Reach")
    while slightly preferring nearby targets at equal value.

Key formula:
    spatial_factor = max(0.15, 1.0 - (distance / 160.0) * 0.85)
    
    distance  0 → factor 1.00  (full bonus, local)
    distance 50 → factor 0.73  (still strong reach)
    distance 80 → factor 0.55  (moderate discount)
    distance 141 → factor 0.25  (board diagonal, floor)

This is Option B from our conversation: evolve V41.1's gated logic
into a global soft-discount approach that avoids the "Isolationism Trap".
"""
