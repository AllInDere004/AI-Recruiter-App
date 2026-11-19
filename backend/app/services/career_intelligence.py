"""Deterministic, source-backed career estimates; no LLM or model download."""
import math
import re

from app.ml.skill_taxonomy import normalize_skill, skill_match, skill_span, unique_skills
from app.services.evidence import input_version, is_instruction_like, normalize_text, requirement_priority, supports_claim, verified_evidence

ALGORITHM_VERSION = "career-evidence-v1"
DEFAULT_WEIGHTS = {
    "required_skills": 40.0,
    "preferred_skills": 15.0,
    "experience_projects": 20.0,
    "education": 10.0,
    "role_alignment": 15.0,
}
LABELS = {
    "required_skills": "Required skills",
    "preferred_skills": "Preferred skills",
    "experience_projects": "Experience and projects",
    "education": "Education",
    "role_alignment": "Role alignment",
}
DISCLAIMER = (
    "This is an evidence-based compatibility estimate, not a hiring probability, "
    "eligibility decision or guarantee. Missing evidence does not prove a skill is absent."
)
ATS_DISCLAIMER = "Rule-based ATS-readiness guidance cannot guarantee acceptance by any employer's ATS."

def _strings(value):
    return [item.strip() for item in value if isinstance(item, str) and item.strip()] if isinstance(value, list) else []

def _field_matches(item, prefixes):
    return any(item["field"] == p or item["field"].startswith(p + "[") or item["field"].startswith(p + ".") for p in prefixes)

def _job_requirements(data, job_text):
    experience = _strings(data.get("experience_requirements")) or _strings(data.get("key_responsibilities"))
    required_skills = unique_skills(_strings(data.get("required_skills")))
    preferred_skills = unique_skills(_strings(data.get("preferred_skills")))
    moved_preferred = [skill for skill in required_skills if requirement_priority(skill, job_text, skill=True) == "preferred"]
    moved_required = [skill for skill in preferred_skills if requirement_priority(skill, job_text, skill=True) == "required"]
    required_skills = unique_skills([skill for skill in required_skills if skill not in moved_preferred] + moved_required)
    preferred_skills = unique_skills([skill for skill in preferred_skills if skill not in moved_required] + moved_preferred)
    required_keys = {normalize_skill(skill) for skill in required_skills}
    preferred_skills = [skill for skill in preferred_skills if normalize_skill(skill) not in required_keys]
    return {
        "required_skills": required_skills,
        "preferred_skills": preferred_skills,
        "experience_projects": list(dict.fromkeys(experience)),
        "education": list(dict.fromkeys(_strings(data.get("education_requirements")))),
        "role_alignment": [data["title"].strip()] if isinstance(data.get("title"), str) and data["title"].strip() else [],
    }

def _literal_match(phrase, text):
    return bool(re.search(r"(?<!\w)" + re.escape(normalize_text(phrase)) + r"(?!\w)", normalize_text(text)))

def _job_supported(requirement, category, job_text):
    if is_instruction_like(requirement):
        return False
    if category in {"required_skills", "preferred_skills"}:
        return skill_span(job_text, requirement) is not None and any(
            supports_claim(requirement, line, "skills") and not is_instruction_like(line)
            for line in job_text.splitlines() or [job_text]
        )
    return any(_literal_match(requirement, line) and not is_instruction_like(line)
               for line in job_text.splitlines() or [job_text])

def _candidate_status(requirement, category, all_facts):
    prefixes = {
        "required_skills": ("skills", "technical_skills", "soft_skills", "certifications"),
        "preferred_skills": ("skills", "technical_skills", "soft_skills", "certifications"),
        "experience_projects": ("experience", "employment_history", "internships", "projects", "achievements"),
        "education": ("education", "education_details", "certifications"),
        "role_alignment": ("summary", "experience", "employment_history", "internships", "projects"),
    }[category]
    facts = [item for item in all_facts if _field_matches(item, prefixes)]
    verified = [item for item in facts if item["status"] == "verified"]
    uncertain = [item for item in facts if item["status"] != "verified"]
    if category in {"required_skills", "preferred_skills"}:
        matches = [(skill_match(item["value"], requirement), item) for item in verified]
        for status in ("exact", "alias", "related"):
            evidence = [item["quote"] for match, item in matches if match == status]
            if evidence:
                return status, list(dict.fromkeys(evidence)), 100.0 if status in {"exact", "alias"} else 0.0
        if any(skill_match(item["value"], requirement) in {"exact", "alias"} for item in uncertain):
            return "uncertain", [], 0.0
        return "missing", [], 0.0
    phrase = normalize_text(requirement)
    exact = [item["quote"] for item in verified if _literal_match(phrase, item["value"]) and supports_claim(requirement, item["quote"], item["field"])]
    if exact:
        return "exact", list(dict.fromkeys(exact)), 100.0
    if any(_literal_match(phrase, item["value"]) for item in uncertain):
        return "uncertain", [], 0.0
    # Role alignment is transparent lexical coverage, not a claim of experience.
    if category == "role_alignment":
        tokens = {token.casefold() for token in re.findall(r"[A-Za-z][A-Za-z0-9+#.]*", requirement)
                  if token.casefold() not in {"a", "an", "the", "of", "and", "for", "in", "at"}}
        matched, quotes = set(), []
        for item in verified:
            words = {word.casefold() for word in re.findall(r"[A-Za-z][A-Za-z0-9+#.]*", item["value"])}
            if tokens & words:
                matched |= tokens & words
                quotes.append(item["quote"])
        if matched:
            return "related", list(dict.fromkeys(quotes)), len(matched) / len(tokens) * 100.0
    return "missing", [], 0.0

