default: compile

clean:
	rm -rf dist/*
	rm -rf venv

compile:
	poetry build

upload:
	poetry publish

docs: compile
	virtualenv venv
	. venv/bin/activate && pip install dist/*.whl && hodl -h > README
	rm -rf venv
