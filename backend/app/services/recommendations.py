from datetime import datetime, timedelta, timezone

from app.models.discovery import ExternalJobListing, JobPreference, RecommendationCache
from app.models.intelligence import ResumeVersion
from app.services.career_intelligence import ALGORITHM_VERSION, analyze_career
from app.services.career_repository import resume_source
from app.services.discovery_repository import fingerprint


RECOMMENDATION_VERSION = f"{ALGORITHM_VERSION}+preferences-v1"


def _contains(value: str | None, choices: list[str]) -> bool:
    text = (value or "").casefold()
    return any(choice.casefold() in text for choice in choices if choice.strip())


def preference_score(listing: ExternalJobListing, preference: JobPreference | None) -> tuple[float, list[str]]:
    if preference is None:
        return 50.0, ["No job preferences saved; ranking uses career compatibility only."]
    checks: list[tuple[bool, str]] = []
    if preference.roles_json:
        checks.append((_contains(listing.title, preference.roles_json), "preferred role"))
    if preference.locations_json:
        checks.append((_contains(listing.location, preference.locations_json), "preferred location"))
    if preference.job_types_json:
        checks.append((_contains(listing.job_type, preference.job_types_json), "preferred job type"))
    if preference.remote_policy != "any":
        text = f"{listing.location or ''} {listing.description or ''}".casefold()
        if preference.remote_policy == "remote":
            checks.append(("remote" in text or "work from home" in text, "remote preference"))
        elif preference.remote_policy == "hybrid":
            checks.append(("hybrid" in text, "hybrid preference"))
        else:
            checks.append((not any(word in text for word in ("remote", "work from home", "hybrid")), "onsite preference"))
    if not checks:
        return 50.0, ["No ranking preferences selected."]
    matched = [label for passed, label in checks if passed]
    missed = [label for passed, label in checks if not passed]
    details = ([f"Matches {', '.join(matched)}."] if matched else []) + ([f"Does not match {', '.join(missed)}."] if missed else [])
    return round(sum(1 for passed, _ in checks if passed) * 100 / len(checks), 1), details


def recommend(db, user_id: int, limit: int = 20) -> list[dict]:
    resume = db.query(ResumeVersion).filter_by(user_id=user_id, approved=True).order_by(
        ResumeVersion.revision.desc()).first()
    if resume is None:
        return []
    source = resume_source(db, resume)
    preference = db.query(JobPreference).filter_by(user_id=user_id).first()
    now = datetime.now(timezone.utc)
    listings = db.query(ExternalJobListing).filter(ExternalJobListing.is_active.is_(True)).order_by(
        ExternalJobListing.published_at.desc(), ExternalJobListing.fetched_at.desc()).limit(200).all()
    results = []
    for listing in listings:
        pref_score, pref_details = preference_score(listing, preference)
        input_hash = fingerprint({"resume": resume.fingerprint, "listing": listing.content_fingerprint,
                                  "preference_version": preference.version if preference else 0})
        cached = db.query(RecommendationCache).filter_by(
            user_id=user_id, listing_id=listing.id, algorithm_version=RECOMMENDATION_VERSION,
            input_hash=input_hash).first()
        expiry = cached.expires_at if cached else None
        if expiry and expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if cached and expiry and expiry > now and cached.listing_fetched_at == listing.fetched_at:
            result = cached.result_json
        else:
            job_data = {"title": listing.title, "company": listing.company,
                        "required_skills": listing.skills_json or [], "preferred_skills": [],
                        "location": listing.location, "employment_type": listing.job_type,
                        "experience_requirements": [listing.experience_text] if listing.experience_text else [],
                        "education_requirements": [], "other_qualifications": [],
                        "key_responsibilities": []}
            analysis = analyze_career(resume.data_json, job_data, source, listing.description)
            compatibility = analysis["overall_score"]
            ranking = round(compatibility * 0.85 + pref_score * 0.15, 1)
            result = {"listing_id": listing.id, "compatibility_score": compatibility,
                      "preference_score": pref_score, "ranking_score": ranking,
                      "preference_explanation": pref_details,
                      "missing_required": [item["requirement"] for item in analysis["requirements"]
                                           if item["mandatory"] and item["status"] in {"missing", "uncertain"}],
                      "preferred_gaps": [gap["skill"] for gap in analysis["gaps"] if gap["priority"] == "preferred"],
                      "categories": analysis["categories"], "requirements": analysis["requirements"],
                      "disclaimer": "Compatibility is evidence-based guidance, not a prediction of hiring success."}
            if cached is None:
                cached = RecommendationCache(user_id=user_id, listing_id=listing.id,
                    resume_version_id=resume.id, algorithm_version=RECOMMENDATION_VERSION,
                    input_hash=input_hash, result_json=result, listing_fetched_at=listing.fetched_at,
                    expires_at=now + timedelta(hours=1))
                db.add(cached)
            else:
                cached.result_json, cached.listing_fetched_at = result, listing.fetched_at
                cached.expires_at = now + timedelta(hours=1)
        results.append({**result, "listing": {"id": listing.id, "title": listing.title,
            "company": listing.company, "location": listing.location, "job_type": listing.job_type,
            "provider": listing.provider, "application_url": listing.application_url,
            "published_at": listing.published_at, "fetched_at": listing.fetched_at}})
    db.flush()
    return sorted(results, key=lambda item: (-item["ranking_score"], -item["compatibility_score"], item["listing_id"]))[:limit]
