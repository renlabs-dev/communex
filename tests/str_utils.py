import re

# remove all weird non-alphanumeric characters, such as table borders
_clean_pattern = re.compile("[^a-zA-Z0-9_\\s'\"-:;%.]", re.UNICODE)


def clean(text: str) -> str:
    """ removes extra spaces and weird non-alphanumeric characters from a string."""
    text = re.sub(_clean_pattern, '', text)

    return " ".join(text.split())