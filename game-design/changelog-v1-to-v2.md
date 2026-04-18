# v1 → v2 changelog

Each change traces back to the reviewer(s) who raised it. `M` mechanics,
`S` sensitivity, `T` thematic, `A` accessibility, `P` playtest.

## Changes made

| # | Change | Raised by | Notes |
|---|---|---|---|
| 1 | Rename "Settler Republic" → "Garrison Republic", generalise kit | S | Sensitivity review: "Settler" is a political claim, not a neutral archetype. |
| 2 | Add Diaspora as 6th playable faction (non-state role) | S | Adds one non-state perspective; doesn't pretend the game is comprehensive. |
| 3 | Rondel (8 slots, scaling cost) → faction-weighted drafting (6 slots) | M, A | Mechanics: rondel starves asymmetric factions; Accessibility: 8 slots = rules bloat. |
| 4 | Legitimacy: merge internal+regional into one per-region track | A | Collapses the most-confused teach point. |
| 5 | Legitimacy: split into three colours (Religious / Revolutionary / Dynastic) | T | Orthogonal to #4 — same track, contested colour. |
| 6 | Fold Appeal into Diplomacy (variant), Information into Covert Military | A | 8 actions → 6. |
| 7 | Era Cards: draft with Influence bid, not reveal | M | Kills "gotcha" single-draw variance. |
| 8 | Stability bonus: additive → multiplicative, keyed to **minimum** region | S, P | Sensitivity: min not avg to make shared-fate real. Playtest: additive was too small to influence play. |
| 9 | Proxy cap: 2 per region; Revolutionary bypasses once/Era via Shadow Economy | P, T | Playtest: Proxy spam feasible. Theme: sanctioned actor should get *weirder*, not just poorer. |
| 10 | Rentier Rule on Petro-Sovereign | T | The oil curse mechanic v1 gestured at but didn't produce. |
| 11 | Shadow Economy unlock at Sanction step 2 (Revolutionary Republic) | T, P | Theme: sanctions resilience. Playtest bug #5: sanctions drained the same resource that gated Revolutionary's actions, causing mid-game lockout. |
| 12 | Fragmented region state (any region at Stability 0) | T | Fragmentation was modelled only inside Contested Republic in v1; is regional in reality. |
| 13 | Pyrrhic Rule on Military actions | T | The ceiling-of-force dynamic. Overwhelming force should foreclose settlement. |
| 14 | Realignment Offer Era Card | T | Produces Abraham-Accords-style whiplash the rondel could not. |
| 15 | Upheaval mechanic (voluntary + one forced per game) | T | Produces leader-death pivots, 1979-style flips, 1991/2011-style collapses. |
| 16 | Unequal Era length (2/4/3/3/3) | T | Middle stretch is where path dependencies locked in. |
| 17 | Holy Site → Sacred Ground; shared Legitimacy cost to damage | S | Sensitivity review: calling a sacred place "resource tile" is the problem. |
| 18 | Refugee Wave → Displacement with persistent Population tokens, attributed | S | Displacement is not weather. |
| 19 | A/B/C/D blocs → named invented confessional colours | S | "Naming real communities in the spec and hiding behind letters in play is worse than either extreme." |
| 20 | Tech ladder: remove nuclear analogue; drone/cyber/energy/space reachable by any faction | S | Nuclear analogue is the Garrison Republic's private lever dressed as shared. |
| 21 | Remove Outside Power as playable; represent via shared Intervention deck | A, M | One fewer faction, external pressure still present. |
| 22 | Contested Republic reconciliation: binary cliff → 0–8 gradient | M, P | Mechanics: binary cliff is bad design. Playtest: cliff was unreachable after one opponent Appeal. |
| 23 | Appeal protection: cost scales with target's Reconciliation track | P | Playtest bug #1: t=1 Appeal killed a 30-VP private lever. Private levers cannot be opponent-gated cheaply. |
| 24 | Coalition: inverted risk/reward, now raises strife threshold instead of triggering it | P | Playtest bug #4: Coalition as written was a trap. |
| 25 | Safe Harbour: hosted assets add to region's Stability debt; escrow scoring | M, T, P | Mechanics, Theme, Playtest all independently flagged Safe Harbour. |
| 26 | Megaproject payout: Era 5 only, reduced by 1/Era held lead | P | Playtest: Era 3 megaproject (+6) locked the lead for three eras. |
| 27 | Hidden Objective VP cap 15 (was implicitly ~30) | M | Too much hidden scoring sours the post-game. |
| 28 | Era 5 Reckoning: Influence leader seeds mandatory Era 5 crisis | M | Forces endgame engagement without breaking no-elimination. |
| 29 | Map 12 → 10 regions | A | Subsystem-count reduction. |
| 30 | Map resources: add Fragmentation state | T | Already listed #12; included as a map change too. |
| 31 | First-game subset (3 factions), suggested-opening sidebars, revealed Hidden Objectives | A | Single highest-ROI fix per accessibility review. |

