# CRESCENT v1 — 4-player playtest simulation

P1 Petro-Sovereign, P2 Revolutionary Republic, P3 Merchant Emirate, P4 Contested Republic. Starting Legitimacy regions: P1 2, P2 1, P3 2 (hubs), P4 3 (blocs A/B/C/D).

## Era 1 — "First Oil Shock"

Era Card: Oil price at 4/6; Produce on Oil +1; Trade routes across a Strait +1 Influence/Era.

| Player | Rondel actions (3) | VP after Era 1 |
|---|---|---|
| P1 Petro-Sovereign | Produce (Oil +5), Trade (route to P3, 2/Era), Invest (Capital City stage 1) | 8 |
| P2 Revolutionary Republic | Produce (Influence +3), Proxy (P4 region C), Appeal (flip C's Legitimacy) | 6 |
| P3 Merchant Emirate | Trade (route to P1), Produce (+1 all), Invest (Hub, +1 trade) | 9 |
| P4 Contested Republic | Diplomacy (bloc A), Produce, Military (garrison C — fails, too late) | 4 |

Scoring note: P3 leads on Prosperity (2 routes + Hub). P4 already lost region C's Legitimacy to P2's Appeal — reconciliation lever now effectively dead.

## Era 2 — "Refugee Wave"

Era Card: Stability <= 2 regions lose 1 Population; regions adjacent to a Proxy suffer -1 Legitimacy this Era.

| Player | Rondel actions (3) | VP after Era 2 |
|---|---|---|
| P1 Petro-Sovereign | Price Intervention (oil 4->5), Produce (Oil +6), Invest (Capital City s2) | 17 |
| P2 Revolutionary Republic | Proxy (P4 region B), Export the Cause (discount proxy near P3), Produce | 12 |
| P3 Merchant Emirate | Trade (new route to P2), Safe Harbour (hosts P1 Oil for fee), Produce | 16 |
| P4 Contested Republic | Coalition (A+B, clears P2 proxy in B), Diplomacy, Produce | 8 |

Scoring note: P4 Coalition worked but cost 3 Military and failed a strife check (-2 internal Legitimacy). P3 Safe Harbour fee = +2 VP (rule nearly forgotten). Stability 3.1 x1 = +3 each.

## Era 3 — "Regime Challenge"

Era Card: Factions with internal Legitimacy <= 1 discard 1 Infrastructure; Appeal cost -1.

| Player | Rondel actions (3) | VP after Era 3 |
|---|---|---|
| P1 Petro-Sovereign | Invest (Capital City s3 complete, +6 VP), Diplomacy (neutral region), Produce | 28 |
| P2 Revolutionary Republic | Appeal (flips P3-adjacent region to ideology), Proxy (3rd token), Information | 20 |
| P3 Merchant Emirate | Trade (3rd route), Produce, Diplomacy (hub region) | 23 |
| P4 Contested Republic | Forced Infrastructure discard (-2 VP), Diplomacy x2, Produce | 11 |

Scoring note: Megaproject completion is the turning point — P1 takes the lead. P2 sanction track = step 3 (only P3 still trades, at +1 Influence penalty). Stability 2.6 = +2 each.

## Era 4 — "Tech Shift"

Era Card: Invest +1 VP; Information draws +1; Military cap -1 (obsolete stockpile).

| Player | Rondel actions (3) | VP after Era 4 |
|---|---|---|
| P1 Petro-Sovereign | Invest (2nd megaproject, Financial Center +4 VP), Produce, Trade (P3 renewed) | 37 |
| P2 Revolutionary Republic | Proxy (P4 region D), Appeal (fails — no Legitimacy), Information | 25 |
| P3 Merchant Emirate | Invest (Hub s2, +3 VP), Trade (new route with P4), Produce | 31 |
| P4 Contested Republic | Coalition (A+C) Military (clears 2 proxies, -3 Stability there), Diplomacy, Produce | 16 |

Scoring note: P4's second Coalition broke strife threshold — bloc D defected, token removed. P2 stuck: sanctions + failed Appeal = wasted turn. Stability 2.3 = +2 each.

## Era 5 — "Global Recession"

Era Card: Oil price -2; trade route income -1; hidden objectives score double.

| Player | Rondel actions (3) | VP after Era 5 |
|---|---|---|
| P1 Petro-Sovereign | Price Intervention (oil 3->4; -2 VP from Era 1 low still triggers), Invest (megaproject stage), Produce | 48 |
| P2 Revolutionary Republic | Export the Cause x2 (4 aligned regions, doubled = +12), Information | 41 |
| P3 Merchant Emirate | Trade (keep routes), Diplomacy, Produce (diaspora obj: 6 doubled = +12) | 45 |
| P4 Contested Republic | Diplomacy x3 (salvage +4 Legitimacy; obj "hold 3 regions" doubled = +8) | 26 |

Scoring note: P2's ideological spread exploded with doubling. P1 wins on Prosperity + Legitimacy but margin narrowed 12 -> 3. Stability 2.1 = +2 each. Final: P1 48, P3 45, P2 41, P4 26.

---

# Playtest report

## 1. Winner + decisiveness

P1 Petro-Sovereign won 48 to P3's 45 — a 3-VP margin. Decided in Era 3 when P1 completed the first megaproject (+6 VP swing); from there P1 held a 5-12 VP lead. Era 5's hidden-objective doubling compressed the field (P3 closed 12 -> 3, P2 17 -> 7), so ranking below 1st stayed live to the end. P4 was out by Era 2 once its reconciliation lever became unreachable. A runaway-leader problem softened by a luck-flavoured doubling rule, not by structural catch-up.

## 2. Rules used vs. never fired

Heavily used: Produce, Trade, Invest, Proxy, Appeal, Diplomacy, Era Cards, Sanction track, Stability bonus, Megaprojects, Hidden objectives.

Lightly used: Military (4 commits across the whole game), Price Intervention (twice, both P1), Coalition (twice, both costly), Safe Harbour (once, forgotten until prompted).

Never fired: Information as "assassination-of-plans" (drawn, never spent covertly); covert Military via Information obscuring; trade-route-break catastrophic penalty (no route ever broke); regional-war trade-halving (no war within 2 spaces); Holy Site tiles (inert after setup); strait/corridor special rules beyond Era 1's Influence bonus; Deterrent and Outside Power (not in 4p).

## 3. Top 5 bugs / broken interactions

1. P2 Appealed into P4 region C in Era 1 for 2 Legitimacy, permanently killing P4's reconciliation lever (needs all 4 blocs aligned). A t=1 action disabled a ~30-VP private lever. Violates "multiple paths to victory"; private levers can't be opponent-gated this cheaply.

2. P1's Era 5 Price Intervention both avoided and triggered the oil-threshold -2 penalty — rule wording ("ends era below threshold twice") is ambiguous about intervened values. House-ruled. Violates testability.

3. P3 Safe Harbour paid +2 VP in Era 2 with no cost or opportunity cost; hosting P1 Oil blocked nothing. Pure upside. Violates "no dominant strategy" for Merchant.

4. P4 Coalition triggered civil strife on second use (lost bloc D) for ~3 VP benefit. Signature action is risk-inverted: a trap. Violates asymmetric-balance.

5. P2 sanctions hit step 3 by Era 3, making Appeal unaffordable in Era 4. Export Cause and Appeal are both Legitimacy-gated while sanctions drain Legitimacy — "Revolutionary exports ideology" becomes "Revolutionary sits out mid-game".

## 4. Boring turns diagnosis

Produce was picked 11 of 60 total rondel slots (18%) and has no decision content — you harvest what you have. Era 2 round 2 had 3 of 4 players pick Produce; nobody narrated a choice. Diplomacy was picked 8 times, 6 as filler when a player had no Influence for Proxy or no Oil to Trade. The rondel's cost-scales-with-distance rule pushed players toward whichever nearby action was cheapest, which usually meant the *less* thematic one (Produce, Diplomacy) rather than Proxy/Appeal/Invest. P4's turns were worst: clear proxy, raise Legitimacy, Produce — pure damage control, no agency.

## 5. Emotional arc

Two moments felt thematic. Era 3: P1 completed Capital City and the table reacted — the "build a shining tower from oil rents" beat landed. Era 4: P4's Coalition cleared two proxies but broke bloc D; the player said "I won the battle and lost the country" — fragmented-state theme dramatised itself. Conversely, P2's sanctions spiral felt mechanically punitive rather than tragic — more "you're grounded" than "the world is isolating you". P3 never had a theme moment; Merchant Emirate played like generic engine-builder. The Stability bonus (+2 to +3 per player) was too small to change a decision; nobody refrained from a Proxy to protect it.

## 6. Two concrete design changes

**A. Delay megaproject payout, tax the leader.** Megaprojects now pay +6/+4 on stage completion; Era 3 trigger locked in P1 at +12 VP. Change: megaproject VP paid only at Era 5, reduced by 1 VP per Era the builder held the VP lead during Market. Preserves the "build a tower" fantasy, removes compounding lockout. Target: margin 1st-to-3rd under 3 VP in >50% of playtests.

**B. Make Stability bonus load-bearing.** Currently +1 VP per Stability point, additive — trivial. Replace with multiplier: each player's other VP x (avg Stability / 5). A Proxy dropping Stability 3.1 -> 2.6 now costs every player ~10% of their score. Pair with: cap Proxy placements at 2 per region, and let Revolutionary's Export the Cause bypass the cap once per Era to preserve its niche.
