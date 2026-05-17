#!/bin/bash
set -e

# Update OAI-OpenAPI-Specification which uses 'main'
echo "Updating OAI-OpenAPI-Specification..."
cd OAI-OpenAPI-Specification
git checkout main
git pull origin main
cd ..

# Array of cdd submodules
submodules=(
  "cdd-c" "cdd-cpp" "cdd-csharp" "cdd-go" "cdd-java" "cdd-kotlin"
  "cdd-php" "cdd-python-all" "cdd-ruby" "cdd-rust" "cdd-sh" "cdd-swift" "cdd-ts"
)

for sub in "${submodules[@]}"; do
  echo "Updating $sub..."
  cd "$sub"
  
  # Commit any local changes made during this session to the submodule first
  if ! git diff-index --quiet HEAD --; then
    echo "Committing local changes in $sub before pulling..."
    git add .
    git commit -m "Update tests, compliance tables, and bug fixes" || true
  fi
  
  # Checkout master and pull
  git checkout master
  git pull origin master --rebase || true # We will handle rebase conflicts if they happen
  
  # Push up the local changes to remote master
  git push origin master
  
  cd ..
done
echo "Submodules updated."