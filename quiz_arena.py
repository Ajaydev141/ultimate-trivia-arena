#!/usr/bin/env python3
"""
ULTIMATE TRIVIA ARENA (TUI Edition)
Built with Textual, Rich, Pydantic, and Typer.
"""

from __future__ import annotations

import json
import random
import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import typer
from pydantic import BaseModel, Field, field_validator
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import (
    Center,
    Container,
    Grid,
    Horizontal,
    ScrollableContainer,
    Vertical,
)
from textual.reactive import reactive
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    OptionList,
    ProgressBar,
    RadioButton,
    RadioSet,
    Select,
    Static,
    Switch,
)
from textual.widgets.option_list import Option

# =====================================================================
# 1. CONFIGURATION & CONSTANTS
# =====================================================================

APP_TITLE = "ULTIMATE TRIVIA ARENA"
APP_SUBTITLE = "Powered by Textual • Pydantic • Rich • Typer"
DATA_DIR = Path.home() / ".trivia_arena"
SCORES_FILE = DATA_DIR / "leaderboard.json"
CUSTOM_QUESTIONS_FILE = DATA_DIR / "custom_questions.json"

DEFAULT_TIME_LIMIT = 15
BASE_POINTS = 100
TIME_BONUS_MULTIPLIER = 10
STREAK_BONUS_STEP = 25


class Difficulty(str, Enum):
    EASY = "Easy"
    MEDIUM = "Medium"
    HARD = "Hard"
    ALL = "All"


class Category(str, Enum):
    SCIENCE = "Science & Space"
    CODING = "Coding & Tech"
    GAMING = "Video Games"
    WORLD = "World & Geography"
    MATH = "Math & Logic"
    ALL = "All Categories"


# =====================================================================
# 2. PYDANTIC DATA MODELS & VALIDATION
# =====================================================================


class Question(BaseModel):
    id: str
    category: Category
    difficulty: Difficulty
    prompt: str = Field(..., min_length=5, max_length=300)
    options: List[str] = Field(..., min_length=4, max_length=4)
    correct_index: int = Field(..., ge=0, le=3)
    explanation: str = Field(default="No explanation provided.")
    hint: str = Field(default="Think carefully about each option.")

    @field_validator("options")
    @classmethod
    def check_unique_options(cls, v: List[str]) -> List[str]:
        cleaned = [opt.strip() for opt in v]
        if len(set(cleaned)) != 4:
            raise ValueError("All four answer options must be unique.")
        if any(not opt for opt in cleaned):
            raise ValueError("Answer options cannot be empty.")
        return cleaned

    @property
    def correct_text(self) -> str:
        return self.options[self.correct_index]


class GameSettings(BaseModel):
    player_name: str = Field(default="Player 1", min_length=1, max_length=25)
    category: Category = Category.ALL
    difficulty: Difficulty = Difficulty.ALL
    question_count: int = Field(default=10, ge=3, le=30)
    time_per_question: int = Field(default=15, ge=5, le=60)
    enable_timer: bool = True
    shuffle_options: bool = True


class QuestionResult(BaseModel):
    question_id: str
    prompt: str
    category: Category
    difficulty: Difficulty
    selected_option: Optional[str]
    correct_option: str
    is_correct: bool
    timed_out: bool
    time_taken: float
    points_earned: int


class ScoreEntry(BaseModel):
    player_name: str
    score: int
    correct_count: int
    total_questions: int
    accuracy: float
    max_streak: int
    category: str
    difficulty: str
    timestamp: str


class GameSession(BaseModel):
    settings: GameSettings
    questions: List[Question]
    current_index: int = 0
    score: int = 0
    streak: int = 0
    max_streak: int = 0
    lifeline_fifty_used: bool = False
    lifeline_hint_used: bool = False
    lifeline_skip_used: bool = False
    results: List[QuestionResult] = Field(default_factory=list)

    @property
    def total_questions(self) -> int:
        return len(self.questions)

    @property
    def current_question(self) -> Optional[Question]:
        if 0 <= self.current_index < len(self.questions):
            return self.questions[self.current_index]
        return None

    @property
    def correct_count(self) -> int:
        return sum(1 for r in self.results if r.is_correct)

    @property
    def accuracy(self) -> float:
        if not self.results:
            return 0.0
        return (self.correct_count / len(self.results)) * 100.0


# =====================================================================
# 3. BUILT-IN QUESTION BANK (35 CURATED QUESTIONS)
# =====================================================================


