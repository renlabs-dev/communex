from pathlib import Path

TEST_TEMPORARY_KEY = "warn_temporary_key_983"

TEST_FAKE_MNEM_DO_NOT_USE_THIS = "spy odor tomato foam supreme double vanish minute quarter anxiety wagon hundred"


def delete_temporary_key():
    """ WARNING: this function deletes the key from the disk. USE WITH CAUTION."""

    path = Path(Path.home(), ".commune", "key", TEST_TEMPORARY_KEY+".json")
    if path.exists():
        path.unlink()