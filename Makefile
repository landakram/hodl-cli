default: compile

clean:
	rm dist/*

compile:
	python setup.py bdist_wheel

upload:
	twine register -r pypi dist/*
	twine upload -r pypi dist/*