def get_builtin_questions() -> List[Question]:
    raw_data = [
        # --- SCIENCE & SPACE ---
        {
            "id": "sci_01",
            "category": Category.SCIENCE,
            "difficulty": Difficulty.EASY,
            "prompt": "Which planet in our solar system has the most confirmed moons?",
            "options": ["Jupiter", "Saturn", "Uranus", "Neptune"],
            "correct_index": 1,
            "explanation": "Saturn leads the solar system with over 140 confirmed moons, edging out Jupiter.",
            "hint": "This gas giant is famous for its massive icy ring system.",
        },
        {
            "id": "sci_02",
            "category": Category.SCIENCE,
            "difficulty": Difficulty.EASY,
            "prompt": "What gas do plants absorb from the atmosphere during photosynthesis?",
            "options": ["Oxygen", "Nitrogen", "Carbon Dioxide", "Hydrogen"],
            "correct_index": 2,
            "explanation": "Plants take in carbon dioxide (CO2) and water, using sunlight to make glucose and oxygen.",
            "hint": "Humans exhale this gas every time we breathe out.",
        },
        {
            "id": "sci_03",
            "category": Category.SCIENCE,
            "difficulty": Difficulty.MEDIUM,
            "prompt": "What is the chemical symbol for the element Gold?",
            "options": ["Gd", "Go", "Ag", "Au"],
            "correct_index": 3,
            "explanation": "Au comes from 'Aurum', the Latin word for gold.",
            "hint": "Ag is Silver; look for the two-letter symbol starting with A.",
        },
        {
            "id": "sci_04",
            "category": Category.SCIENCE,
            "difficulty": Difficulty.MEDIUM,
            "prompt": "Which part of the human eye controls how much light enters the pupil?",
            "options": ["Cornea", "Iris", "Retina", "Optic Nerve"],
            "correct_index": 1,
            "explanation": "The colored iris expands and contracts to adjust the size of the pupil.",
            "hint": "This is the colored ring around the black center of your eye.",
        },
        {
            "id": "sci_05",
            "category": Category.SCIENCE,
            "difficulty": Difficulty.HARD,
            "prompt": "What is the approximate speed of light in a vacuum?",
            "options": [
                "300,000 km/s",
                "150,000 km/s",
                "30,000 km/s",
                "3,000,000 km/s",
            ],
            "correct_index": 0,
            "explanation": "Light travels at exactly 299,792,458 meters per second, roughly 300,000 km/s.",
            "hint": "It takes sunlight about 8 minutes to travel 150 million km to Earth.",
        },
        {
            "id": "sci_06",
            "category": Category.SCIENCE,
            "difficulty": Difficulty.HARD,
            "prompt": "Which subatomic particle was discovered by James Chadwick in 1932?",
            "options": ["Electron", "Proton", "Neutron", "Positron"],
            "correct_index": 2,
            "explanation": "James Chadwick discovered the neutral neutron inside the atomic nucleus.",
            "hint": "This particle carries zero electrical charge.",
        },
        {
            "id": "sci_07",
            "category": Category.SCIENCE,
            "difficulty": Difficulty.EASY,
            "prompt": "What is the hardest natural substance found on Earth?",
            "options": ["Quartz", "Titanium", "Diamond", "Obsidian"],
            "correct_index": 2,
            "explanation": "Diamond ranks 10 on the Mohs hardness scale due to its rigid carbon lattice.",
            "hint": "It is made of pure carbon under extreme pressure.",
        },
        # --- CODING & TECH ---
        {
            "id": "cod_01",
            "category": Category.CODING,
            "difficulty": Difficulty.EASY,
            "prompt": "Which Python keyword is used to define a reusable function?",
            "options": ["func", "define", "def", "function"],
            "correct_index": 2,
            "explanation": "In Python, functions start with 'def function_name():'.",
            "hint": "It is a 3-letter abbreviation of 'define'.",
        },
        {
            "id": "cod_02",
            "category": Category.CODING,
            "difficulty": Difficulty.EASY,
            "prompt": "What does 'CPU' stand for in computer hardware?",
            "options": [
                "Central Process Unit",
                "Central Processing Unit",
                "Computer Personal Unit",
                "Core Program Utility",
            ],
            "correct_index": 1,
            "explanation": "The Central Processing Unit executes instructions and acts as the brain of a computer.",
            "hint": "The middle word ends with '-ing'.",
        },
        {
            "id": "cod_03",
            "category": Category.CODING,
            "difficulty": Difficulty.MEDIUM,
            "prompt": "In Python, what error happens if a file named 'turtle.py' runs 'import turtle'?",
            "options": [
                "SyntaxError",
                "MemoryError",
                "AttributeError (Circular Import)",
                "ZeroDivisionError",
            ],
            "correct_index": 2,
            "explanation": "Python imports your local script first instead of the standard library module!",
            "hint": "The file tries to import itself before its attributes exist.",
        },
        {
            "id": "cod_04",
            "category": Category.CODING,
            "difficulty": Difficulty.MEDIUM,
            "prompt": "Which data structure stores items in key-value pairs in Python?",
            "options": ["List", "Tuple", "Dictionary", "Set"],
            "correct_index": 2,
            "explanation": "Dictionaries use curly braces {'key': 'value'} for instant O(1) lookups.",
            "hint": "You look up a word to find its definition.",
        },
        {
            "id": "cod_05",
            "category": Category.CODING,
            "difficulty": Difficulty.HARD,
            "prompt": "What is the time complexity of binary search on a sorted list of N items?",
            "options": ["O(1)", "O(log n)", "O(n)", "O(n^2)"],
            "correct_index": 1,
            "explanation": "Binary search cuts the remaining search space in half on every step.",
            "hint": "Repeatedly halving a problem produces a logarithmic curve.",
        },
        {
            "id": "cod_06",
            "category": Category.CODING,
            "difficulty": Difficulty.MEDIUM,
            "prompt": "Which Linux terminal command lists running processes in real time with CPU/RAM bars?",
            "options": ["ls -la", "htop", "chmod", "grep"],
            "correct_index": 1,
            "explanation": "htop is an interactive system-monitor process viewer for Unix/Linux.",
            "hint": "It is an upgraded, colorful version of 'top'.",
        },
        {
            "id": "cod_07",
            "category": Category.CODING,
            "difficulty": Difficulty.EASY,
            "prompt": "What number does the binary string '101' represent in decimal?",
            "options": ["3", "5", "6", "7"],
            "correct_index": 1,
            "explanation": "1*(4) + 0*(2) + 1*(1) = 5.",
            "hint": "Add the 4s place and the 1s place together.",
        },
        # --- VIDEO GAMES ---
        {
            "id": "gam_01",
            "category": Category.GAMING,
            "difficulty": Difficulty.EASY,
            "prompt": "In Minecraft, which material is required to mine Obsidian blocks?",
            "options": ["Iron Pickaxe", "Gold Pickaxe", "Diamond Pickaxe", "Stone Pickaxe"],
            "correct_index": 2,
            "explanation": "Only a Diamond or Netherite pickaxe can harvest Obsidian without destroying it.",
            "hint": "It is a bright cyan gem found deep underground.",
        },
        {
            "id": "gam_02",
            "category": Category.GAMING,
            "difficulty": Difficulty.MEDIUM,
            "prompt": "In God of War Ragnarök, what is the name of Kratos's Leviathan Axe creator?",
            "options": [
                "Brok and Sindri",
                "Odin and Thor",
                "Mimir and Tyr",
                "Freya and Baldur",
            ],
            "correct_index": 0,
            "explanation": "The Huldra brothers, Brok and Sindri, forged both Mjölnir and the Leviathan Axe.",
            "hint": "They are two dwarven blacksmith brothers.",
        },
        {
            "id": "gam_03",
            "category": Category.GAMING,
            "difficulty": Difficulty.EASY,
            "prompt": "Which classic arcade character eats dots while avoiding Blinky, Pinky, Inky, and Clyde?",
            "options": ["Mario", "Sonic", "Pac-Man", "Donkey Kong"],
            "correct_index": 2,
            "explanation": "Pac-Man debuted in 1980 and featured four color-coded ghosts.",
            "hint": "He is a yellow circle with a wedge-shaped mouth.",
        },
        {
            "id": "gam_04",
            "category": Category.GAMING,
            "difficulty": Difficulty.MEDIUM,
            "prompt": "In Need for Speed Heat, what do you earn during night races to unlock car parts?",
            "options": ["Bank", "Rep", "Nitro", "Stars"],
            "correct_index": 1,
            "explanation": "Day races earn Bank (cash), while illegal night races earn Rep (reputation).",
            "hint": "Short for 'Reputation'.",
        },
        {
            "id": "gam_05",
            "category": Category.GAMING,
            "difficulty": Difficulty.HARD,
            "prompt": "What was the best-selling home video game console of all time?",
            "options": [
                "PlayStation 2",
                "Nintendo Wii",
                "PlayStation 4",
                "Xbox 360",
            ],
            "correct_index": 0,
            "explanation": "Sony's PlayStation 2 sold over 155 million units worldwide.",
            "hint": "Released by Sony in the year 2000.",
        },
        {
            "id": "gam_06",
            "category": Category.GAMING,
            "difficulty": Difficulty.EASY,
            "prompt": "What is the name of the fictional currency used in Fortnite?",
            "options": ["Robux", "V-Bucks", "Minecoins", "Gems"],
            "correct_index": 1,
            "explanation": "V-Bucks (Vindertech Bucks) are used to buy outfits and Battle Passes.",
            "hint": "Starts with the letter V.",
        },
        {
            "id": "gam_07",
            "category": Category.GAMING,
            "difficulty": Difficulty.HARD,
            "prompt": "In chess, what is the only piece capable of jumping over other pieces?",
            "options": ["Bishop", "Rook", "Queen", "Knight"],
            "correct_index": 3,
            "explanation": "The Knight moves in an L-shape and leaps directly over intervening pieces.",
            "hint": "This piece looks like a horse.",
        },
        # --- WORLD & GEOGRAPHY ---
        {
            "id": "geo_01",
            "category": Category.WORLD,
            "difficulty": Difficulty.EASY,
            "prompt": "Which is the largest ocean on Earth?",
            "options": [
                "Atlantic Ocean",
                "Indian Ocean",
                "Pacific Ocean",
                "Arctic Ocean",
            ],
            "correct_index": 2,
            "explanation": "The Pacific Ocean covers more than 30% of Earth's entire surface.",
            "hint": "It lies between Asia/Australia and the Americas.",
        },
        {
            "id": "geo_02",
            "category": Category.WORLD,
            "difficulty": Difficulty.MEDIUM,
            "prompt": "Which Indian city is known as the 'Detroit of India' for its automobile industry?",
            "options": ["Mumbai", "Bengaluru", "Chennai", "Pune"],
            "correct_index": 2,
            "explanation": "Chennai accounts for over 35% of India's automobile and auto-component industry.",
            "hint": "Capital city of Tamil Nadu along the Bay of Bengal.",
        },
        {
            "id": "geo_03",
            "category": Category.WORLD,
            "difficulty": Difficulty.EASY,
            "prompt": "Which country is home to the Great Pyramid of Giza?",
            "options": ["Mexico", "Peru", "Egypt", "Jordan"],
            "correct_index": 2,
            "explanation": "The Great Pyramid of Giza stands just outside Cairo, Egypt.",
            "hint": "Located in northeastern Africa along the Nile River.",
        },
        {
            "id": "geo_04",
            "category": Category.WORLD,
            "difficulty": Difficulty.MEDIUM,
            "prompt": "What is the longest river in the world?",
            "options": ["Amazon River", "Nile River", "Yangtze River", "Ganges River"],
            "correct_index": 1,
            "explanation": "The Nile River stretches roughly 6,650 km across northeastern Africa.",
            "hint": "It flows northward into the Mediterranean Sea.",
        },
        {
            "id": "geo_05",
            "category": Category.WORLD,
            "difficulty": Difficulty.HARD,
            "prompt": "Which country has the most natural lakes in the world?",
            "options": ["Russia", "United States", "Canada", "Finland"],
            "correct_index": 2,
            "explanation": "Canada contains over 60% of the world's natural lakes—more than 879,000 of them.",
            "hint": "Located immediately north of the United States.",
        },
        {
            "id": "geo_06",
            "category": Category.WORLD,
            "difficulty": Difficulty.MEDIUM,
            "prompt": "Which mountain range separates India from the Tibetan Plateau?",
            "options": ["Andes", "Rockies", "Himalayas", "Alps"],
            "correct_index": 2,
            "explanation": "The Himalayas include Mount Everest and Kanchenjunga along India's northern border.",
            "hint": "Its name translates to 'Abode of Snow' in Sanskrit.",
        },
        {
            "id": "geo_07",
            "category": Category.WORLD,
            "difficulty": Difficulty.HARD,
            "prompt": "What is the capital city of the Philippines?",
            "options": ["Cebu", "Manila", "Davao", "Quezon City"],
            "correct_index": 1,
            "explanation": "Manila is the historic capital city of the Philippines on Luzon island.",
            "hint": "Situated on the eastern shore of Manila Bay.",
        },
        # --- MATH & LOGIC ---
        {
            "id": "mth_01",
            "category": Category.MATH,
            "difficulty": Difficulty.EASY,
            "prompt": "What is the next prime number after 7?",
            "options": ["9", "10", "11", "13"],
            "correct_index": 2,
            "explanation": "9 is divisible by 3, and 10 is even, making 11 the next prime number.",
            "hint": "A prime number is only divisible by 1 and itself.",
        },
        {
            "id": "mth_02",
            "category": Category.MATH,
            "difficulty": Difficulty.EASY,
            "prompt": "How many degrees are inside a standard flat triangle?",
            "options": ["90°", "180°", "270°", "360°"],
            "correct_index": 1,
            "explanation": "The interior angles of any Euclidean triangle always add up to 180 degrees.",
            "hint": "Half of a full 360° circle.",
        },
        {
            "id": "mth_03",
            "category": Category.MATH,
            "difficulty": Difficulty.MEDIUM,
            "prompt": "What is the value of 15% of 200?",
            "options": ["20", "25", "30", "35"],
            "correct_index": 2,
            "explanation": "10% of 200 is 20, and 5% is 10; 20 + 10 = 30.",
            "hint": "15 per 100, doubled for 200.",
        },
        {
            "id": "mth_04",
            "category": Category.MATH,
            "difficulty": Difficulty.MEDIUM,
            "prompt": "Which sequence begins with 0, 1, 1, 2, 3, 5, 8, 13...?",
            "options": [
                "Pascal Sequence",
                "Fibonacci Sequence",
                "Euler Sequence",
                "Lucas Sequence",
            ],
            "correct_index": 1,
            "explanation": "Each number in the Fibonacci sequence is the sum of the two preceding ones.",
            "hint": "Named after a famous 13th-century Italian mathematician.",
        },
        {
            "id": "mth_05",
            "category": Category.MATH,
            "difficulty": Difficulty.HARD,
            "prompt": "If 3 machines take 3 minutes to make 3 widgets, how long do 100 machines take to make 100 widgets?",
            "options": ["100 minutes", "33 minutes", "3 minutes", "1 minute"],
            "correct_index": 2,
            "explanation": "Each single machine takes 3 minutes to make 1 widget, so 100 working together still take 3 minutes!",
            "hint": "Calculate how fast ONE machine makes ONE widget.",
        },
        {
            "id": "mth_06",
            "category": Category.MATH,
            "difficulty": Difficulty.HARD,
            "prompt": "What is 2 raised to the power of 10 (2^10)?",
            "options": ["512", "1000", "1024", "2048"],
            "correct_index": 2,
            "explanation": "2^10 = 1024, which is the foundation of a kilobyte (KiB) in computing.",
            "hint": "Just slightly over 1,000.",
        },
        {
            "id": "mth_07",
            "category": Category.MATH,
            "difficulty": Difficulty.EASY,
            "prompt": "What is the square root of 144?",
            "options": ["11", "12", "13", "14"],
            "correct_index": 1,
            "explanation": "12 × 12 = 144 (also known as one gross).",
            "hint": "One dozen times one dozen.",
        },
    ]
    return [Question(**q) for q in raw_data]


