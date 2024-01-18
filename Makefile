.PHONY: docs_run

docs_run:
	@echo "URL: http://localhost:8080/communex"
	pdoc -n --docformat google ./src/communex 

docs_generate:
	pdoc communex 							\
		--docformat google 					\
		--output-directory ./docs/_build 	\
		--logo assets/logo.png 				\
		--favicon assets/favicon.ico 		\
		--logo-link https://github.com/agicommies/communex \
		--edit-url communex=https://github.com/agicommies/communex/blob/main/src/communex/

docs_copy_assets:
	mkdir -p ./docs/_build/assets
	cp -r ./docs/assets ./docs/_build/

docs_build: docs_generate docs_copy_assets
