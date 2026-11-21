"""Runs before any test. It makes sure the tests never touch the real database,
the real Gemini key or the real secret key from your .env file."""
import os
import sys
from pathlib import Path

# These must be set BEFORE the app's files are imported (load_dotenv never overrides them).
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-only-used-by-the-tests"
os.environ["GEMINI_API_KEY"] = ""   # empty = no AI, so outfits always use the rule-based picker

# Lets the tests do "import outfits", "import security" from the backend folder.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
