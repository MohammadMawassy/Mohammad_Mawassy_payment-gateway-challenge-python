.PHONY: install
install:
	@poetry install 

.PHONY: run
run:
	@poetry run python main.py

.PHONY: test
test: 
	@poetry run python -m pytest -vv