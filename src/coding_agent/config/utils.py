"""Shared utilities - will be implemented as needed."""


def truncate_output(text: str, max_length: int = 30000) -> str:
    """Truncate output to max_length characters.

    Args:
        text: The text to truncate
        max_length: Maximum length (default 30000)

    Returns:
        Truncated text with indicator appended
    """
    if len(text) <= max_length:
        return text

    truncated = text[:max_length]
    indicator = "\n\n[Output truncated - showing first 30000 characters]"
    return truncated + indicator