## Deliberate non-changes

| # | Did not change | Why |
|---|---|---|
| A | Public attribution of Military — kept | Accessibility flagged it as sacred cow; all reviewers agreed it's load-bearing. |
| B | No military victory — kept | Core to the game's thesis. |
| C | 5 Eras, not 3 or 7 | Theme review explicitly endorsed 5. |
| D | Hidden Objectives retained in advanced play (cap lowered) | Accessibility: drop for game 1 only. |
| E | Did not commit to being a "game about these specific nations, by name" | Sensitivity offered this as an alternative to half-abstraction. v2 takes the other option: stylised names, explicit sources in the rulebook, not coy archetypes. Both are defensible; we picked one. |

## Tensions resolved between reviews

| Tension | Resolution |
|---|---|
| Accessibility wants Legitimacy tracks merged; Theme wants Legitimacy split into three | Orthogonal axes. Merge internal+regional into one per-region track; split that track by three colours. Net: one track with more semantic content. |
| Accessibility says 12 subsystems is too many; Theme adds 5+ rules (Rentier, Shadow Economy, Pyrrhic, Realignment, Upheaval) | Theme additions are folded into existing subsystems (faction modifiers, action rules, Era Card subtypes), not new subsystems. Net subsystem count lower than v1. |
| Mechanics says rondel wrong; Playtest shows rondel worked well enough to generate bugs | Mechanics review wins. The rondel was generating bugs because it starved asymmetric factions of their signature actions (Produce was picked 18% of slots, Military 4 times in 15 rounds). Drafting makes this tunable. |
| Sensitivity says add non-state role; all others silent on faction count | Added. Diaspora is explicitly the role sensitivity asked for. |

## What v2 does not claim to fix

- The design is still a room of states (plus one diaspora) looking at
  populations. A civil-society faction was also proposed; v2 did not add it.
  If playtest shows the Diaspora role works, a Civil Society faction in v3 is
  plausible. If it doesn't, the whole "non-state playable" concept may not
  carry its weight and v3 should revisit.
- Six factions at 3–5 players means not every faction plays every game.
  That's normal for asymmetric games but needs balance testing per 3p / 4p /
  5p.
- The Diaspora's scoring depends heavily on other players' actions, which
  risks feeling like a kingmaker role rather than an agent. This is an open
  question for v3.

## Recommended next playtest

Same four-player setup as the v1 playtest (P1 Petro, P2 Revolutionary, P3
Merchant, P4 Contested) plus one change: the Contested Republic player should
*not* ignore their Reconciliation track this time, because the opponent-gating
bug is fixed. Hypotheses to test:

- Does the faction-weighted draft make Proxy and Appeal viable across
  factions, or did we just move the rondel starvation into a cost table?
- Does the minimum-Stability multiplier cause a single region to become a
  griefing target, or does it produce cooperation?
- Does the Era-5 megaproject payout eliminate the Era-3 lock-in, or just
  move it to Era 5?
- Does the Era Card draft reduce Petro-Sovereign's oil-shock vulnerability to
  the point the Rentier Rule is no longer a real constraint?
