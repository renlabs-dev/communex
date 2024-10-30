.PHONY: all clean check lint type_check test test_slow docs_run docs_generate docs_copy_assets docs_build

all: check

clean:
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf dist

check: lint type_check

lint:
	ruff check ./src

fix:
	ruff check --fix ./src

type_check:
	pyright ./src

check_format:
	ruff format --check ./src

format:
	ruff format ./src

# fmt:
# 	isort ./src
# 	autopep8 --in-place --recursive ./src

test_all: test test_slow

test:
	pytest -k "not slow"

test_slow:
	pytest -k "slow"

docs_run:
	@echo "URL: http://localhost:8080/communex"
	pdoc -n --docformat google ./src/communex

docs_generate:
	pdoc communex \
		--docformat google \
		--output-directory ./docs/_build \
		--logo assets/logo.png \
		--favicon assets/favicon.ico \
		--logo-link https://github.com/agicommies/communex \
		--edit-url communex=https://github.com/agicommies/communex/blob/main/src/communex/

docs_copy_assets:
	mkdir -p ./docs/_build/assets
	cp -r ./docs/assets ./docs/_build/

docs_build: docs_generate docs_copy_assets
