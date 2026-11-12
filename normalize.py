"""Stage 3: data cleaning rules shared by the loader and the retrieval API.

Every rule here is listed in data/cleaning_log.md so the team can review it.
"""
import re

# Known spelling problems in the Kaggle files, keyed by whitespace-collapsed raw name.
DISEASE_CORRECTIONS = {
    "Dimorphic hemmorhoids(piles)": "Dimorphic hemorrhoids (piles)",
    "Dimorphic hemorrhoids(piles)": "Dimorphic hemorrhoids (piles)",
    "(vertigo) Paroymsal Positional Vertigo": "(Vertigo) Paroxysmal Positional Vertigo",
    "Peptic ulcer diseae": "Peptic ulcer disease",
    "Osteoarthristis": "Osteoarthritis",
    "hepatitis A": "Hepatitis A",
}


# Symptom names that are still wrong after normalisation (typos in the source files).
SYMPTOM_CORRECTIONS = {
    "foul_smell_ofurine": "foul_smell_of_urine",
}


def collapse_spaces(text: str) -> str:
    return " ".join(text.split())


def canonical_disease(raw: str) -> str:
    """Return the canonical disease name used everywhere in the database."""
    collapsed = collapse_spaces(raw)
    return DISEASE_CORRECTIONS.get(collapsed, collapsed)


def normalize_symptom(raw: str) -> str:
    """Lower-case, join words with single underscores, drop stray spaces.

    'spotting_ urination' -> 'spotting_urination'
    'dischromic _patches' -> 'dischromic_patches'
    'High Fever'          -> 'high_fever'
    """
    s = raw.strip().lower()
    s = re.sub(r"[\s_]+", "_", s)
    s = s.strip("_")
    return SYMPTOM_CORRECTIONS.get(s, s)


def display_symptom(symptom_name: str) -> str:
    return symptom_name.replace("_", " ").capitalize()
