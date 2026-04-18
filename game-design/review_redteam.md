# Crescent Imperium v1 — Red Team Report

**Reviewer stance:** 7 tryhards, 20 rulebook reads, no mercy. I am looking for the line that makes the other six players quit.

---

## 1. Opening-book (turn-1 dominant moves)

- **Iran:** Draft **Covert Action**, drop two Proxy Cells into Levant + Mesopotamia before anyone has Intel doctrine. Every Proxy you seed in Era 1 compounds across four Eras. Forced trap: spending Legitimacy on an overt move in Era 1 when the Proxy layer is unopposed.
- **Saudi:** Draft **Energy**, push Oil price **down** (counterintuitive) to starve importers of Legitimacy income before your own reserves matter. Trap: racing for Prestige objectives turn 1 — Prestige scales on Era-5 public objectives, not Era-1.
- **Israel:** Draft **Intelligence**, buy the first tier of the Intel doctrine, and pre-place stations in every Theater adjacent to a rival Proxy slot. You are the only faction that scores off *exposing* proxies; do not build units turn 1. Trap: early Normalization — you need rival Legitimacy low first.
- **Turkey:** Draft **Diplomacy**, sit on the Anatolia–Levant–Kurdistan tri-point and sell flex-alignment votes. Trap: committing to NATO umbrella before you've extracted concessions from Hegemon.
- **Ba'ath:** Draft **Mobilization**. You are the only faction whose board *flips worse* at Era transition (Iraq/Syria split), so you must bank military score **now**. Trap: investing in Doctrine — you won't live long enough as a single faction to amortize it.
- **Movement:** Draft **Media**. Do not take territory. Bait belligerents into pushing Regional Suffering up; you convert their Legitimacy losses into your Legitimacy Transfer score. Trap: taking sanctuary in a Theater the Hegemon can cheaply strike.
- **Hegemon:** Draft **Summit**. Lock in an Agenda that rewards "system stability" in Era 1 while nothing is unstable. Trap: deploying carriers turn 1 — you burn domestic war-fatigue against nothing.

---

## 2. Dominant / dominated faction

**Winner: Iran.** The Proxy layer is the most mechanically leveraged system in the game, and Iran is the only faction whose *victory track* directly rewards what the Proxy layer already produces. Legitimacy laundering through Proxies means Iran pays list price for aggression that every other faction pays retail for. Its "fear" (sanctions choke) is gated behind Hegemon agreeing to spend its own action budget — a coordination problem a 7p table never solves.

**Loser: Ba'ath / Successor States.** Forced mid-game board-split is a unique negative catalyst no one else suffers. In tournament play, it is strictly -EV to be handed a faction whose board worsens at a scripted moment. You also wear the Regional Suffering attribution when you use your own strength (mass army, chemical doctrine).

Movement is a close second-best; Hegemon is a close second-worst (kingmaker tax — see §4).

---

## 3. Degenerate combos

- **Iran: Oil Shock event + Proxy layer + Hegemon umbrella** = free Legitimacy laundering. Hegemon (USSR-flavored in Era 1) parks an umbrella over Iranian Proxies; Iran pushes Legitimacy-costly ops through Proxies at zero net cost; Oil Shock pays the ideology tax.
- **Saudi: Energy card + OPEC agenda + Media** = price-whip combo. Crash oil to bankrupt importers' Legitimacy income, then vote an OPEC resolution you wrote, then Media-spin the fallout. Three-action combo, one-turn cycle.
- **Israel: Intelligence + Covert Action + Doctrine (InfoOps)** = the "expose everything" engine. Every revealed Proxy is Legitimacy damage to a rival *and* a secret-objective tick for you. Self-fueling.
- **Turkey: Diplomacy + Summit + Spheres track** = vote-broker loop. Turkey's victory track scores off *who else* controls theaters, so Turkey can sell the same vote twice per Era to two enemies and score both times.
- **Movement: Media + any belligerent's escalation** = parasitic scoring. You do not need a Doctrine combo; you need *other players* to combo. The game hands you free points whenever Suffering advances.
- **Hegemon: Summit + Sanctions Regime doctrine** = lock-in. Write the Agenda, then unilaterally enforce it via Sanctions. Effectively a house rule you invented mid-game.

---

## 4. Kingmaker math (Era 5)

Seven asymmetric tracks mean Era-5 scoring is effectively a vector-sum over six incommensurable axes. Two players will be mathematically live; two more will be within a public-objective of live; **three will be eliminated from contention by mid-Era 4**.