# =====================================================================
# 4. STORAGE & DATA REPOSITORY
# =====================================================================


class StorageManager:
    """Handles persistent JSON storage for custom questions and high scores."""

    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    def load_custom_questions(self) -> List[Question]:
        if not CUSTOM_QUESTIONS_FILE.exists():
            return []
        try:
            data = json.loads(CUSTOM_QUESTIONS_FILE.read_text(encoding="utf-8"))
            return [Question(**item) for item in data]
        except Exception:
            return []

    def save_custom_question(self, question: Question) -> None:
        existing = self.load_custom_questions()
        existing.append(question)
        serialized = [q.model_dump(mode="json") for q in existing]
        CUSTOM_QUESTIONS_FILE.write_text(
            json.dumps(serialized, indent=2), encoding="utf-8"
        )

    def get_all_questions(self) -> List[Question]:
        return get_builtin_questions() + self.load_custom_questions()

    def load_scores(self) -> List[ScoreEntry]:
        if not SCORES_FILE.exists():
            return []
        try:
            data = json.loads(SCORES_FILE.read_text(encoding="utf-8"))
            entries = [ScoreEntry(**item) for item in data]
            return sorted(entries, key=lambda x: x.score, reverse=True)
        except Exception:
            return []

    def save_score(self, entry: ScoreEntry) -> None:
        scores = self.load_scores()
        scores.append(entry)
        scores = sorted(scores, key=lambda x: x.score, reverse=True)[:50]
        serialized = [s.model_dump(mode="json") for s in scores]
        SCORES_FILE.write_text(json.dumps(serialized, indent=2), encoding="utf-8")

    def clear_scores(self) -> None:
        if SCORES_FILE.exists():
            SCORES_FILE.unlink()


