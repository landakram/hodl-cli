default: compile

clean:
	rm -rf dist/*
	rm -rf venv

compile:
	poetry build

install:
	virtualenv venv
	./venv/bin/pip install dist/*.whl

upload:
	poetry publish

docs: compile
	virtualenv venv
	. venv/bin/activate && pip install dist/*.whl && hodl-cli -h > README
	rm -rf venv