Those three decide the game. Specifically: Hegemon and Movement both have action types that *directly move other players' tracks* (Hegemon via umbrellas/sanctions, Movement via Legitimacy Transfer). An eliminated Hegemon is a pure kingmaker with a full action economy and no incentive to spend it on itself. This is the worst failure mode in the design — **the faction designed to regulate the system becomes the chooser of winners when it loses**.

There is no stable endgame. Expect a 20-minute Era-5 negotiation where the bottom-three players auction their remaining actions.

---

## 5. Table-politics exploits

- **Three-player Legitimacy cartel:** Israel + Hegemon + Saudi can all score off rival Legitimacy suppression. They have no reason not to form a permanent bloc, and nothing in the rules punishes a stable 3-alliance in a 7p game.
- **Vote-trading loop:** Legitimacy-weighted Agenda votes mean the two highest-Legitimacy players can trade votes across consecutive Agenda phases to exclude everyone else from resolutions. No anti-collusion rule exists.
- **Intel-leak extortion:** Once Israel has any Proxy reveal queued, Israel can extort the sponsor ("pay me X or I expose next turn"). Proxies are hidden but *known-to-exist*; the threat is credible without the reveal.
- **Movement protection racket:** "Pay me Hard Currency or I let Suffering tick and tank your Legitimacy." Movement has structurally nothing to lose from escalation, so the threat is free.

---

## 6. Pacing exploits

- **Early win:** Not quite possible by Era 2, but Iran can **lock** Era-5 by Era 3 via Proxy saturation. Once 8+ Proxy Cells are placed and Intel doctrine hasn't universalized, exposing them costs more actions than Iran gains from them — Iran then turtles on Legitimacy and runs out the clock.
- **Timeout stall:** Turkey and Hegemon both benefit from "system inside preferred equilibrium." A Turkey–Hegemon non-aggression pact can stall Flashpoint resolutions indefinitely by abstaining as a bloc (Legitimacy-weighted votes mean two high-Legitimacy abstentions kill quorum). Game drags into real-clock timeout; tournament tiebreakers (usually VP) favor the stallers.

---

## 7. The boring optimal line (scariest bug)

**"Iran Proxy Monoculture."** Iran opens Covert Action every Era, places the maximum Proxy Cells each Action phase, and refuses every fight. Its victory track (Proxy Reach + Ideological Conversion) scores monotonically off Proxy count. Other players must spend *their* action economy on Intel doctrine and reveals to slow it — but doing so is zero-sum for them and negative-sum against the non-Iran table. Classic collective-action failure.

It is not flashy. It is not interactive. It is not fun to play against. And it wins.

---

## Ranked exploit list + minimum patches

1. **Iran Proxy Monoculture (§7).** *Patch:* Proxy Cells score with **diminishing returns** past 3 per sponsor per Era (e.g., 3/2/1/0 points). One-line change, kills the monoculture, preserves the fantasy.
2. **Iran Oil-Shock-umbrella laundering (§3).** *Patch:* Hegemon umbrella cannot stack with an Era Event Legitimacy gain in the same round. One exclusion clause.
3. **Eliminated-Hegemon kingmaker (§4).** *Patch:* Once a faction is mathematically eliminated, their remaining actions cost double (or their Agenda votes halve). "Lame duck" rule.
4. **Israel intel-extortion (§5).** *Patch:* Revealing a Proxy must be *committed in secret* at start of round (sealed bid) and flipped in Crisis phase. Kills the extortion threat; preserves the reveal.
5. **Turkey double-selling votes (§3).** *Patch:* Vote commitments are binding across the Era, tracked on a public ledger.
6. **Turkey–Hegemon stall (§6).** *Patch:* Flashpoints unresolved for 2 consecutive rounds auto-escalate Regional Suffering. Punishes abstention, doesn't force a winner.
7. **Saudi price-whip (§3).** *Patch:* Oil price moves capped to ±1 per round regardless of action stacking.
8. **Movement protection racket (§5).** *Patch:* Movement's Legitimacy Transfer requires *attributed* Suffering from a named belligerent, not ambient ticks. Makes the threat cost Movement an action to realize.
9. **Ba'ath forced bad split (§2).** *Patch:* Ba'ath player chooses which successor they pilot post-split, or gets a compensating objective reveal. Not balance — fairness.

**Bottom line:** The game's center of gravity is Legitimacy + Proxy. Both systems have too many zero-cost laundering paths and one faction (Iran) sits at the intersection. Patch #1 alone shifts the meta more than the other eight combined. Ship it and playtest again before touching anything else.
