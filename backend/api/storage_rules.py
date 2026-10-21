"""Pure validation rules for storage intake; call inside authenticated DB transactions.

These rules are not an API and MUST NOT be treated as authorization.
"""
import re

PHOTO_KINDS = frozenset({"front", "rear", "left", "right", "vin", "dashboard", "damage", "other", "pts"})
REQUIRED_INTAKE_PHOTOS = frozenset({"front", "rear", "left", "right"})
ALLOWED_TRANSITIONS = {
    "draft": frozenset({"stored", "cancelled"}),
    "stored": frozenset({"return_requested"}),
    "return_requested": frozenset({"returned", "stored"}),
    "returned": frozenset(),
    "cancelled": frozenset(),
}

def normalize_vin(value: str) -> str:
    """Normalize for duplicate detection; do not incorrectly impose 17 chars on frame IDs."""
    return re.sub(r"[\s-]+", "", value or "").upper()

def photo_validation_errors(photos: list[dict]) -> list[str]:
    errors = []
    kinds = set()
    for photo in photos:
        kind = photo.get("kind")
        if kind not in PHOTO_KINDS:
            errors.append("Unknown photo category")
            continue
        if photo.get("deleted_at"):
            continue
        if kind == "damage" and not str(photo.get("note") or "").strip():
            errors.append("Damage photo needs a description")
        kinds.add(kind)
    missing = REQUIRED_INTAKE_PHOTOS - kinds
    if missing:
        errors.append("Missing intake photos: " + ", ".join(sorted(missing)))
    return errors

def validate_transition(old_status: str, new_status: str, photos: list[dict]) -> None:
    """Raises ValueError. Caller must lock row and commit transition and event atomically."""
    if new_status not in ALLOWED_TRANSITIONS.get(old_status, frozenset()):
        raise ValueError(f"Invalid storage transition: {old_status} -> {new_status}")
    if new_status == "stored":
        errors = photo_validation_errors(photos)
        if errors:
            raise ValueError("; ".join(errors))
    if new_status == "returned" and old_status != "return_requested":
        raise ValueError("Return must be requested before completing handover")
