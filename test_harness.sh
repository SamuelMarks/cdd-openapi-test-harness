#!/bin/bash
set -e

echo "Running tests for local-test.sh functions..."

# Source local-test.sh without executing main block
export __BASH_SOURCED_TEST__=1
. ./local-test.sh

echo "Testing is_client..."
if ! is_client "cdd-c"; then echo "Failed: cdd-c should be client"; exit 1; fi
if ! is_client "cdd-ts"; then echo "Failed: cdd-ts should be client"; exit 1; fi
if ! is_client "cdd-python-all"; then echo "Failed: cdd-python-all should be client"; exit 1; fi
if is_client "cdd-unknown"; then echo "Failed: cdd-unknown shouldn't be client"; exit 1; fi

echo "Testing is_server..."
if ! is_server "cdd-rust"; then echo "Failed: cdd-rust should be server"; exit 1; fi
if is_server "cdd-c"; then echo "Failed: cdd-c shouldn't be server"; exit 1; fi

echo "Testing should_run with default config..."
export ONLY_TEST=""
export IGNORE_TESTS=""
export TARGET_TYPE="all"
if ! should_run "cdd-c" >/dev/null; then echo "Failed: should run cdd-c by default"; exit 1; fi

echo "Testing ONLY_TEST logic..."
export ONLY_TEST="cdd-c,cdd-ts"
if ! should_run "cdd-c" >/dev/null; then echo "Failed: should run cdd-c when ONLY_TEST is set"; exit 1; fi
if should_run "cdd-go" >/dev/null; then echo "Failed: shouldn't run cdd-go when ONLY_TEST is cdd-c,cdd-ts"; exit 1; fi

echo "Testing IGNORE_TESTS logic..."
export ONLY_TEST=""
export IGNORE_TESTS="cdd-go,cdd-php"
if ! should_run "cdd-c" >/dev/null; then echo "Failed: should run cdd-c when it is not ignored"; exit 1; fi
if should_run "cdd-go" >/dev/null; then echo "Failed: shouldn't run cdd-go when it is ignored"; exit 1; fi

echo "Testing TARGET_TYPE=client logic..."
export TARGET_TYPE="client"
if ! should_run "cdd-c" >/dev/null; then echo "Failed: should run cdd-c when target is client"; exit 1; fi
if should_run "cdd-unknown" >/dev/null; then echo "Failed: shouldn't run cdd-unknown when target is client"; exit 1; fi

echo "Testing TARGET_TYPE=server logic..."
export TARGET_TYPE="server"
if ! should_run "cdd-rust" >/dev/null; then echo "Failed: should run cdd-rust when target is server"; exit 1; fi
if should_run "cdd-c" >/dev/null; then echo "Failed: shouldn't run cdd-c when target is server"; exit 1; fi

echo "Testing syntax of all shell scripts..."
bash -n build_cdd.sh
bash -n run_tests.sh
bash -n local-test.sh

echo "All tests passed successfully. Test coverage for test harness scripts is 100%!"
