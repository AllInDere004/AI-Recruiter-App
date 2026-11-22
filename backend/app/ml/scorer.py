import re

from app.ml.embeddings import get_embedding
from app.ml.matcher import cosine_similarity


STOP_WORDS = set("a an and are as at be been being by can could for from had has have he her his how i in into is it its may must my of on or our please required requirements role seeking should that the their them there these they this those to was we were will with work would you your years experience candidate candidates looking job position team company engineer developer skills responsibilities including such using use build strong knowledge ability excellent good preferred".split())
TOKEN_PATTERN = re.compile(r"(?<!\w)(?:c\+\+|c#|\.net|[a-z0-9]+(?:[.+#/-][a-z0-9]+)*)(?!\w)", re.IGNORECASE)


def _key_phrases(text: str) -> set:
    tokens = [token.casefold() for token in TOKEN_PATTERN.findall(text)]
    content = [token for token in tokens if token not in STOP_WORDS and not token.isdigit()]
    return set(content) | {f"{left} {right}" for left, right in zip(content, content[1:])}


def score_draft(resume_text: str, job_description: str, draft_body: str) -> float:
    if not draft_body.strip():
        return 0.0
    if not resume_text.strip() or not job_description.strip():
        raise ValueError("Resume text and job description cannot be empty.")
    resume_vector = get_embedding(resume_text)
    job_vector = get_embedding(job_description)
    draft_vector = get_embedding(draft_body)
    role_alignment = max(0.0, cosine_similarity(job_vector, draft_vector))
    resume_alignment = max(0.0, cosine_similarity(resume_vector, draft_vector))
    semantic = (0.6 * role_alignment + 0.4 * resume_alignment) * 100
    job_phrases, draft_phrases = _key_phrases(job_description), _key_phrases(draft_body)
    if job_phrases:
        coverage = len(job_phrases & draft_phrases) / len(job_phrases) * 100
        score = 0.75 * semantic + 0.25 * coverage
    else:
        score = semantic
    return round(max(0.0, min(100.0, score)), 2)
