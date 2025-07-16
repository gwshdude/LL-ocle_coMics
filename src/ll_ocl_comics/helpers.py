
def remove_between_anchors(text: str, anchor: str) -> str:
    """Removes everything from the first occurrence of `anchor` (an HTML tag
    name) up to and including the second occurrence of `anchor`, then strips
    whitespace. If fewer than two anchors are found, returns text stripped.
    
    Example:
        text="<think> I think I am string. <think> Strong!"
        anchor="think"
        returns "Strong!"

    Args:
        text (str): The input string.
        anchor (str): The anchor substring.

    Returns:
        str: The text with the first-2-anchor span removed.
    """
    anchor_open, anchor_close = f"<{anchor}>", f"</{anchor}>"
    first = text.find(anchor_open)
    if first == -1:
        # no anchor at all
        return text.strip()

    second = text.find(anchor_close, first + len(anchor_open))
    if second == -1:
        # only one anchor
        return text.strip()

    # build result: up to opening anchor, then after closing anchor
    result = text[:first] + text[second + len(anchor_close):]

    return result.strip()

if __name__ == "__main__":
    s = "<think> I think I am string. </think> Strong!"
    print(remove_between_anchors(s, "think"))  # outputs: Strong!
