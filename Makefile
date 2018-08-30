black:
ifndef BLACKBIN
	echo "black needs Py3 env, define env var BLACKBIN pointing to the black executable"
	exit 1
endif
	${BLACKBIN} -l 120 docs kw test setup.py
