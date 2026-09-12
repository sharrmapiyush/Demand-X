import pytest
import sys

if __name__ == "__main__":
    ret_code = pytest.main([
        "tests/integration/test_ingestion_pipeline.py",
        "tests/integration/test_dvet_pipeline.py",
        "tests/unit/test_ingestion.py",
        "-v"
    ])
    sys.exit(ret_code)
