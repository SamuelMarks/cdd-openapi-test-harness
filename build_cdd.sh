#!/bin/bash
# ==========================================
# Script: build_cdd.sh
# Description: Installs dependencies and builds the cdd-ts package.
# Usage: ./build_cdd.sh
# ==========================================

cd cdd-ts || exit 1
npm i
npm run build
