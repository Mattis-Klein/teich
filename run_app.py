from pathlib import Path
from app.app import run

if __name__ == "__main__":
    # This script expects to live in the project root (sukkah_teich_sample)
    run(Path(__file__).resolve().parent)