# =====================================================================
# 5. GAME ENGINE CONTROLLER
# =====================================================================


class QuizEngine:
    """Core game logic independent of UI widgets."""

    def __init__(self, storage: StorageManager) -> None:
        self.storage = storage

    def create_session(self, settings: GameSettings) -> GameSession:
        pool = self.storage.get_all_questions()

        if settings.category != Category.ALL:
            pool = [q for q in pool if q.category == settings.category]

        if settings.difficulty != Difficulty.ALL:
            pool = [q for q in pool if q.difficulty == settings.difficulty]

        # Fallback if filters returned too few questions
        if not pool:
            pool = self.storage.get_all_questions()

        random.shuffle(pool)
        selected = pool[: min(settings.question_count, len(pool))]

        processed: List[Question] = []
        for q in selected:
            if settings.shuffle_options:
                correct_val = q.options[q.correct_index]
                shuffled_opts = list(q.options)
                random.shuffle(shuffled_opts)
                new_correct_idx = shuffled_opts.index(correct_val)
                processed.append(
                    q.model_copy(
                        update={
                            "options": shuffled_opts,
                            "correct_index": new_correct_idx,
                        }
                    )
                )
            else:
                processed.append(q)

        return GameSession(settings=settings, questions=processed)

    def calculate_points(
        self,
        difficulty: Difficulty,
        time_remaining: float,
        enable_timer: bool,
        current_streak: int,
    ) -> int:
        diff_multiplier = {
            Difficulty.EASY: 1.0,
            Difficulty.MEDIUM: 1.5,
            Difficulty.HARD: 2.0,
            Difficulty.ALL: 1.0,
        }[difficulty]

        time_bonus = int(max(0, time_remaining) * TIME_BONUS_MULTIPLIER) if enable_timer else 50
        streak_bonus = current_streak * STREAK_BONUS_STEP
        raw_points = (BASE_POINTS + time_bonus + streak_bonus) * diff_multiplier
        return int(round(raw_points))

    def submit_answer(
        self,
        session: GameSession,
        selected_index: Optional[int],
        time_taken: float,
        time_remaining: float,
        timed_out: bool = False,
    ) -> QuestionResult:
        question = session.current_question
        assert question is not None

        is_correct = (
            not timed_out
            and selected_index is not None
            and selected_index == question.correct_index
        )

        if is_correct:
            points = self.calculate_points(
                question.difficulty,
                time_remaining,
                session.settings.enable_timer,
                session.streak,
            )
            session.score += points
            session.streak += 1
            session.max_streak = max(session.max_streak, session.streak)
        else:
            points = 0
            session.streak = 0

        selected_text = (
            question.options[selected_index]
            if selected_index is not None and 0 <= selected_index < 4
            else None
        )

        result = QuestionResult(
            question_id=question.id,
            prompt=question.prompt,
            category=question.category,
            difficulty=question.difficulty,
            selected_option=selected_text,
            correct_option=question.correct_text,
            is_correct=is_correct,
            timed_out=timed_out,
            time_taken=round(time_taken, 2),
            points_earned=points,
        )
        session.results.append(result)
        return result


# =====================================================================
# 6. MODAL DIALOGS (HELP, HINT, CONFIRM)
# =====================================================================


class HintModal(ModalScreen[None]):
    """Displays a clue for the active question."""

    BINDINGS = [Binding("escape", "dismiss", "Close")]

    def __init__(self, hint_text: str) -> None:
        super().__init__()
        self.hint_text = hint_text

    def compose(self) -> ComposeResult:
        with Container(id="modal-box"):
            yield Label("💡 LIFELINE: CLUE UNLOCKED", id="modal-title")
            yield Static(self.hint_text, id="modal-body")
            with Center():
                yield Button("Got It!", variant="primary", id="close-hint")

    @on(Button.Pressed, "#close-hint")
    def close_modal(self) -> None:
        self.dismiss()


