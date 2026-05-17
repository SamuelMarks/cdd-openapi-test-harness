#!/bin/bash
set -e

# Array of cdd submodules
submodules=(
  "cdd-c" "cdd-cpp" "cdd-csharp" "cdd-go" "cdd-java" "cdd-kotlin"
  "cdd-php" "cdd-python-all" "cdd-ruby" "cdd-rust" "cdd-sh" "cdd-swift" "cdd-ts"
)

for sub in "${submodules[@]}"; do
  echo "Updating $sub..."
  cd "$sub"
  
  if ! git diff-index --quiet HEAD --; then
    echo "Committing Markdown text updates in $sub..."
    git add .
    git commit -m "docs: update compliance documentation to explicitly reference both Swagger 2.0 and OpenAPI 3.2.0" || true
    git push origin master
  fi
  
  cd ..
done
echo "Markdown Submodules updated."