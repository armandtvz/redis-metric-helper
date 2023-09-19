build:
	python3 -m build && \
	pip install twine --upgrade && \
	twine upload dist/*

coverage:
	pytest --cov=metric_helper --cov-report html
