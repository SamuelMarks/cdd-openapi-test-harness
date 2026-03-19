#!/bin/bash
# ==========================================
# Script: run_tests.sh
# Description: Executes tests within the cdd-ts package.
# Usage: ./run_tests.sh
# ==========================================

cd cdd-ts || exit 1
npm run test --run
