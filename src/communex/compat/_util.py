import os.path


def ensure_dir_exists(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def ensure_parent_dir_exists(path: str) -> None:
    ensure_dir_exists(os.path.dirname(path))
