from app.schemas.travel import ValidationResult


def finalize_validation(result: ValidationResult) -> ValidationResult:
    """Remove exact target duplicates, retaining distinct POIs and hotel route targets."""
    unique = {}
    for issue in result.issues:
        key = (issue.day, issue.type, issue.activity_id or issue.target)
        previous = unique.get(key)
        if previous is None or (issue.blocking and not previous.blocking):
            unique[key] = issue
    result.issues = list(unique.values())
    result.unverified_checks = list(dict.fromkeys(result.unverified_checks))
    result.confirmed_count = sum(i.status == "confirmed" for i in result.issues)
    result.blocking_confirmed_count = sum(i.blocking for i in result.issues)
    result.unverified_count = sum(i.status == "unverified" for i in result.issues)
    result.informational_count = sum(i.status == "informational" for i in result.issues)
    result.valid = result.blocking_confirmed_count == 0
    return result
