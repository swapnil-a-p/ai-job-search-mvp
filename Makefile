PYTHON ?= python3
VENV ?= .venv

.PHONY: setup run validate clean

setup:
	$(PYTHON) -m venv $(VENV)
	. $(VENV)/bin/activate && pip install -r requirements.txt

run:
	. $(VENV)/bin/activate && python main.py

validate:
	$(PYTHON) -m py_compile *.py

clean:
	rm -rf __pycache__ .pytest_cache
