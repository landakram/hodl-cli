default: compile

clean:
	rm -rf dist/*
	rm -rf venv

compile:
	python setup.py bdist_wheel

upload:
	twine register -r pypi dist/*
	twine upload -r pypi dist/*

docs: compile
	virtualenv venv
	. venv/bin/activate && pip install dist/* && gdax_recurring -h > README
	rm -rf venv
