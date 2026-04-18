# CRESCENT — v2 design spec

A Eurogame for 3–5 players, 90–150 min, on the structural dynamics of the
Middle East, 1975–2025. v2 is a response to five parallel reviews of v1
(mechanics, sensitivity, theme, accessibility, playtest). See
`changelog-v1-to-v2.md` for the full trace of what changed and why.

## Design principles (revised)

- Not archetypal in the v1 sense. v1 half-abstracted; v2 is explicit about what
  it is. The faction names are stylised, the flavour is not. Sources in the
  rulebook.
- No player elimination. No military victory condition.
- The Eurogame tensions (indirect conflict, multi-track scoring, resource
  interdependence) are load-bearing. The conflict-sim chrome is pruned back.
- One non-state playable role.
- Six active subsystems, not twelve. Everything v1 added as a separate
  subsystem that could be folded into an existing one has been folded.

## Factions (6; 3-faction starter subset marked *)

Each faction has one starting profile, one signature action, one structural
constraint, and one private scoring lever. No "special-action-plus-vulnerability-
plus-private-lever" triple-stack from v1.

1. **The Petro-Sovereign*** — Gulf monarchy with oil rents and megaprojects.
   - +2 Oil income. Rentier Rule: while Oil income ≥ 4, Diplomacy and
     institutional Invest cost +1.
   - Signature: *Price Intervention* — shift global oil price one step, once
     per Era.
   - Lever: Megaprojects. Pays at Era 5, reduced by 1 VP per Era the builder
     held the overall VP lead at Market.

2. **The Revolutionary Republic** — ideological exporter under sanctions.
   - +2 Influence income. Sanction track ratchets each Era.
   - Signature: *Export the Cause* — place an Aligned token at discount.
   - Lever: Aligned regions score end-Era. **Shadow Economy** unlocks at
     Sanction step 2: the sanctioned player can convert Oil→Influence at a
     black-market rate and place Proxies at a further discount, bypassing the
     per-region Proxy cap once per Era.

3. **The Merchant Emirate*** — trade hub / soft power.
   - +1 of each resource; low Military cap.
   - Signature: *Safe Harbour* — host other players' assets at a fee.
     **Hosted assets count toward this region's Stability debt** — hosting is
     not free.
   - Lever: Escrow scoring. Hub scores VP proportional to the *total value*
     of assets hosted, not just fees.

4. **The Contested Republic** — fragmented state with internal balance.
   - Starts with four confessional/regional blocs, each named (invented
     names, not A/B/C/D, not real-world labels). Blocs have distinct home
     regions and distinct political colours (Religious / Revolutionary /
     Dynastic), which matters for Legitimacy scoring.
   - Signature: *Coalition* — merge two blocs for one round. **Revised:**
     Coalition grants a bonus action *and* raises the strife threshold for
     that Era by +1 (i.e. it is actually a lever, not a trap).
   - Lever: Reconciliation is a gradient track (0–8), not a binary cliff.
     End-Era VP scales; perfect reconciliation is the top of the curve, not
     the only payout.
   - **Protection:** Appeal actions by others against this faction's home
     regions cost the Appealer Legitimacy equal to the faction's current
     Reconciliation track. Private levers cannot be opponent-gated for
     cheap on turn 1.