class HelpModal(ModalScreen[None]):
    """Displays keyboard shortcuts and scoring rules."""

    BINDINGS = [Binding("escape", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        rules = (
            "[b cyan]Keyboard Controls[/b cyan]\n"
            "• Press [b]1, 2, 3, 4[/b] or [b]A, B, C, D[/b] to answer instantly\n"
            "• Press [b]H[/b] for Hint  |  [b]F[/b] for 50/50  |  [b]S[/b] to Skip\n"
            "• Press [b]Enter[/b] or [b]Space[/b] to advance after feedback\n\n"
            "[b yellow]Scoring Formula[/b yellow]\n"
            "• Base Answer: [b]+100 pts[/b]\n"
            "• Speed Bonus: [b]+10 pts[/b] per second left on clock\n"
            "• Streak Bonus: [b]+25 pts × streak[/b]\n"
            "• Difficulty Multiplier: Easy [b]1.0x[/b] | Medium [b]1.5x[/b] | Hard [b]2.0x[/b]"
        )
        with Container(id="modal-box"):
            yield Label("📘 HOW TO PLAY & SCORING", id="modal-title")
            yield Static(rules, id="modal-body")
            with Center():
                yield Button("Back to Arena", variant="success", id="close-help")

    @on(Button.Pressed, "#close-help")
    def close_modal(self) -> None:
        self.dismiss()


# =====================================================================
# 7. MAIN MENU & SETUP SCREEN
# =====================================================================


class MainMenuScreen(Screen):
    """Landing screen with game configuration and navigation."""

    def compose(self) -> ComposeResult:
        yield Header()
        with ScrollableContainer(id="menu-scroll"):
            with Container(id="hero-banner"):
                yield Label("🏆 ULTIMATE TRIVIA ARENA 🏆", id="hero-title")
                yield Label(
                    "Configure your match settings below or jump straight in!",
                    id="hero-subtitle",
                )

            with Container(id="setup-card"):
                yield Label("⚙️ MATCH CONFIGURATION", classes="section-header")

                with Grid(id="setup-grid"):
                    yield Label("Player Name:", classes="field-label")
                    yield Input(
                        value=self.app.default_player,
                        placeholder="Enter your name...",
                        id="player-input",
                    )

                    yield Label("Topic Category:", classes="field-label")
                    yield Select(
                        [(c.value, c.value) for c in Category],
                        value=Category.ALL.value,
                        id="category-select",
                    )

                    yield Label("Difficulty Level:", classes="field-label")
                    yield Select(
                        [(d.value, d.value) for d in Difficulty],
                        value=Difficulty.ALL.value,
                        id="difficulty-select",
                    )

                    yield Label("Number of Questions:", classes="field-label")
                    yield Select(
                        [("5 Questions (Quick)", 5), ("10 Questions (Standard)", 10), ("15 Questions (Marathon)", 15), ("25 Questions (Expert)", 25)],
                        value=10,
                        id="count-select",
                    )

                    yield Label("Seconds per Question:", classes="field-label")
                    yield Select(
                        [("10 Seconds (Blitz)", 10), ("15 Seconds (Normal)", 15), ("30 Seconds (Relaxed)", 30)],
                        value=self.app.default_time,
                        id="time-select",
                    )

                    yield Label("Enable Countdown Timer:", classes="field-label")
                    yield Switch(value=True, id="timer-switch")

                    yield Label("Shuffle Answer Order:", classes="field-label")
                    yield Switch(value=True, id="shuffle-switch")

            with Horizontal(id="menu-actions"):
                yield Button("▶ START QUIZ", variant="success", id="btn-start")
                yield Button("🏅 LEADERBOARD", variant="primary", id="btn-scores")
                yield Button("➕ ADD QUESTION", variant="warning", id="btn-editor")
                yield Button("❓ RULES", variant="default", id="btn-rules")

            total_q = len(self.app.storage.get_all_questions())
            yield Label(
                f"📚 Question Bank Ready: {total_q} total questions loaded.",
                id="bank-status",
            )
        yield Footer()

    @on(Button.Pressed, "#btn-start")
    def start_quiz(self) -> None:
        name = self.query_one("#player-input", Input).value.strip() or "Player 1"
        cat_val = self.query_one("#category-select", Select).value
        diff_val = self.query_one("#difficulty-select", Select).value
        count_val = self.query_one("#count-select", Select).value
        time_val = self.query_one("#time-select", Select).value
        timer_on = self.query_one("#timer-switch", Switch).value
        shuffle_on = self.query_one("#shuffle-switch", Switch).value

        settings = GameSettings(
            player_name=name,
            category=Category(cat_val),
            difficulty=Difficulty(diff_val),
            question_count=int(count_val),
            time_per_question=int(time_val),
            enable_timer=timer_on,
            shuffle_options=shuffle_on,
        )
        session = self.app.engine.create_session(settings)
        self.app.push_screen(QuizPlayScreen(session))

    @on(Button.Pressed, "#btn-scores")
    def open_leaderboard(self) -> None:
        self.app.push_screen(LeaderboardScreen())

    @on(Button.Pressed, "#btn-editor")
    def open_editor(self) -> None:
        self.app.push_screen(QuestionEditorScreen())

    @on(Button.Pressed, "#btn-rules")
    def open_rules(self) -> None:
        self.app.push_screen(HelpModal())


# =====================================================================
# 8. ACTIVE QUIZ GAMEPLAY SCREEN
# =====================================================================


class QuizPlayScreen(Screen):
    """Interactive gameplay screen with timer, lifelines, and feedback."""

    BINDINGS = [
        Binding("1,a,A", "choose_0", "Option A", show=False),
        Binding("2,b,B", "choose_1", "Option B", show=False),
        Binding("3,c,C", "choose_2", "Option C", show=False),
        Binding("4,d,D", "choose_3", "Option D", show=False),
        Binding("f,F", "use_fifty", "50/50"),
        Binding("h,H", "use_hint", "Hint"),
        Binding("s,S", "use_skip", "Skip"),
        Binding("enter,space", "next_step", "Next", show=False),
        Binding("escape", "quit_match", "Quit Match"),
    ]

    time_left: reactive[float] = reactive(15.0)

    def __init__(self, session: GameSession) -> None:
        super().__init__()
        self.session = session
        self.answered = False
        self.question_start_time = time.monotonic()
        self.eliminated_indices: set[int] = set()
        self.timer_handle = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="play-container"):
            # Top HUD Bar
            with Horizontal(id="hud-bar"):
                yield Label("", id="hud-progress")
                yield Label("", id="hud-category")
                yield Label("", id="hud-streak")
                yield Label("", id="hud-score")

            # Timer Row
            with Horizontal(id="timer-row"):
                yield Label("⏱️ Time:", id="timer-label")
                yield ProgressBar(
                    total=self.session.settings.time_per_question,
                    show_eta=False,
                    show_percentage=False,
                    id="timer-bar",
                )
                yield Label("", id="timer-seconds")

            # Question Card
            with Container(id="question-card"):
                yield Label("", id="question-meta")
                yield Static("", id="question-prompt")

            # Answer Buttons Grid
            with Grid(id="answers-grid"):
                yield Button("", id="opt-0", classes="answer-btn")
                yield Button("", id="opt-1", classes="answer-btn")
                yield Button("", id="opt-2", classes="answer-btn")
                yield Button("", id="opt-3", classes="answer-btn")

            # Lifelines Bar
            with Horizontal(id="lifelines-bar"):
                yield Button("✂️ 50/50 Lifeline [F]", id="life-fifty", variant="primary")
                yield Button("💡 Clue Hint [H]", id="life-hint", variant="primary")
                yield Button("⏭️ Free Skip [S]", id="life-skip", variant="primary")

            # Feedback Banner (Hidden until answered)
            with Container(id="feedback-box"):
                yield Static("", id="feedback-text")
                with Center():
                    yield Button(
                        "Next Question ➔ [Enter]",
                        variant="success",
                        id="btn-next",
                    )
        yield Footer()

    def on_mount(self) -> None:
        self.load_current_question()
        if self.session.settings.enable_timer:
            self.timer_handle = self.set_interval(0.1, self._tick_timer)
        else:
            self.query_one("#timer-row").display = False

    def _tick_timer(self) -> None:
        if self.answered:
            return
        self.time_left = max(0.0, self.time_left - 0.1)
        self.query_one("#timer-bar", ProgressBar).progress = self.time_left
        self.query_one("#timer-seconds", Label).update(f"{self.time_left:04.1f}s")

        if self.time_left <= 0.0:
            self.handle_answer(selected_index=None, timed_out=True)

    def load_current_question(self) -> None:
        q = self.session.current_question
        if q is None:
            self.finish_quiz()
            return

        self.answered = False
        self.eliminated_indices.clear()
        self.question_start_time = time.monotonic()
        self.time_left = float(self.session.settings.time_per_question)

        # Update HUD
        q_num = self.session.current_index + 1
        total = self.session.total_questions
        self.query_one("#hud-progress", Label).update(f"📋 Question {q_num}/{total}")
        self.query_one("#hud-category", Label).update(f"🏷️ {q.category.value}")
        self.query_one("#hud-streak", Label).update(f"🔥 Streak: {self.session.streak}")
        self.query_one("#hud-score", Label).update(f"⭐ Score: {self.session.score}")

        # Update Timer
        bar = self.query_one("#timer-bar", ProgressBar)
        bar.total = self.session.settings.time_per_question
        bar.progress = self.time_left
        self.query_one("#timer-seconds", Label).update(f"{self.time_left:04.1f}s")

        # Update Question Text
        self.query_one("#question-meta", Label).update(
            f"Difficulty: {q.difficulty.value.upper()}"
        )
        self.query_one("#question-prompt", Static).update(q.prompt)

        # Reset Answer Buttons
        letters = ["A", "B", "C", "D"]
        for idx in range(4):
            btn = self.query_one(f"#opt-{idx}", Button)
            btn.label = f"[{letters[idx]}]  {q.options[idx]}"
            btn.variant = "default"
            btn.disabled = False

        # Update Lifelines State
        self.query_one("#life-fifty", Button).disabled = self.session.lifeline_fifty_used
        self.query_one("#life-hint", Button).disabled = self.session.lifeline_hint_used
        self.query_one("#life-skip", Button).disabled = self.session.lifeline_skip_used

        # Hide Feedback Box
        self.query_one("#feedback-box").display = False

    def handle_answer(self, selected_index: Optional[int], timed_out: bool = False) -> None:
        if self.answered:
            return
        self.answered = True

        q = self.session.current_question
        assert q is not None

        elapsed = time.monotonic() - self.question_start_time
        result = self.app.engine.submit_answer(
            session=self.session,
            selected_index=selected_index,
            time_taken=elapsed,
            time_remaining=self.time_left,
            timed_out=timed_out,
        )

        # Highlight Buttons
        for idx in range(4):
            btn = self.query_one(f"#opt-{idx}", Button)
            btn.disabled = True
            if idx == q.correct_index:
                btn.variant = "success"
            elif selected_index == idx:
                btn.variant = "error"

        # Disable Lifelines during feedback
        self.query_one("#life-fifty", Button).disabled = True
        self.query_one("#life-hint", Button).disabled = True
        self.query_one("#life-skip", Button).disabled = True

        # Refresh Score HUD
        self.query_one("#hud-streak", Label).update(f"🔥 Streak: {self.session.streak}")
        self.query_one("#hud-score", Label).update(f"⭐ Score: {self.session.score}")

        # Show Feedback Panel
        if timed_out:
            headline = f"[b red]⏰ TIME'S UP![/b red] Correct answer: [b green]{q.correct_text}[/b green]"
        elif result.is_correct:
            headline = f"[b green]✅ CORRECT! (+{result.points_earned} pts)[/b green]"
        else:
            headline = f"[b red]❌ INCORRECT![/b red] Correct answer: [b green]{q.correct_text}[/b green]"

        feedback_msg = f"{headline}\n[dim]{q.explanation}[/dim]"
        self.query_one("#feedback-text", Static).update(feedback_msg)

        next_btn = self.query_one("#btn-next", Button)
        if self.session.current_index + 1 >= self.session.total_questions:
            next_btn.label = "View Final Results 🏆 [Enter]"
        else:
            next_btn.label = "Next Question ➔ [Enter]"

        self.query_one("#feedback-box").display = True
        next_btn.focus()

    # --- Button Click Handlers ---

    @on(Button.Pressed, "#opt-0")
    def click_opt_0(self) -> None:
        self.handle_answer(0)

    @on(Button.Pressed, "#opt-1")
    def click_opt_1(self) -> None:
        self.handle_answer(1)

    @on(Button.Pressed, "#opt-2")
    def click_opt_2(self) -> None:
        self.handle_answer(2)

    @on(Button.Pressed, "#opt-3")
    def click_opt_3(self) -> None:
        self.handle_answer(3)

    @on(Button.Pressed, "#btn-next")
    def click_next(self) -> None:
        self.action_next_step()

    @on(Button.Pressed, "#life-fifty")
    def click_fifty(self) -> None:
        self.action_use_fifty()

    @on(Button.Pressed, "#life-hint")
    def click_hint(self) -> None:
        self.action_use_hint()

    @on(Button.Pressed, "#life-skip")
    def click_skip(self) -> None:
        self.action_use_skip()

    # --- Keyboard Actions ---

    def action_choose_0(self) -> None:
        if 0 not in self.eliminated_indices:
            self.handle_answer(0)

    def action_choose_1(self) -> None:
        if 1 not in self.eliminated_indices:
            self.handle_answer(1)

    def action_choose_2(self) -> None:
        if 2 not in self.eliminated_indices:
            self.handle_answer(2)

    def action_choose_3(self) -> None:
        if 3 not in self.eliminated_indices:
            self.handle_answer(3)

    def action_next_step(self) -> None:
        if not self.answered:
            return
        self.session.current_index += 1
        if self.session.current_index >= self.session.total_questions:
            self.finish_quiz()
        else:
            self.load_current_question()

    def action_use_fifty(self) -> None:
        if self.answered or self.session.lifeline_fifty_used:
            return
        q = self.session.current_question
        assert q is not None

        self.session.lifeline_fifty_used = True
        self.query_one("#life-fifty", Button).disabled = True

        wrong_indices = [i for i in range(4) if i != q.correct_index]
        to_remove = random.sample(wrong_indices, 2)
        for idx in to_remove:
            self.eliminated_indices.add(idx)
            btn = self.query_one(f"#opt-{idx}", Button)
            btn.disabled = True
            btn.label = "--- Eliminated ---"

    def action_use_hint(self) -> None:
        if self.answered or self.session.lifeline_hint_used:
            return
        q = self.session.current_question
        assert q is not None

        self.session.lifeline_hint_used = True
        self.query_one("#life-hint", Button).disabled = True
        self.app.push_screen(HintModal(q.hint))

    def action_use_skip(self) -> None:
        if self.answered or self.session.lifeline_skip_used:
            return
        self.session.lifeline_skip_used = True
        self.session.current_index += 1
        if self.session.current_index >= self.session.total_questions:
            self.finish_quiz()
        else:
            self.load_current_question()

    def action_quit_match(self) -> None:
        if self.timer_handle:
            self.timer_handle.stop()
        self.app.pop_screen()

    def finish_quiz(self) -> None:
        if self.timer_handle:
            self.timer_handle.stop()

        entry = ScoreEntry(
            player_name=self.session.settings.player_name,
            score=self.session.score,
            correct_count=self.session.correct_count,
            total_questions=len(self.session.results),
            accuracy=round(self.session.accuracy, 1),
            max_streak=self.session.max_streak,
            category=self.session.settings.category.value,
            difficulty=self.session.settings.difficulty.value,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )
        self.app.storage.save_score(entry)
        self.app.switch_screen(ResultsSummaryScreen(self.session, entry))


# =====================================================================
# 9. POST-GAME RESULTS & REVIEW SCREEN
# =====================================================================


class ResultsSummaryScreen(Screen):
    """Displays final grade, stats breakdown, and question-by-question review."""

    BINDINGS = [Binding("escape", "go_home", "Main Menu")]

    def __init__(self, session: GameSession, entry: ScoreEntry) -> None:
        super().__init__()
        self.session = session
        self.entry = entry

    def compose(self) -> ComposeResult:
        yield Header()
        with ScrollableContainer(id="results-scroll"):
            rank_title = self._compute_rank(self.entry.accuracy)
            with Container(id="results-banner"):
                yield Label(f"🎉 MATCH COMPLETE: {rank_title}", id="results-title")
                yield Label(
                    f"Player: {self.entry.player_name}  |  Final Score: {self.entry.score} pts",
                    id="results-score",
                )

            with Grid(id="stats-grid"):
                yield Static(
                    f"[b]Accuracy[/b]\n[cyan]{self.entry.accuracy:.1f}%[/cyan]",
                    classes="stat-card",
                )
                yield Static(
                    f"[b]Correct[/b]\n[green]{self.entry.correct_count} / {self.entry.total_questions}[/green]",
                    classes="stat-card",
                )
                yield Static(
                    f"[b]Best Streak[/b]\n[yellow]{self.entry.max_streak} 🔥[/yellow]",
                    classes="stat-card",
                )
                yield Static(
                    f"[b]Difficulty[/b]\n[magenta]{self.entry.difficulty}[/magenta]",
                    classes="stat-card",
                )

            yield Label("📝 QUESTION-BY-QUESTION BREAKDOWN", classes="section-header")
            table = DataTable(id="review-table")
            table.add_columns("#", "Status", "Question", "Your Answer", "Correct Answer", "Pts")
            for idx, r in enumerate(self.session.results, start=1):
                status = "✅" if r.is_correct else ("⏰" if r.timed_out else "❌")
                your_ans = r.selected_option or ("Timed Out" if r.timed_out else "Skipped")
                short_q = (r.prompt[:42] + "...") if len(r.prompt) > 45 else r.prompt
                table.add_row(
                    str(idx),
                    status,
                    short_q,
                    your_ans,
                    r.correct_option,
                    f"+{r.points_earned}",
                )
            yield table

            with Horizontal(id="results-actions"):
                yield Button("🔄 PLAY AGAIN", variant="success", id="btn-replay")
                yield Button("🏅 VIEW LEADERBOARD", variant="primary", id="btn-board")
                yield Button("🏠 MAIN MENU", variant="default", id="btn-home")
        yield Footer()

    @staticmethod
    def _compute_rank(accuracy: float) -> str:
        if accuracy >= 95:
            return "GRANDMASTER GENIUS 🧠"
        if accuracy >= 80:
            return "TRIVIA CHAMPION 🏆"
        if accuracy >= 60:
            return "SHARP CONTENDER ⭐"
        if accuracy >= 40:
            return "RISING CHALLENGER 🚀"
        return "ROOKIE EXPLORER 🌱"

    @on(Button.Pressed, "#btn-replay")
    def replay(self) -> None:
        new_session = self.app.engine.create_session(self.session.settings)
        self.app.switch_screen(QuizPlayScreen(new_session))

    @on(Button.Pressed, "#btn-board")
    def view_board(self) -> None:
        self.app.switch_screen(LeaderboardScreen())

    @on(Button.Pressed, "#btn-home")
    def action_go_home(self) -> None:
        self.app.pop_screen()


# =====================================================================
# 10. LEADERBOARD SCREEN
# =====================================================================


class LeaderboardScreen(Screen):
    """Persistent Hall of Fame table."""

    BINDINGS = [Binding("escape", "go_back", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="board-container"):
            yield Label("🏅 HALL OF FAME — TOP SCORES", id="board-title")
            table = DataTable(id="leaderboard-table")
            table.add_columns(
                "Rank", "Player", "Score", "Accuracy", "Streak", "Topic", "Difficulty", "Date"
            )
            scores = self.app.storage.load_scores()
            if not scores:
                table.add_row("-", "No scores yet!", "0", "0%", "0", "-", "-", "-")
            else:
                for rank, entry in enumerate(scores[:20], start=1):
                    medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"#{rank}")
                    table.add_row(
                        medal,
                        entry.player_name,
                        str(entry.score),
                        f"{entry.accuracy:.1f}%",
                        f"{entry.max_streak}🔥",
                        entry.category,
                        entry.difficulty,
                        entry.timestamp,
                    )
            yield table

            with Horizontal(id="board-actions"):
                yield Button("⬅ Back to Menu", variant="primary", id="btn-back")
                yield Button("🗑️ Clear History", variant="error", id="btn-clear")
        yield Footer()

    @on(Button.Pressed, "#btn-back")
    def action_go_back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-clear")
    def clear_history(self) -> None:
        self.app.storage.clear_scores()
        self.notify("Leaderboard history cleared.", severity="warning")
        self.app.pop_screen()


# =====================================================================
# 11. CUSTOM QUESTION BUILDER SCREEN
# =====================================================================


class QuestionEditorScreen(Screen):
    """Allows players to create and validate new custom trivia questions."""

    BINDINGS = [Binding("escape", "go_back", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with ScrollableContainer(id="editor-scroll"):
            yield Label("➕ CUSTOM QUESTION CREATOR", id="editor-title")
            yield Label(
                "Create your own trivia questions—validated with Pydantic and saved locally!",
                id="editor-subtitle",
            )

            with Grid(id="editor-grid"):
                yield Label("Category:", classes="field-label")
                yield Select(
                    [(c.value, c.value) for c in Category if c != Category.ALL],
                    value=Category.SCIENCE.value,
                    id="ed-category",
                )

                yield Label("Difficulty:", classes="field-label")
                yield Select(
                    [(d.value, d.value) for d in Difficulty if d != Difficulty.ALL],
                    value=Difficulty.MEDIUM.value,
                    id="ed-difficulty",
                )

                yield Label("Question Prompt:", classes="field-label")
                yield Input(placeholder="e.g., What is the fastest land animal?", id="ed-prompt")

                yield Label("Option A:", classes="field-label")
                yield Input(placeholder="First choice...", id="ed-opt-0")

                yield Label("Option B:", classes="field-label")
                yield Input(placeholder="Second choice...", id="ed-opt-1")

                yield Label("Option C:", classes="field-label")
                yield Input(placeholder="Third choice...", id="ed-opt-2")

                yield Label("Option D:", classes="field-label")
                yield Input(placeholder="Fourth choice...", id="ed-opt-3")

                yield Label("Correct Option:", classes="field-label")
                yield Select(
                    [("Option A", 0), ("Option B", 1), ("Option C", 2), ("Option D", 3)],
                    value=0,
                    id="ed-correct",
                )

                yield Label("Clue / Hint:", classes="field-label")
                yield Input(placeholder="Helpful hint for 50/50 clue lifeline...", id="ed-hint")

                yield Label("Explanation:", classes="field-label")
                yield Input(placeholder="Fact shown after answering...", id="ed-explanation")

            with Horizontal(id="editor-actions"):
                yield Button("💾 SAVE QUESTION", variant="success", id="btn-save-q")
                yield Button("⬅ CANCEL", variant="default", id="btn-cancel-q")
        yield Footer()

    @on(Button.Pressed, "#btn-save-q")
    def save_question(self) -> None:
        try:
            cat_val = self.query_one("#ed-category", Select).value
            diff_val = self.query_one("#ed-difficulty", Select).value
            prompt = self.query_one("#ed-prompt", Input).value.strip()
            options = [
                self.query_one("#ed-opt-0", Input).value.strip(),
                self.query_one("#ed-opt-1", Input).value.strip(),
                self.query_one("#ed-opt-2", Input).value.strip(),
                self.query_one("#ed-opt-3", Input).value.strip(),
            ]
            correct_idx = int(self.query_one("#ed-correct", Select).value)
            hint = self.query_one("#ed-hint", Input).value.strip() or "No hint available."
            explanation = (
                self.query_one("#ed-explanation", Input).value.strip()
                or "Custom question created by player."
            )

            new_q = Question(
                id=f"custom_{int(time.time())}",
                category=Category(cat_val),
                difficulty=Difficulty(diff_val),
                prompt=prompt,
                options=options,
                correct_index=correct_idx,
                hint=hint,
                explanation=explanation,
            )
            self.app.storage.save_custom_question(new_q)
            self.notify("Custom question saved to your bank!", severity="information")
            self.app.pop_screen()
        except Exception as exc:
            self.notify(f"Validation Error: {exc}", severity="error")

    @on(Button.Pressed, "#btn-cancel-q")
    def action_go_back(self) -> None:
        self.app.pop_screen()


# =====================================================================
# 12. TEXTUAL APPLICATION & CSS STYLING
# =====================================================================


class TriviaArenaApp(App):
    """Main Textual TUI Application."""

    TITLE = APP_TITLE
    SUB_TITLE = APP_SUBTITLE

    CSS = """
    Screen {
        background: #0f172a;
        color: #f8fafc;
    }

    #menu-scroll, #results-scroll, #editor-scroll {
        padding: 1 2;
    }

    #hero-banner, #results-banner {
        background: #1e293b;
        border: heavy #38bdf8;
        padding: 1 2;
        margin-bottom: 1;
        content-align: center middle;
    }

    #hero-title, #results-title, #board-title, #editor-title {
        text-style: bold;
        color: #38bdf8;
        width: 100%;
        content-align: center middle;
    }

    #hero-subtitle, #results-score, #editor-subtitle {
        color: #94a3b8;
        width: 100%;
        content-align: center middle;
    }

    #setup-card {
        background: #1e293b;
        border: round #475569;
        padding: 1 2;
        margin-bottom: 1;
    }

    .section-header {
        text-style: bold;
        color: #facc15;
        margin-bottom: 1;
    }

    #setup-grid, #editor-grid {
        grid-size: 2;
        grid-columns: 1fr 2fr;
        grid-gutter: 1 2;
        height: auto;
    }

    .field-label {
        content-align: left middle;
        color: #e2e8f0;
        text-style: bold;
    }

    #menu-actions, #results-actions, #board-actions, #editor-actions, #lifelines-bar {
        height: auto;
        align: center middle;
        margin-top: 1;
    }

    #menu-actions Button, #results-actions Button, #board-actions Button, #editor-actions Button, #lifelines-bar Button {
        margin: 0 1;
    }

    #bank-status {
        margin-top: 1;
        width: 100%;
        content-align: center middle;
        color: #4ade80;
    }

    /* Gameplay Layout */
    #play-container {
        padding: 1 2;
    }

    #hud-bar {
        background: #1e293b;
        border: round #38bdf8;
        padding: 0 2;
        height: 3;
        align: center middle;
    }

    #hud-bar Label {
        width: 1fr;
        content-align: center middle;
        text-style: bold;
    }

    #timer-row {
        height: 3;
        align: center middle;
        padding: 0 1;
    }

    #timer-label {
        width: 10;
        text-style: bold;
        color: #facc15;
    }

    #timer-bar {
        width: 1fr;
    }

    #timer-seconds {
        width: 8;
        content-align: right middle;
        text-style: bold;
        color: #38bdf8;
    }

    #question-card {
        background: #1e293b;
        border: heavy #818cf8;
        padding: 1 2;
        margin: 1 0;
        height: auto;
    }

    #question-meta {
        color: #a5b4fc;
        text-style: bold;
        margin-bottom: 1;
    }

    #question-prompt {
        text-style: bold;
        color: #ffffff;
    }

    #answers-grid {
        grid-size: 2;
        grid-columns: 1fr 1fr;
        grid-gutter: 1 2;
        height: auto;
        margin-bottom: 1;
    }

    .answer-btn {
        width: 100%;
        height: 3;
    }

    #feedback-box {
        background: #1e293b;
        border: round #4ade80;
        padding: 1 2;
        margin-top: 1;
        height: auto;
    }

    #feedback-text {
        margin-bottom: 1;
    }

    /* Stats & Tables */
    #stats-grid {
        grid-size: 4;
        grid-columns: 1fr 1fr 1fr 1fr;
        grid-gutter: 1;
        height: auto;
        margin-bottom: 1;
    }

    .stat-card {
        background: #1e293b;
        border: round #475569;
        padding: 1;
        content-align: center middle;
    }

    #review-table, #leaderboard-table {
        height: 16;
        margin-bottom: 1;
    }

    #board-container {
        padding: 1 2;
    }

    /* Modals */
    #modal-box {
        width: 60;
        height: auto;
        background: #1e293b;
        border: heavy #facc15;
        padding: 2;
        margin: 4 10;
    }

    #modal-title {
        text-style: bold;
        color: #facc15;
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }

    #modal-body {
        margin-bottom: 1;
    }
    """

    def __init__(
        self,
        default_player: str = "Player 1",
        default_time: int = DEFAULT_TIME_LIMIT,
    ) -> None:
        super().__init__()
        self.default_player = default_player
        self.default_time = default_time
        self.storage = StorageManager()
        self.engine = QuizEngine(self.storage)

    def on_mount(self) -> None:
        self.push_screen(MainMenuScreen())


# =====================================================================
# 13. TYPER CLI ENTRYPOINT
# =====================================================================

cli = typer.Typer(add_completion=False, help="Launch the Ultimate Trivia Arena TUI.")


@cli.command()
def main(
    player: str = typer.Option("Player 1", "--player", "-p", help="Default player name"),
    time_limit: int = typer.Option(
        15, "--time", "-t", min=5, max=60, help="Seconds per question (5-60)"
    ),
    reset_scores: bool = typer.Option(
        False, "--reset-scores", help="Wipe saved leaderboard before launching"
    ),
) -> None:
    """Starts the interactive Textual Trivia Quiz Arena."""
    storage = StorageManager()
    if reset_scores:
        storage.clear_scores()
        typer.secho("Leaderboard cleared!", fg=typer.colors.YELLOW)

    app = TriviaArenaApp(default_player=player, default_time=time_limit)
    app.run()


if __name__ == "__main__":
    cli()