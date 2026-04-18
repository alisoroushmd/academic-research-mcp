# Mechanical Stress Test: Crescent Imperium v1

Reviewer: senior designer, TI4 / Root / COIN / Scythe lineage.
Verdict up front: the thematic chassis is strong, but the mechanical load-bearing walls (Legitimacy, Proxy, Agenda) are under-specified in ways that historically produce 12-hour sessions, one dominant archetype, and a kingmaker-ridden final Agenda. Top concerns below, each with a concrete fix.

## 1. Runaway leader / snowball — Legitimacy + Agenda is a positive loop

The snowball vector is not military; it is **Legitimacy → Agenda weight → Summit resolutions → Legitimacy-laundering of aggression → more Legitimacy**. Whoever enters Era 2 with a Legitimacy lead controls the weighted vote, writes the world-state modifier, and uses it to legalize their next expansion (which would otherwise cost Legitimacy). This is the exact TI4 Politics-card problem, amplified because Legitimacy is *also* the soft currency gating scoring. Oil is a second loop: Gulf production decisions move the global track, and the Kingdom has both the largest lever and the largest exposure to it — price manipulation pays them twice (income + Hegemon alignment).

**Fix:** Cap Agenda voting influence per faction at `min(Legitimacy, 2 + Era)` and add a **Backlash** rule: winning three consecutive Agenda votes triggers a "Overreach" token that inverts your next Legitimacy gain. Borrow COIN's "you cannot take the same Op twice in a row" logic.

## 2. Degenerate strategy — Proxy-spam + never attribute

First dominant strategy a competitive group discovers: **hidden Proxy saturation + refuse to escalate**. Proxies cost less Legitimacy than direct action, are only exposed by opposing Intel spend, and scale with Theater count. Iran and the Hegemon are the obvious abusers; the Movement wants to do this anyway. Three players all proxy-spamming creates a Nash where nobody burns Intel to expose, because exposure only hurts the *exposed* sponsor — the exposer gets no direct reward commensurate with the tempo lost. Classic "secret action, public cost" asymmetry gone wrong (cf. Diplomacy press, or early Root Cult).

**Fix:** Exposing a Proxy must grant the exposer a concrete, scaling bounty — Intel refund + one free Legitimacy or a Crisis token placed on sponsor. Also cap Proxies to **one per Theater per faction** with a diminishing-return cost curve, so the 4th cell in a region costs 4× the first.

## 3. Dead turns / dead factions by Era

- **Hegemon in Era 5 (Multipolar):** the faction's core lever is unipolar credibility; in 2016–26 context it has nothing to threaten with. Expect a dead player, or worse, a kingmaker.
- **Ba'ath in Era 4+ (post-rupture):** splitting into Iraq/Syria halves the board presence but the victory track still reads "pan-Arab" — the win condition becomes unreachable. Classic "mechanics outlive the fantasy" problem.
- **The State (Israel) in Era 1:** tech-tree strength doesn't come online until Era 2–3; early rounds are just absorbing pressure.
- **The Movement between identity swaps:** the transition round is mechanically hollow.

**Fix:** Give each faction a **per-Era pivot objective** (COIN does this well via Propaganda rounds). Ba'ath post-rupture gets a new victory track ("Reconstitution" or "Regional Revanche") seeded at split. Hegemon gets a Multipolar-specific kit: Sanctions Architect + Coalition Broker actions that scale with *other* players' conflict.

## 4. Action economy — round-robin with 7 asymmetric factions will bog

TI4 works with 6 because tactical actions are *spatially bounded* (one system) and strategic actions are *drafted once per round*. COIN works with 4 because sequence-of-play forces pass/eligibility tradeoffs. Your doc proposes single-action round-robin across 7 factions with heterogeneous action lists — that is a ~35 minute round at a minimum, × ~6 rounds/Era × 5 Eras = game-over-your-weekend. Also: "single action" with 8 Strategy Cards means a 7-player game leaves one card undrafted, creating information asymmetry without a counterweight.

**Fix:** Adopt **COIN eligibility**: after acting, you skip the next round of initiative unless you take a weaker "Limited" action. This compresses turn count and creates real pass decisions. Reduce Strategy Cards to 6, drafted snake-order. Cut round-robin actions per round to ~2 per player and batch map moves.

## 5. Legitimacy — soft cap or real gate?

Right now it's a **soft cap everyone pays**. The doc says aggressive actions "cost Legitimacy unless laundered," but Oil income, doctrine trees, and Agenda victories all regenerate it. Anything fungible against regenerating income becomes a tax, not a gate. TI4's command tokens work because they are *strictly rivalrous* with other actions; Legitimacy as described is rivalrous with nothing.

**Fix:** Make Legitimacy **non-linearly regenerative** — you can only gain back Legitimacy via actions that *cost* the resource you're richest in (Oil-rich factions must flare income to rebuild; military-rich must demobilize). Also hard-gate objective *scoring* (not attempting) on Legitimacy thresholds: below 3, you cannot score Public Objectives at all.

## 6. Length — this is a 14-hour game, not 8

5 Eras × ~6 rounds × 7 players × 5 phases × round-robin actions = a convention-weekend game. The designer already flagged this. **Cut to 3 Eras** (1976–95, 1996–2010, 2011–26), collapse Strategy + Action into one interleaved phase, and make the Crisis Phase a card-flip resolved in-initiative rather than a discrete step. Target 6 hours / 3 Eras / ~4 rounds each.

## 7. Kingmaker risk in Agenda Phase

Seven asymmetric win conditions mean in Era 5 at least two factions are mathematically eliminated but still voting. With Legitimacy-weighted votes, the losers **choose the winner** — pure kingmaking. Worse, the Hegemon's "Order Points" win condition incentivizes voting *against* whoever is ahead, institutionalizing the role.

**Fix:** In Era 5, Agenda votes require a **stake** — you can only vote on resolutions that move *your* victory track. Eliminated factions get a "Legacy" mini-objective (Scythe-style end-game trigger) so they're playing their own game, not brokering someone else's.

---

## Ship-blocker vs. polish triage

**Ship-blockers (do not playtest without fixing):**
1. Length / round structure (§4, §6) — unplayable as written.
2. Legitimacy not actually rivalrous (§5) — the central mechanic doesn't do its job.
3. Proxy exposure has no reward (§2) — guarantees degenerate equilibrium.
4. Ba'ath / Hegemon dead-faction risk per Era (§3) — 2 of 7 seats rot.
5. Agenda kingmaking in Era 5 (§7) — poisons the finale.

**Polish (post-first-playtest):**
- Oil track tuning and OPEC cadence.
- Nuclear doctrine cap (designer already flagged).
- Movement identity-swap transition smoothing.
- Israel Era-1 pacing.
- Strategy card count / draft order.

Fix the five blockers before the first external playtest. The thematic frame is worth protecting; the mechanics aren't ready to carry it yet.
