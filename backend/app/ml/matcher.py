import math
from typing import List


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    if len(vec1) != len(vec2):
        raise ValueError("Embedding vectors must have the same dimension.")
    if not all(math.isfinite(value) for value in [*vec1, *vec2]):
        raise ValueError("Embedding vectors must contain only finite numbers.")
    norm1, norm2 = math.hypot(*vec1), math.hypot(*vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    score = math.fsum((left / norm1) * (right / norm2) for left, right in zip(vec1, vec2))
    return max(-1.0, min(1.0, score))


def calculate_skill_overlap(user_skills: List[str], required_skills: List[str]) -> dict:
    def normalized(skill: str) -> str:
        return " ".join(skill.split()).casefold()

    available = {normalized(skill) for skill in user_skills if skill.strip()}
    unique_required = {}
    for skill in required_skills:
        key = normalized(skill)
        if key and key not in unique_required:
            unique_required[key] = " ".join(skill.split())
    matched = [display for key, display in unique_required.items() if key in available]
    missing = [display for key, display in unique_required.items() if key not in available]
    percentage = len(matched) / len(unique_required) * 100 if unique_required else 0.0
    return {"matched_skills": matched, "missing_skills": missing, "overlap_percentage": percentage}
