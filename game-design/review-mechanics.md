# CRESCENT v1 — Mechanical Design Review

Reviewer brief: critique as a Eurogame, theme-blind. No hedging.

## 1. Is this actually a Eurogame?

Mostly yes, but with a conflict-sim undertow that will fight the designer at every turn.

**Pulling Euro:** shared rondel with scaling cost, multi-track scoring (Prosperity / Legitimacy / Influence / Hidden / Stability), no elimination, no military victory, indirect-conflict framing, trade routes as mutual-dependency engines, a shared-fate Stability multiplier, era scoring cadence. The scoring architecture is textbook Feld — many small streams, cap around 30 per category, target 60–80.

**Pulling CDG/wargame:** Proxy tokens that destabilise regions, Military as an expended resource with public attribution, hidden Information tokens used for "assassination-of-plans," Era Cards as structural shocks, a Contested Republic whose map state is literally a civil-war tracker. The Information action and covert-ops chrome are pure *Twilight Struggle*. Asymmetric factions with "structural vulnerabilities" are closer to COIN than to *Terra Mystica* — TM asymmetry is about engine shape, not about being legally attackable.

Verdict: it's a Euro *chassis* carrying CDG *payloads*. That's viable (see Lacerda's *Kanban EV* vs. *Vinhos*), but only if the payloads resolve deterministically. Right now, Proxy, Military, and Information all read as hidden-info bluff systems, which is Euro poison at 4–5 players because turn length scales with paranoia.

## 2. Dominant strategies / degenerate equilibria

1. **Merchant Emirate turtle + Safe Harbour rent-seeking.** +1 of every resource, hosts others' assets for a fee, scores on trade routes and Prosperity. Vulnerability triggers only on *regional war within 2 spaces* — and everyone else is disincentivised from war by the Legitimacy paradox. The Emirate free-rides on a peace everyone is already structurally forced into. Expected outcome: Emirate wins uncontested in 70%+ of games that don't feature a Revolutionary Republic committed to burning them.
2. **Stability-bonus collusion.** Every player scores avg Stability × multiplier. Combined with Proxy's externalised cost, the Nash equilibrium for non-Revolutionary factions is "nobody places proxies, everyone farms Produce/Trade/Invest." This is *Through the Ages* culture-pacifism: the game converges to a parallel solitaire where the richest engine wins. Petro-Sovereign megaprojects likely dominate this mode.
3. **Settler Republic Tech rush + Deterrent lockout.** Starts with +2 Tech and highest Military cap. If the Tech ladder compounds (nuclear/drone/cyber/energy), and Deterrent credibly shuts down attacks, it converts its Legitimacy deficit into a non-issue and wins on Tech VP. The "regional Legitimacy caps trade partners" vulnerability is toothless if Tech VP > Trade VP.

## 3. Elegant-looking mechanics that will feel bad

- **Public attribution on Military actions, obscurable by Information.** Reads clever, plays as analysis-paralysis. Every Military action becomes a ten-minute table discussion about who paid Info, who's bluffing, and whether the attribution is binding. This is the *Twilight Struggle* headline problem at 5 players.
- **Era Card swinginess.** Five Eras, each with a single structural-pressure card. Petro-Sovereign's entire strategy can be gutted by one Oil Shock draw. "Gotcha" is exactly right — and your own open question (#3) admits it. Single-card era modifiers in a 2.5-hour game are a known anti-pattern (*Age of Empires III* era cards, pre-errata).
- **Rondel cost scaling with 8 actions and 3 rounds per era.** Three rondel selections per era means each player touches ~3 of 8 actions per era. That's not tempo-vs-flexibility tension; that's forced starvation. Players will feel locked out of Information and Appeal entirely.
- **Contested Republic's four-bloc balancing.** Reconciliation VP "if all 4 blocs end aligned" is a binary cliff. Either the player spends the game chasing it and wins huge, or gives up Era 2 and plays a crippled faction for 2 hours.

## 4. Right action-selection engine

**Not the rondel.** A shared 8-slot rondel with scaling cost works in *Antike* or *Trajan* because the action space is symmetric and the rondel *is* the engine. Here the actions are wildly asymmetric in power and in who wants them (Proxy matters to 2 factions, Information to 1, Appeal to 2). Scaling cost punishes exactly the faction whose identity depends on that action.

**Not card-driven** à la *Twilight Struggle*. CDGs require a shared event deck everyone reads; asymmetric private levers + hidden objectives + Era Cards is already too much hidden state.

**Right answer: action-drafting with faction-weighted costs**, *Ora et Labora* / *A Feast for Odin* style. A shared pool of action spaces, but each faction pays a different cost to take each one (Revolutionary Republic gets Proxy at discount; Merchant Emirate pays a premium for Military; etc.). This preserves asymmetry *inside* the selection mechanism instead of bolting it onto faction powers, kills the rondel-starvation problem, and lets you tune dominant strategies by reweighting costs rather than rewriting powers.

Secondary option: **worker placement with a blocking-tax**, where Military and Proxy slots are limited but placing there also generates a public Stability debt tracked on the board. That externalises the Legitimacy paradox into the selection layer directly.

## 5. Biggest pacing concern

**Era 5 will be anticlimactic.** Three reasons stacked:

1. Hidden Objectives and Stability bonuses favour accumulators, and by Era 5 the engine leaders are set. No catch-up mechanism is specified.
2. Trade routes "break catastrophically" — so nobody initiates conflict in Era 5 because it costs both sides. Era 5 becomes a Produce/Invest optimisation round.
3. The Stability multiplier means everyone is incentivised to *not* make the final era dramatic. You've designed cooperative endgame incentives into a competitive game.

Expect the last 45 minutes to play as parallel scoring optimisation with the winner determined in Era 3. This is *Terra Mystica*'s final-round problem without TM's tight clock.

## 6. Concrete fixes

**Fix 1 — Replace the rondel with faction-weighted drafting.** 6 shared action slots, each with base cost + per-faction modifier printed on the faction board. Each round, players draft in turn order determined by Legitimacy (low Legitimacy picks first — a natural catch-up). Kills rondel starvation, makes asymmetry legible, gives you a tuning knob per faction per action.

**Fix 2 — Make Era Cards a draft, not a reveal.** At start of each era, reveal 3 Era Cards; players bid Influence in reverse-score order to *choose which one is active* or to *add a secondary modifier*. Removes "gotcha," converts structural pressure into a player-agency moment, and creates a leader-suppression lever that isn't kingmaking.

**Fix 3 — Nerf the Merchant Emirate and add an Era 5 shock clock.** Change Emirate's Safe Harbour so hosted assets count toward the *host's* Stability burden, not just fees. Separately, add an **Era 5 Reckoning**: at Era 4 end, the player with the most Influence VP seeds one mandatory crisis (forced Proxy resolution, sanction detonation, or trade-route audit) that all players must respond to in Era 5. Forces endgame engagement without breaking the no-elimination rule, and routes leader-suppression through the mechanic rather than through table talk.

**Bonus fix — Cap Hidden Objective VP at 15, not 30.** Currently it's a third of a winning score hidden from the table, which is too much for a game this long. Visible scoring drives Euro tension; hidden scoring drives post-game resentment.

---

Bottom line: the chassis is sound and the tensions named in Section "Core tensions" are genuinely interesting. The selection mechanism, the Era Card variance, and the Merchant Emirate's cost structure will sink the playtest. Fix those three and you have a 3.8-weight Euro with real teeth. Leave them and you have a 4.2-weight CDG that reviewers will call "interesting but exhausting."
