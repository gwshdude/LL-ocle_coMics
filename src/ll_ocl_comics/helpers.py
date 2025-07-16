
def remove_between_anchors(text: str, anchor: str) -> str:
    """Removes everything from the first occurrence of `anchor` up to
    and including the second occurrence of `anchor`, then strips whitespace.
    If fewer than two anchors are found, returns text stripped.

    Args:
        text (str): The input string.
        anchor (str): The anchor substring.

    Returns:
        str: The text with the first-2-anchor span removed.
    """
    first = text.find(anchor)
    if first == -1:
        # no anchor at all
        return text.strip()

    second = text.find(anchor, first + len(anchor))
    if second == -1:
        # only one anchor
        return text.strip()

    # build result: up to first anchor, then after second anchor
    result = text[:first] + text[second + len(anchor):]
    return result.strip()
