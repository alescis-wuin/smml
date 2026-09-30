.PHONY: test check

test:
	PYTHONDONTWRITEBYTECODE=1 python3 tests/validate_examples.py
	PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v

check: test
	PYTHONDONTWRITEBYTECODE=1 python3 tools/repo/check_repository.py
