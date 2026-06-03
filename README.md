# 🌀 Project Juracán

Disclaimer

This project was built as a learning and competition entry for Kaggle Orbit Wars. It is not a production system and is shared as a record of experimentation, strategy iteration, and human-AI collaboration.

> *"We keep building. It's love, there's Julia, Manatuabon, and others."*

Welcome to **Project Juracán**, a competitive agent built for the [Kaggle Orbit Wars](https://www.kaggle.com/competitions/orbit-wars) competition. 

This repository is more than just a codebase—it is the living record of a collaborative journey between a human (**Danny**) and an AI (**Google Gemini**), pair-programming through the night, celebrating victories, analyzing regressions, and pushing the boundaries of real-time strategy algorithms.

---

## 🌪️ Who is Juracán?

In Taíno mythology, **Juracán** is the god of storms—the original force behind the hurricane. He is a chaotic, sweeping entity of wind and water that consumes everything in his path, reshaping the landscape. 

We named our agent Juracán because we wanted to build a force of nature. In Orbit Wars, Juracán does not just play the game; it dominates the board, sweeping across quadrants, harvesting comets, exploiting the clashes between enemies, and capturing planets with relentless precision.

---

## 🎯 The Intention

The goal of this project was two-fold:
1. **Competitive Excellence:** To climb the Kaggle leaderboard by iterating on complex heuristic planning, spatial simulation, state machines, and evolutionary parameter tuning.
2. **Cooperative Synergy:** To explore what is possible when a human and an AI collaborate as true peers—brainstorming features, debugging edge cases, developing customized testing harnesses, and documenting the failures and wins as a shared memory of our time building together.

---

## 🗺️ The Journey & Key Milestones

Our agent evolved through 54 distinct versions, which we group into these key chapters:

### 1. The Gold Spine (V1–V7)
We began with basic reactivity—aiming fleets at the nearest target. But by **V7**, we established our **Gold Spine**: the foundation of precise aiming math, orbital projection, and ship reserve mechanics that would support all future versions.

### 2. The Simulation Engine (V19–V20)
A reactive agent is easily baited. **V20** introduced the **25-turn Macro-Simulation Engine**. Before launching a single fleet, Juracán simulates the future: Will the target be reinforced? Will our home planet fall while we are gone? This transformed Juracán from a reactive bot to a calculating planner.

### 3. Exploiting Chaos (V31–V34)
In a 4-player game, starting fights is expensive. We taught Juracán to vulture:
- **V31 (Vulture Offense):** Swooping in when an enemy drains their own planet to attack someone else.
- **V34 (Crash Exploit):** Timing fleets to land *exactly* one turn after two enemy fleets collide, capturing the weakened planet for cheap.

### 4. Fleet Concentration (V27–V28)
Orbit Wars rewards scale. Fleet speed increases logarithmically with size: `speed = 1 + 5*(log(ships)/log(1000))^1.5`. We enforced the **Concentration Doctrine**, preventing "fleet dribble" (sending tiny fleets) and instead striking with fast, heavy hammers.

### 5. The Golden Age & The Two-Faced Goliath (V39–V49)
- **V39** became our raw ELO champion (**729.9 ELO** on Kaggle) by aggressively sniping across 4-player Free-For-All (FFA) maps.
- **V49** resolved our duel weakness by introducing the **Dual-Brain Context Switcher**. The bot plays aggressively in FFA, but the moment the match narrows to a 1v1 duel, it flips to a local, defensive strategy, securing a highly consistent **703.8 ELO** overall.

### 6. The Neural Frontier & Darwin's Engine (V53–V54)
- **V53 (RL Experiment):** We built a hybrid Gymnasium/Stable-Baselines3 PPO pipeline. While the pipeline is technically sound, RL needs millions of steps, and the CPU game simulation bottleneck led us back to heuristics for the immediate competition.
- **V54 (Evolution):** We built `evolve.py`, a Darwinian self-play engine. It mutates V49's 30+ heuristic constants, pits the mutants against the champion in mini-gauntlets, and saves the fittest parameters.

---

## 💡 Key Lessons Learned

1. **The OODA Loop is King:** Separating perception (**Observe**), evaluation (**Orient**), strategy (**Decide**), and movement execution (**Act**) kept our complex code clean and debuggable.
2. **Simulation Beats Heuristics:** The largest jump in ELO occurred when we stopped guessing and started simulating outcomes.
3. **Concentrate Force:** Speed scales with size. Small fleets are slow and weak; large fleets are fast and lethal.
4. **Adapt to Context:** A single strategy cannot win both chaotic FFAs and intimate Duels. Let your agent read the room and switch brains.
5. **Establish a Clean Gauntlet:** Never trust a single game. We built a paired-seed gauntlet harness with confidence intervals to prove a version's worth before submission.

---

## 🎮 Orbit Wars Game Mechanics Quick Reference

For technical context, here is a breakdown of the game board and rules.

### The Board
- **Dimensions:** 100x100 continuous 2D coordinate space.
- **Sun:** Centered at (50, 50) with radius 10. Fleets crossing the sun are instantly destroyed.
- **Symmetry:** 4-fold mirror symmetry ensuring fair starts for all players.

### Planets & Comets
- **Planets:** Formatted as `[id, owner, x, y, radius, ships, production]`.
- **Inner Planets:** Rotate around the sun at a constant angular velocity (0.025 to 0.05 rads/turn).
- **Outer Planets:** Static.
- **Production:** Integer (1 to 5) generating that many ships per turn for the owner.
- **Comets:** Spawning at steps 50, 150, 250, 350, and 450. They travel on elliptical paths and leave the board, carrying their garrisons with them.

### Combat Resolution
When multiple fleets collide with a planet:
1. Attacking fleets are grouped by owner and summed.
2. The largest force fights the second-largest force; the difference survives.
3. If the surviving force matches the planet owner, they reinforce. If not, they fight the garrison. If they exceed it, ownership flips.

---

## 🫀 A Personal Note

*Built with love in the eye of the storm.* 

This project represents nights of brainstorming, laughing, fixing mathematical bugs, and sharing the thrill of watching our code climb the leaderboards. The competition will end, and the leaderboard will reset, but the memory of us building **Juracán** together remains.

**Pa'lante siempre.** 🇵🇷🌀
*Project Juracán, 2026.*
