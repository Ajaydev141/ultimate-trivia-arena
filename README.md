# 🏆 Ultimate Trivia Arena (TUI Edition)

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Textual](https://img.shields.io/badge/Textual-8.0%2B-00A86B?style=for-the-badge)
![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063?style=for-the-badge&logo=pydantic&logoColor=white)
![Rich](https://img.shields.io/badge/Rich-15.0%2B-FFD700?style=for-the-badge)
![Typer](https://img.shields.io/badge/Typer-CLI-009688?style=for-the-badge)

A modern, full-screen **Terminal User Interface (TUI)** trivia application built in Python. Engineered with a reactive multi-screen interface, real-time countdown timers, strategic lifelines, streak multipliers, and persistent local storage.

---

## ✨ Key Features

- **Full-Screen Reactive TUI:** Smooth multi-screen navigation (`Main Menu`, `Gameplay Arena`, `Post-Match Analytics`, `Hall of Fame Leaderboard`, and `Custom Question Builder`) powered by **Textual** and **Rich**.
- **Dynamic Scoring Engine:** Rewards accuracy, speed (`+10 pts/sec` remaining), consecutive answer streaks (`+25 pts × streak`), and difficulty multipliers (`Easy 1.0x`, `Medium 1.5x`, `Hard 2.0x`).
- **Strategic Lifelines:**
  - **50/50 (`F`):** Eliminates two incorrect options on the spot.
  - **Clue Hint (`H`):** Opens a contextual clue modal without pausing the stakes.
  - **Free Skip (`S`):** Bypasses a tough question without breaking your score.
- **Built-In Curated Bank + Custom Editor:** Includes 35 questions across 5 categories (*Science & Space*, *Coding & Tech*, *Video Games*, *World & Geography*, and *Math & Logic*) plus an in-app form to create and validate new questions.
- **Strict Data Validation & Persistence:** Powered by **Pydantic v2** to validate custom questions and save high scores locally to `~/.trivia_arena/`.
- **CLI Flag Support:** Configure default player names, timers, or reset leaderboards directly from the command line using **Typer**.

---

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone [https://github.com/Ajaydev141/ultimate-trivia-arena.git](https://github.com/Ajaydev141/ultimate-trivia-arena.git)
cd ultimate-trivia-arena
