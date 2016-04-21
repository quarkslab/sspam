#!/bin/bash

# Function to test return status of command
function test {
    "$@"
    local status=$?
    if [ $status -ne 0 ]; then
        echo "[$1] Fail!" >&2
    	exit $status
    fi
    echo "[$1] Success!" >&2
    return $status
}

# Main sspam modules
lint_dirs="sspam/ tests/"

flake8conf=".flake8"
test flake8 --config=$flake8conf $lint_dirs

# Run pylint
pylint_conf=".pylintrc"
test pylint --rcfile=$pylint_conf $lint_dirs

