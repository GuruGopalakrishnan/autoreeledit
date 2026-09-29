"""Groups word-level timestamps into caption blocks for the timeline editor -- the same cue-grouping concept srt_parser.py's transcripts already carry, generalized so Whisper-sourced words (no natural cue boundaries) get sensible ones too."""

import re

_GAP_THRESHOLD = 0.6  # seconds of silence between words that starts a new caption block


def assign_synthetic_cue_ids(words: list[dict]) -> None:
    """Mutates `words` in place, adding a `cue_id` to any word that doesn't
    already have one (i.e. Whisper output, which has no natural phrase
    boundaries) based on pause gaps -- so the timeline still shows sensible
    caption blocks instead of one word per block."""
    cue_id = 0
    prev_end: float | None = None
    for w in words:
        if "cue_id" in w:
            prev_end = w["end"]
            continue
        if prev_end is not None and w["start"] - prev_end > _GAP_THRESHOLD:
            cue_id += 1
        w["cue_id"] = cue_id
        prev_end = w["end"]


def group_into_captions(words: list[dict]) -> list[dict]:
    """Returns one entry per cue_id: {id, start, end, text, isKeyword}."""
    groups: dict[int, list[dict]] = {}
    for w in words:
        groups.setdefault(w["cue_id"], []).append(w)

    captions = []
    for cue_id in sorted(groups.keys()):
        ws = groups[cue_id]
        captions.append(
            {
                "id": cue_id,
                "start": ws[0]["start"],
                "end": ws[-1]["end"],
                "text": " ".join(w["text"] for w in ws),
                "isKeyword": any(w["is_keyword"] for w in ws),
                "titleMoment": ws[0].get("title_moment"),
            }
        )
    return captions


def replace_caption_text(words: list[dict], cue_id: int, new_text: str, keyword_set: set[str]) -> list[dict]:
    """
    Returns a new words list with the given cue's words replaced by ones
    derived from `new_text`, spread evenly across the cue's ORIGINAL
    [start, end] window (its timing doesn't change, just what's said) --
    same even-distribution approach used everywhere else a word list is
    built without a better timing signal.
    """
    cue_words = [w for w in words if w["cue_id"] == cue_id]
    if not cue_words:
        return words

    start, end = cue_words[0]["start"], cue_words[-1]["end"]
    existing_title_moment = cue_words[0].get("title_moment")  # preserve an applied Title Moment across a wording edit
    tokens = new_text.split()
    span = max(end - start, 0.1)
    per_word = span / max(1, len(tokens))

    replacement = []
    for i, token in enumerate(tokens):
        clean = re.sub(r"[^\w]", "", token).lower()
        replacement.append(
            {
                "text": token,
                "start": start + i * per_word,
                "end": start + (i + 1) * per_word,
                "is_keyword": clean in keyword_set,
                "cue_id": cue_id,
                "title_moment": existing_title_moment,
            }
        )

    result = [w for w in words if w["cue_id"] != cue_id]
    insert_at = next((i for i, w in enumerate(words) if w["cue_id"] == cue_id), len(result))
    result[insert_at:insert_at] = replacement
    return result


def set_caption_keyword(words: list[dict], cue_id: int, force_keyword: bool) -> None:
    """Mutates `words` in place, flagging (or clearing) every word in a cue as a keyword moment -- lets the editor force/unforce the Dramatic trigger for one caption by hand."""
    for w in words:
        if w["cue_id"] == cue_id:
            w["is_keyword"] = force_keyword


def set_caption_title_moment(words: list[dict], cue_id: int, title_moment: str | None) -> None:
    """
    Mutates `words` in place, tagging every word in a cue with a Title
    Moment preset id (or clearing it with None) -- this is the general
    form of set_caption_keyword: instead of only being able to force the
    Dramatic trigger, the editor can apply any named preset (Starburst,
    Cutout Title, Black Pause, ...) to just this one caption. Checked first,
    ahead of every rule-based trigger, in compositor._pick_style.
    """
    for w in words:
        if w["cue_id"] == cue_id:
            w["title_moment"] = title_moment
