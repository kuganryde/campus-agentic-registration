import os
import pytest

# Inject mock API key into environment before any module imports
os.environ["GEMINI_API_KEY"] = "mock_test_key_for_ci_runner"
os.environ["GOOGLE_API_KEY"] = "mock_test_key_for_ci_runner"