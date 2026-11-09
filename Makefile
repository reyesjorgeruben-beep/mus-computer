VENV_PYTHON := $(firstword $(wildcard .venv/Scripts/python.exe .venv/bin/python))
PYTHON ?= $(if $(VENV_PYTHON),$(VENV_PYTHON),python)
PYTHON_PATHS := src scripts tests api.py setup.py

.PHONY: format format-check docs docs-check

docs:
	$(PYTHON) -m mus_computer.documentation build

docs-check:
	$(PYTHON) -m mus_computer.documentation check

format:
	$(PYTHON) -m ruff format $(PYTHON_PATHS)

format-check:
	$(PYTHON) -m ruff format --check $(PYTHON_PATHS)