5. **The Garrison Republic*** — technologically advanced, diplomatically
   constrained. (Renamed from v1's "Settler Republic.")
   - +2 Tech. Highest Military cap. Regional Legitimacy caps its trade
     reach.
   - Signature: *Deterrent* — at Legitimacy cost, mark a region as
     "deterred"; hostile actions into it cost +1 Influence for one Era.
   - Lever: Tech ladder (drone / cyber / energy / space). Reachable by any
     faction with sufficient Tech, not just this one. **No nuclear
     analogue.**
   - **Pyrrhic Rule:** every Military action against a region permanently
     reduces the maximum Legitimacy the attacker can ever hold in that
     region. Force forecloses settlement.

6. **The Diaspora** — transnational network, no home region. (New in v2.)
   - Scores from remittances, advocacy, and moving Population tokens between
     regions.
   - Signature: *Advocacy* — spend Influence to move a regional Legitimacy
     track one step toward whichever political colour the Diaspora owns.
   - Structural constraint: no Military, no Production; lives entirely on
     Trade, Influence, and other players' actions.
   - Lever: Population tokens the Diaspora has moved score end-Era if the
     destination region's Stability ≥ 3.

(v1's "Outside Power" is removed as a playable faction. External great-power
pressure is now a shared Intervention deck — see Era Cards.)

## Resources (5, same as v1)

Oil, Influence, Legitimacy, Military, Information.

## Legitimacy (redesigned)

Legitimacy is a single per-region track, with **three colours**: Religious,
Revolutionary, Dynastic/Nationalist. A region has a colour and a holder; both
can shift. Each faction scores end-game only from regions held in its native
colour(s), but can *suppress* other colours through Appeal.

- Petro-Sovereign: Dynastic.
- Revolutionary Republic: Revolutionary.
- Merchant Emirate: Dynastic or Civic (its own small fourth colour, harder to
  shift).
- Contested Republic: multi-colour; scores from any of its blocs' colours.
- Garrison Republic: Civic/Nationalist.
- Diaspora: cannot hold Legitimacy, but can *move* a region's colour by one
  step per Advocacy action.

This replaces v1's two-track system (internal + regional) with a single track,
and replaces v1's undifferentiated Legitimacy with a colour contest. Both
accessibility and theme reviews flagged this; the fix is one change that
addresses both.

## Map

Hex/area board of 10 regions (reduced from 12) around an inland basin. Each
region has Stability (0–5), a Legitimacy track with a colour and holder,
resource tiles, and — new in v2 — a **Fragmentation** state. Any region whose
Stability hits 0 flips to Fragmented: it stops yielding resources, but any
faction can place Proxies there at half cost and the region pays +1 Influence
per Proxy end-Era. Fragmentation persists until a faction spends 3 Diplomacy
actions to restore it.

Resource tiles: Oil, Trade, Population. **Sacred Ground** replaces v1's "Holy
Site" — cannot be harvested, gates Legitimacy-colour adjustments, and any
Military action that damages a Sacred Ground region costs all factions 2
Legitimacy (shared penalty for desecration).

## Turn structure: 5 Eras, unequal length

Per theme review, not all decades weigh equally.

- Era 1: 1970s — 2 rounds.
- Era 2: 1980s–90s — 4 rounds. (The path-dependency era.)
- Era 3: 2000s — 3 rounds.
- Era 4: 2010s — 3 rounds.
- Era 5: 2020s — 3 rounds.

Total 15 rounds, same as v1, but weighted toward the middle stretch.

## Era Cards: draft, not reveal

Start of each Era, three Era Cards are revealed. Players bid Influence in
reverse-score order to choose which is active. Remaining cards enter a
side track as "latent" modifiers that can be triggered by Realignment or
Upheaval. This kills the "gotcha single-draw" problem and gives the trailing
player a lever.

Era Card subtypes:

- **Structural pressures** (Oil Shock, Global Recession, Tech Shift).
- **Realignment Offers**: each Era, one random pair of factions may consent to
  a Realignment — wipes prior hostility, unlocks a joint action, costs each
  one Proxy relationship. Realignments feel sudden because they are.
- **Upheaval**: one Era Card per game forces an Upheaval on a random faction
  (leader death, revolution, collapse). Additionally, each faction may
  *voluntarily* trigger Upheaval once per game — reset signature action,
  swap private lever, pay a Legitimacy penalty.
- **Displacement** (replaces v1 "Refugee Wave"): moves Population tokens
  persistently to adjacent regions, does not auto-revert. The tokens remain on
  the board and attribute to whichever faction's action triggered them.

## Action selection: faction-weighted drafting

v1's 8-slot rondel is replaced by 6 shared action slots drafted in turn order
set by **ascending Legitimacy** (least-legitimate picks first). Each slot has a
base cost plus a per-faction modifier printed on the faction board. This
preserves asymmetry inside the selection mechanism and makes catch-up a rule,
not a hope.

The six actions:

1. **Produce** — harvest resources.
2. **Trade** — open a trade route; bilateral dependency.
3. **Invest** — infrastructure, tech, megaprojects.
4. **Proxy** — place a Proxy token (capped 2 per region; Revolutionary
   bypasses once per Era via Shadow Economy).
5. **Diplomacy** (with optional **Appeal** variant at +1 cost) — raise
   Legitimacy, sign non-aggression, or (Appeal) shift a region's Legitimacy
   colour.
6. **Military** (with optional **Covert** variant paid in Information) —
   commit Military publicly or covertly. Public Military triggers Pyrrhic
   Rule and Stability loss; Covert avoids Pyrrhic but risks exposure.

v1's separate Information action is folded into the Covert variant. v1's
separate Appeal action is folded into Diplomacy.

## Victory

End of Era 5:

- **Prosperity VP** — infrastructure, trade routes, megaprojects (megaproject
  payout at Era 5, leader-taxed).
- **Legitimacy VP** — regions held in your native colour(s).
- **Influence VP** — Aligned regions, Advocacy moves.
- **Hidden Objective VP** — capped at 15. Revealed for first-game subset.
- **Shared Stability bonus** — now **multiplicative**, keyed to **minimum**
  regional Stability. Each player's other VP × (minimum regional Stability /
  5). A single collapsed region drags everyone.

## Era 5 Reckoning

At end of Era 4, the faction leading on Influence VP seeds a mandatory crisis
— forced Proxy resolution, sanction detonation, or trade-route audit — that
all players must respond to during Era 5. Forces endgame engagement without
breaking no-elimination, and routes leader-suppression through mechanics, not
table talk.

## First-game experience

- Starter subset: Petro-Sovereign, Merchant Emirate, Garrison Republic.
- Revolutionary Republic, Contested Republic, Diaspora unlocked game two.
- Hidden Objectives revealed to the table for game one.
- Per-faction "suggested opening" sidebars, Spirit Island style.
- Teach target: 35 min (down from v1's realistic 45–55).

## What v2 still tries to dramatise

All eight dynamics the theme review asked for:

| Dynamic | v2 mechanism |
|---|---|
| Oil curse | Rentier Rule |
| Sanctions resilience | Shadow Economy unlock at step 2 |
| Proxy warfare | Proxy + Stability multiplier (keyed to minimum) + attribution |
| Legitimacy competition | Three-colour Legitimacy |
| Hub strategy | Merchant Emirate escrow scoring + Safe Harbour debt |
| Fragmentation | Region-level Fragmented state |
| Ceiling of force | Pyrrhic Rule |
| Normalisation whiplash | Realignment Offer + Upheaval |

## Open questions for v3

1. Is 6 factions playable at 3–5, or does the Diaspora need a separate
   solo/2p variant?
2. Does the Reconciliation gradient actually fix the Contested Republic's v1
   binary cliff at the table, or does it just smooth it?
3. Is minimum-Stability scoring too punishing — does one griefer collapse
   everyone's game?
4. Does faction-weighted drafting teach cleanly, or does it move the asymmetry
   complexity from the faction board onto the draft?
5. Is the Diaspora's dependence on other players' actions a fun position or a
   kingmaker role?
6. Does v2 still have twelve subsystems with the chrome renamed, or did
   consolidation actually land?