def _validated_weights(weights):
    result = dict(DEFAULT_WEIGHTS)
    if weights is not None:
        if not isinstance(weights, dict) or set(weights) - set(DEFAULT_WEIGHTS):
            raise ValueError("Weights must use the five supported category names.")
        for name, value in weights.items():
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
                raise ValueError("Weights must be finite nonnegative numbers.")
            result[name] = float(value)
    if not math.isfinite(sum(result.values())) or sum(result.values()) <= 0:
        raise ValueError("At least one category weight must be positive.")
    return result

def analyze_career(resume_data: dict, job_data: dict, source_text: str, job_text: str, weights: dict | None = None) -> dict:
    """No ungrounded candidate claim earns credit. Missing JOB categories alone
    are excluded from the denominator; candidate omissions always retain zero.
    Skill relatedness never earns equivalence credit. Other requirements require
    a literal supported phrase; role alignment reports lexical coverage only.
    """
    resume_data = resume_data if isinstance(resume_data, dict) else {}
    job_data = job_data if isinstance(job_data, dict) else {}
    base_weights = _validated_weights(weights)
    facts = verified_evidence(resume_data, source_text)
    requested = _job_requirements(job_data, job_text)
    denominator = sum(base_weights[name] for name, values in requested.items() if values)
    if any(requested.values()) and denominator <= 0:
        raise ValueError("At least one available job category must have a positive weight.")
    categories, requirements, gaps, mandatory_unmet = [], [], [], []
    total = 0.0
    for category, values in requested.items():
        points = []
        for value in values:
            priority = requirement_priority(value, job_text, skill=category in {"required_skills", "preferred_skills"})
            mandatory = category in {"required_skills", "experience_projects", "education"} and priority != "preferred"
            if not _job_supported(value, category, job_text):
                mandatory = False
                status, quotes, credit = "uncertain", [], 0.0
                reason = "The job requirement has no verified source evidence; review its extraction."
            else:
                status, quotes, credit = _candidate_status(value, category, facts)
                reasons = {
                    "exact": "Supported by a literal source-backed candidate fact.",
                    "alias": "Supported by a curated equivalent skill alias.",
                    "related": "Related evidence is not proof of the required skill or qualification.",
                    "missing": "No supporting candidate evidence was found.",
                    "uncertain": "The candidate claim exists but could not be grounded in the resume.",
                }
                reason = reasons[status]
            requirements.append({"category": category, "requirement": value, "status": status,
                                 "evidence": quotes, "mandatory": mandatory})
            points.append(credit)
            if mandatory and status not in {"exact", "alias"}:
                mandatory_unmet.append(value)
            if category in {"required_skills", "preferred_skills"} and status not in {"exact", "alias"}:
                priority = "unclear" if status == "uncertain" else ("required" if mandatory else "preferred")
                activities = (
                    [f"Review the source evidence for {value}; add a factual example only if you already possess it."]
                    if priority == "unclear" else
                    [f"Study the fundamentals of {value} and complete a small practical exercise.",
                     f"Build a project using {value}; describe only work you actually complete."]
                )
                gaps.append({"skill": value, "priority": priority, "reason": reason, "activities": activities})
        score = sum(points) / len(points) if points else 0.0
        weight = base_weights[category] / denominator * 100.0 if values and denominator else 0.0
        total += score * weight / 100.0
        explanation = (
            "Not specified by this job; its weight is redistributed across available job categories."
            if not values else
            ("Lexical coverage of the role title in verified candidate facts; not proof of role eligibility."
             if category == "role_alignment" else
             "Only source-backed exact matches and curated skill aliases receive full credit; related or unsupported claims receive none.")
        )
        categories.append({"key": category, "label": LABELS[category], "base_weight": base_weights[category],
                           "weight": round(weight, 4), "score": round(score, 2),
                           "available": bool(values), "explanation": explanation})
    # Other explicit qualifications remain visible without inventing a sixth
    # weighted category. They do not silently change the five configured weights.
    for value in dict.fromkeys(_strings(job_data.get("other_qualifications"))):
        mandatory = requirement_priority(value, job_text) == "required"
        source_backed = _job_supported(value, "other_qualifications", job_text)
        evidence = [item["quote"] for item in facts if item["status"] == "verified"
                    and supports_claim(value, item["quote"], item["field"])]
        status = "exact" if source_backed and evidence else "missing" if source_backed else "uncertain"
        requirements.append({"category": "other_qualifications", "requirement": value, "status": status,
                             "evidence": list(dict.fromkeys(evidence)), "mandatory": mandatory})
        if mandatory and status != "exact":
            mandatory_unmet.append(value)
    gaps.sort(key=lambda gap: {"required": 0, "unclear": 1, "preferred": 2}[gap["priority"]])
    return {
        "algorithm_version": ALGORITHM_VERSION,
        "profile_version": input_version(resume_data, source_text),
        "job_version": input_version(job_data, job_text),
        "overall_score": round(max(0.0, min(100.0, total)), 2),
        "categories": categories, "requirements": requirements,
        "mandatory_unmet": list(dict.fromkeys(mandatory_unmet)), "gaps": gaps,
        "ats": analyze_ats(source_text, resume_data, job_data),
        "disclaimer": DISCLAIMER,
    }

