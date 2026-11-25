"""Validate artifact filenames before storing them or writing them to disk."""

from pathlib import PureWindowsPath


def safe_filename(filename: str) -> str:
    if (
        not filename or filename in {".", ".."} or filename.endswith((" ", "."))
        or PureWindowsPath(filename).is_reserved()
        or any(char in '/\\:<>"|?*' or ord(char) < 32 or ord(char) == 127 for char in filename)
        or len(filename.encode("utf-8")) > 255
    ):
        raise ValueError("Use a plain filename without paths or special characters.")
    return filename



def safe_runner_data_filename(filename: str) -> str:
    filename = safe_filename(filename)
    if filename.casefold() in {"loadtest.js", "perfagent-preflight.js", "perfagent-summary.json", "perfagent-verification.jsonl"}:
        raise ValueError("This filename is reserved by the load runner.")
    return filename
