from typing import Dict, List


def normalize_value(value: float, min_value: float = 0.0, max_value: float = 1.0) -> float:
    if value <= min_value:
        return 0.0
    if value >= max_value:
        return 1.0
    return (value - min_value) / (max_value - min_value)


def compute_event_score(event: Dict[str, object], config: Dict[str, object]) -> float:
    """Compute a weighted score for an event using audio and keyword signals."""
    scoring_cfg = config.get("scoring", {})
    audio_weight = float(scoring_cfg.get("audio_weight", 0.45))
    keyword_weight = float(scoring_cfg.get("keyword_weight", 0.40))
    density_bonus_weight = float(scoring_cfg.get("density_bonus", 0.10))
    proximity_bonus_weight = float(scoring_cfg.get("proximity_bonus", 0.05))

    audio_score = normalize_value(event.get("energy", 0.0), 0.0, event.get("max_energy", 1.0))
    keyword_score = normalize_value(event.get("keyword_hits", 0.0), 0.0, 3.0)
    density_bonus = min(event.get("keyword_hits", 0.0) * 0.1, 0.2) * density_bonus_weight
    proximity_bonus = min(1.0 / (1.0 + event.get("neighbor_gap", 10.0)), 0.2) * proximity_bonus_weight

    score = (
        audio_weight * audio_score +
        keyword_weight * keyword_score +
        density_bonus +
        proximity_bonus
    )
    return min(score, 1.0)


def rank_events(events: List[Dict[str, object]], config: Dict[str, object]) -> List[Dict[str, object]]:
    """Rank all candidate events using scoring and optional config filters."""
    if not events:
        return []

    max_energy = max(event.get("energy", 0.0) for event in events) or 1.0
    for event in events:
        event["max_energy"] = max_energy

    for i, event in enumerate(events):
        nearest_gap = min(
            [abs(event["start"] - other["start"]) for j, other in enumerate(events) if j != i] or [10.0]
        )
        event["neighbor_gap"] = nearest_gap
        event["score"] = compute_event_score(event, config)

    events.sort(key=lambda x: x["score"], reverse=True)
    return events
