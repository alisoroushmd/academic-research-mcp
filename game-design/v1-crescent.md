# CRESCENT — v1 design spec

A Eurogame for 3–5 players, 90–150 min, inspired by the structural dynamics of
Middle Eastern geopolitics, 1975–2025. Designed to reward long-horizon thinking,
punish short-term military adventurism, and expose the player to the
trade-offs that real regional actors navigate (legitimacy vs. control,
prosperity vs. ideology, sovereignty vs. alliance).

Explicit design principles:
- No direct mapping to real nations. Archetypal factions only. The map is a
  stylised basin, not a political map. Goal: structural insight, not simulation
  of specific tragedies.
- No player elimination. No military victory condition.
- Indirect conflict (markets, legitimacy, proxies) dominant; direct conflict
  rare and costly.
- Multiple paths to victory; no dominant strategy.

## Factions (asymmetric)

Each faction has (a) a unique starting resource mix, (b) one special action, (c)
one structural vulnerability, (d) one private victory lever.

1. **The Petro-Sovereign** — oil-rich monarchy archetype.
   - +2 Oil income, -1 Legitimacy baseline.
   - Special: "Price Intervention" — shift global oil price 1 step.
   - Vulnerability: Loses 2 VP if oil price ends era below threshold twice.
   - Private lever: megaproject cards (convert Oil to prestige VP).

2. **The Revolutionary Republic** — ideological exporter archetype.
   - +2 Influence income, cannot trade with two specific factions.
   - Special: "Export the Cause" — place a Proxy token abroad at discount.
   - Vulnerability: Sanction track ratchets each era.
   - Private lever: ideological alignment in foreign regions scores end-era VP.

3. **The Merchant Emirate** — trade hub / soft power archetype.
   - +1 of every resource, low military cap.
   - Special: "Safe Harbour" — host other players' assets for a fee.
   - Vulnerability: Any regional war within 2 spaces halves trade income.
   - Private lever: diaspora and hub cards.

4. **The Contested Republic** — fragmented state / proxy battlefield archetype.
   - Starts with internal Faction tokens (Sunni, Shia, Secular, Kurdish-analogue
     — abstracted as A/B/C/D blocs). Must maintain balance or trigger civil
     strife.
   - Special: "Coalition" — temporarily merge two blocs for a big action.
   - Vulnerability: Other players can legally place Proxy tokens in its regions.
   - Private lever: reconciliation track — huge VP if all 4 blocs end aligned.

5. **The Settler Republic** — technologically advanced, diplomatically
   isolated archetype.
   - +2 Tech, starts with highest Military cap, -2 Legitimacy baseline.
   - Special: "Deterrent" — discourage attacks at a Legitimacy cost.
   - Vulnerability: Regional Legitimacy score caps its trade partners.
   - Private lever: Tech ladder (nuclear-analogue, drone, cyber, energy).

(Optional 6th: **The Outside Power** — plays with different action economy,
represents extra-regional superpower pressure. Recommended as advanced variant.)

## Resources

- **Oil** — tradable commodity, global price, volatile.
- **Influence** — spent to place Proxy tokens, buy events.
- **Legitimacy** — internal (your own track) and regional (each region has one).
  Gates many actions; cheap to lose, slow to gain.
- **Military** — capped per faction. Expended when used, not recovered freely.
- **Information** — asymmetric-info token, hidden. Spent for intelligence
  actions, assassination-of-plans, and hidden objectives.

## Map

Hex/area board of ~12 regions around an inland basin. Each region has:
- A **Stability track** (0–5). Low stability = cheaper proxy play, lower
  resource yield, spillover risk.
- A **Legitimacy holder** (which faction, if any, is the recognised authority).
- **Resource tiles** (Oil, Trade, Population, Holy Site).
- **Adjacency** — some regions are "straits" or "corridors" with special rules.

## Turn structure

The game runs **5 Eras** (≈ decades). Each Era:
1. **Era Card reveal** — a structural pressure that lasts the whole era
   (e.g., Oil Shock, Refugee Wave, Tech Shift, Regime Challenge, Global
   Recession). Modifies costs and scoring.
2. **3 Rounds of action selection** via a shared **rondel** of 8 action
   categories. Rondel cost scales with how far you advance, creating
   tempo-vs-flexibility tension.
3. **Market phase** — oil price resolves, trades execute, sanctions tick.
4. **Era scoring** — partial VP from legitimacy, proxies, megaprojects,
   hidden objectives.

## The 8 rondel actions

1. **Produce** — harvest resources from controlled tiles.
2. **Trade** — open a trade route; sets bilateral income and creates a
   dependency (both sides lose if route breaks).
3. **Invest** — build infrastructure / megaproject / tech.
4. **Proxy** — place a Proxy token in a region; destabilises it.
5. **Diplomacy** — raise your regional Legitimacy; sign non-aggression.
6. **Military** — move/commit Military. All uses are **publicly attributed**
   unless you pay Information to obscure.
7. **Information** — draw Info tokens, look at hidden objectives, stage covert
   ops.
8. **Appeal** — use media/religious/ideological action to shift another
   region's Legitimacy holder, at a Legitimacy cost to yourself.

## Core tensions (the "why it's a Eurogame")

- **Legitimacy paradox**: Military gives you control *now* but degrades
  regional Stability, which degrades everyone's income including yours.
- **Oil dependency**: The obvious resource strategy is also the most
  vulnerable to Era Cards.
- **Proxy trap**: Proxies are cheap power projection but every Proxy in a
  region lowers Stability, and Stability affects *your* trade income too.
- **Attribution**: Public actions are cheap, covert actions cost Information.
  The market tracks who did what.
- **Coalition fragility**: Trade routes score well but break catastrophically
  when a partner is attacked.

## Victory

End of Era 5, sum of:
- **Prosperity VP** — infrastructure, trade routes, megaprojects.
- **Legitimacy VP** — regions where you hold Legitimacy.
- **Influence VP** — aligned proxies, ideological spread.
- **Hidden Objective VP** — per-faction private lever.
- **Stability bonus** — every player scores VP equal to average regional
  Stability × a multiplier. (Creates a shared-fate incentive against
  runaway instability.)

Typical winning score: ~60–80 VP, with no single category above ~30.

## What this design tries to dramatise (without preaching)

- That destabilising a neighbour is rarely free.
- That oil wealth is a treadmill, not a cushion.
- That legitimacy is slower to build than to lose.
- That proxy warfare externalises short-term costs but accumulates long-term
  ones.
- That an isolated technologically-superior actor still faces structural
  ceilings.
- That fragmented states are playing a fundamentally different game than
  consolidated ones.

## Open design questions for the review team

1. Is the rondel the right action-selection mechanism, or does this want a
   card-driven chrome closer to *Here I Stand* / *Twilight Struggle*?
2. Is 5 factions + optional Outside Power the right count, or should the
   Outside Power be baseline?
3. How do we keep Era Cards from being "gotcha" bad luck?
4. Is the "Stability bonus" shared-fate mechanic enough to prevent a
   burn-it-all-down strategy?
5. Where is the rules-complexity ceiling; can this be taught in 20 min?
6. Does abstracting factions actually reduce harm, or does it launder the
   real dynamics into something less honest?
