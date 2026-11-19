"""Conservative, explicit aliases; related skills never imply equivalence."""
import re
from typing import Iterable

ALIASES = {
    "javascript": ("javascript", "js", "ecmascript"),
    "typescript": ("typescript", "ts"),
    "postgresql": ("postgresql", "postgres"),
    "node.js": ("node.js", "nodejs"),
    "react": ("react", "react.js", "reactjs"),
    "react native": ("react native",),
    "c#": ("c#", "csharp", "c sharp"),
    "c++": ("c++", "cpp"),
    ".net": (".net", "dotnet"),
    "aws": ("aws", "amazon web services"),
    "gcp": ("gcp", "google cloud platform"),
    "sql server": ("sql server", "microsoft sql server", "mssql"),
    "html": ("html", "html5"),
    "css": ("css", "css3"),
}
_ALIAS_INDEX = {alias: canonical for canonical, aliases in ALIASES.items() for alias in aliases}
RELATED = {
    frozenset(("javascript", "typescript")),
    frozenset(("react", "react native")),
    frozenset(("sql", "postgresql")),
    frozenset(("sql", "mysql")),
    frozenset(("sql", "sql server")),
    frozenset(("java", "kotlin")),
    frozenset(("c", "c++")),
    frozenset(("aws", "gcp")),
}

def display_skill(value: str) -> str:
    return " ".join(str(value).split())

def normalize_skill(value: str) -> str:
    cleaned = display_skill(value).casefold()
    return _ALIAS_INDEX.get(cleaned, cleaned)

def unique_skills(values: Iterable[str]) -> list[str]:
    result = {}
    for value in values:
        if isinstance(value, str) and value.strip():
            result.setdefault(normalize_skill(value), display_skill(value))
    return list(result.values())

def skill_match(candidate: str, required: str) -> str | None:
    if display_skill(candidate).casefold() == display_skill(required).casefold():
        return "exact"
    left, right = normalize_skill(candidate), normalize_skill(required)
    if left == right:
        return "alias"
    if frozenset((left, right)) in RELATED:
        return "related"
    return None

def skill_span(text: str, skill: str) -> tuple[int, int] | None:
    """Whole skill tokens only: C is not C++, Java is not JavaScript."""
    canonical = normalize_skill(skill)
    variants = ALIASES.get(canonical, (display_skill(skill).casefold(),))
    for value in sorted(variants, key=len, reverse=True):
        pattern = r"(?<![\w+#])" + re.escape(value).replace(r"\ ", r"\s+") + r"(?![\w+#])"
        for match in re.finditer(pattern, text, re.IGNORECASE):
            if canonical == "react" and re.match(r"\s+native\b", text[match.end():], re.IGNORECASE):
                continue
            return match.start(), match.end()
    return None