def analyze_ats(source_text: str, resume_data: dict | None = None, job_data: dict | None = None) -> dict:
    """Text-based checks only; retained original PDF layout is not assumed."""
    text = source_text if isinstance(source_text, str) else ""
    profile = resume_data if isinstance(resume_data, dict) else {}
    job = job_data if isinstance(job_data, dict) else {}
    checks = []
    def add(key, label, status, detail, suggestion):
        checks.append({"key": key, "label": label, "status": status, "detail": detail, "suggestion": suggestion})
    letters = sum(char.isalpha() for char in text)
    readable = len(text.strip()) >= 50 and letters >= 25
    add("text_extraction", "Readable extracted text", "pass" if readable else "fail",
        "Readable text is available." if readable else "Too little readable text was extracted.",
        "Keep a text-based PDF; scanned resumes need accessible text before analysis.")
    email = bool(re.search(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text))
    phone_candidates = re.findall(r"(?<!\d)(?:\+?\d[\d ()-]{6,}\d)(?!\d)", text)
    phone = any(10 <= sum(char.isdigit() for char in value) <= 15 for value in phone_candidates)
    add("contact", "Contact information", "pass" if email and phone else "warn",
        "Email and a phone-like contact are present." if email and phone else "Email or phone contact could not be confirmed in the extracted text.",
        "Use a readable email address and contact number in the document body.")
    heading_names = {
        "education": r"education|academic(?: background)?",
        "experience": r"(?:work |professional )?experience|employment|internships?",
        "skills": r"(?:technical |key )?skills|technologies",
        "projects": r"(?:selected |academic )?projects",
    }
    headings = [name for name, pattern in heading_names.items()
                if re.search(rf"(?im)^\s*(?:{pattern})\s*(?::|$)", text)]
    add("sections", "Recognizable section headings", "pass" if len(headings) >= 2 else "warn",
        f"{len(headings)} common section headings were found.",
        "Use clear headings such as Education, Skills, Experience and Projects where relevant.")
    replacement = "\ufffd" in text
    add("characters", "Text encoding", "warn" if replacement else "pass",
        "Replacement characters may indicate extraction problems." if replacement else "No Unicode replacement characters were detected.",
        "Export a text-based PDF with standard fonts and recheck extracted text.")
    words = len(text.split())
    add("length", "Content available for review", "pass" if 80 <= words <= 1500 else "warn",
        f"{words} extracted words are available; this is a heuristic, not a page limit.",
        "Keep relevant factual detail concise; add evidence of completed work where appropriate.")
    suspicious = is_instruction_like(text)
    add("embedded_instructions", "Untrusted instruction content", "warn" if suspicious else "pass",
        "Instruction-like text was detected and must not be used as candidate evidence." if suspicious else "No obvious instruction-like text was detected.",
        "Remove instructions aimed at AI systems; keep only candidate facts.")
    required = unique_skills(_strings(job.get("required_skills")))
    evidence = verified_evidence(profile, text)
    candidate = [item["value"] for item in evidence if item["status"] == "verified" and
                 _field_matches(item, ("skills", "technical_skills", "soft_skills", "certifications"))]
    matched = sum(any(skill_match(value, skill) in {"exact", "alias"} for value in candidate) for skill in required)
    keyword_relevance = round(matched / len(required) * 100.0, 2) if required else None
    points = {"pass": 1.0, "warn": 0.5, "fail": 0.0}
    technical = sum(points[check["status"]] for check in checks) / len(checks) * 100.0
    if not readable:
        technical = min(technical, 20.0)
    return {"technical_score": round(technical, 2), "checks": checks, "keyword_relevance": keyword_relevance,
            "limitations": [
                "These checks analyze extracted text, not any employer's proprietary ATS.",
                "Original PDF layout, reading order, columns, images and font embedding cannot be confirmed from stored text alone.",
                "Keyword relevance is separate from technical readability and uses only verified extracted skills.",
            ], "disclaimer": ATS_DISCLAIMER}
