"""Download spaCy English model for ticker mapping."""

import subprocess
import sys


def main():
    subprocess.check_call(
        [sys.executable, "-m", "spacy", "download", "en_core_web_sm"]
    )
    print("spaCy model en_core_web_sm installed.")


if __name__ == "__main__":
    main()
