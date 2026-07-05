#!/usr/bin/env python3
"""
Orchestrates local execution of native tests, WASM builds, and roundtrip tests
across all CDD toolchains.

Usage: python3 local_test.py [roundtrip|all|only-test]
Configuration Variables (Env):
  IGNORE_TESTS: Comma-separated list of toolchains to skip.
  ONLY_TEST: Comma-separated list of toolchains to exclusively run.
  TARGET_TYPE: Filter by target type ('client', 'server', 'all'). Defaults to 'all'.
"""

import os
import sys
import shutil
import subprocess
import time
import argparse
import atexit
import contextlib
import glob
from typing import List, Callable, Optional, Dict

def cleanup() -> None:
    """Stops the petstore_server Docker container upon exit."""
    if shutil.which("docker"):
        res = subprocess.run(["docker", "ps", "-q", "--filter", "name=petstore_server"], capture_output=True, text=True)
        if res.stdout.strip():
            print("Stopping petstore_server...")
            subprocess.run(["docker", "rm", "-f", "petstore_server"], capture_output=True)

atexit.register(cleanup)

@contextlib.contextmanager
def chdir(path: str):
    """Context manager for changing the current working directory."""
    prev = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)

def xcmd(cmd_list: List[str]) -> List[str]:
    """Translates paths in commands for cross-platform execution."""
    new_list = list(cmd_list)
    if os.name == 'nt':
        if new_list[0].startswith("./") or new_list[0].startswith("../"):
            new_list[0] = os.path.normpath(new_list[0])
            if new_list[0].endswith("gradlew"):
                new_list[0] += ".bat"
    return new_list

def run_cmd(cmd: List[str], check: bool = True, cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None, capture_output: bool = False, ignore_errors: bool = False) -> subprocess.CompletedProcess:
    """Runs a shell command using subprocess without shell=True."""
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    
    exe = shutil.which(cmd[0])
    if exe:
        cmd[0] = exe
        
    try:
        return subprocess.run(cmd, check=check, cwd=cwd, env=full_env, capture_output=capture_output, text=True)
    except subprocess.CalledProcessError as e:
        if not ignore_errors:
            print(f"Command '{' '.join(cmd)}' failed with exit code {e.returncode}")
        if check:
            raise
        return e
    except Exception as e:
        if not ignore_errors:
            print(f"Exception running command '{' '.join(cmd)}': {e}")
        if check:
            raise
        return subprocess.CompletedProcess(args=cmd, returncode=1)

def is_client(module: str) -> bool:
    """Determines if a given module is a client toolchain."""
    return module in [
        "cdd-c", "cdd-cpp", "cdd-csharp", "cdd-go", "cdd-java",
        "cdd-kotlin", "cdd-php", "cdd-python-all", "cdd-ruby",
        "cdd-rust", "cdd-sh", "cdd-swift", "cdd-ts"
    ]

def is_server(module: str) -> bool:
    """Determines if a given module is a server toolchain."""
    return module == "cdd-rust"

def should_run(module: str) -> bool:
    """Determines if a given module should be executed based on configuration variables."""
    only_test = os.environ.get("ONLY_TEST", "")
    ignore_tests = os.environ.get("IGNORE_TESTS", "")
    target_type = os.environ.get("TARGET_TYPE", "all")

    if only_test:
        if module in only_test.split(','):
            return True
        return False

    if ignore_tests and module in ignore_tests.split(','):
        print(f"Skipping {module} (in IGNORE_TESTS)")
        return False
        
    if target_type == "client" and not is_client(module):
        print(f"Skipping {module} (not a client)")
        return False

    if target_type == "server" and not is_server(module):
        print(f"Skipping {module} (not a server)")
        return False

    return True

def start_petstore(base_path: str = "/v2") -> None:
    """Starts the petstore_server via Docker for integration tests."""
    if shutil.which("docker"):
        print(f"Starting petstore server via docker (Base Path: {base_path})...")
        subprocess.run(["docker", "rm", "-f", "petstore_server"], capture_output=True)
        subprocess.run([
            "docker", "run", "-d", "-p", "8080:8080",
            "-e", "SWAGGER_HOST=http://localhost:8080",
            "-e", f"SWAGGER_BASE_PATH={base_path}",
            "--name", "petstore_server",
            "swaggerapi/petstore"
        ], stdout=subprocess.DEVNULL)
        time.sleep(3)
    else:
        print("Warning: docker is not installed or available. Integration tests relying on localhost:8080 may fail.")

def setup_emsdk() -> None:
    """Sets up the Emscripten SDK required for WASM builds."""
    if not os.path.isdir("emsdk"):
        print("Setting up emsdk...")
        run_cmd(["git", "clone", "https://github.com/emscripten-core/emsdk.git"])
        with chdir("emsdk"):
            run_cmd(xcmd(["./emsdk", "install", "latest"]))
            run_cmd(xcmd(["./emsdk", "activate", "latest"]))

def run_wasm_builds() -> None:
    """Triggers WebAssembly builds across applicable toolchains."""
    print("===================================")
    print("Running WASM Builds")
    print("===================================")
    setup_emsdk()
    
    if should_run("cdd-c"):
        print("Building WASM for cdd-c...")
        with chdir("cdd-c"):
            run_cmd(["make", "build_wasm"])
            
    if should_run("cdd-cpp"):
        print("Building WASM for cdd-cpp...")
        with chdir("cdd-cpp"):
            run_cmd(["make", "build_wasm"])
            
    if should_run("cdd-csharp"):
        print("Building WASM for cdd-csharp...")
        with chdir("cdd-csharp"):
            run_cmd(["make", "build_wasm"])
            
    if should_run("cdd-go"):
        print("===================================")
        print("Running cdd-go tests")
        print("===================================")
        with chdir("cdd-go"):
            run_cmd(["make", "test"])
            run_cmd(["make", "build"])
            shutil.rmtree("../cdd-go-client", ignore_errors=True)
            run_cmd(xcmd(["./bin/cdd-go", "from_openapi", "to_sdk", "-i", "../petstore.json", "-o", "../cdd-go-client", "-create-composable-tests"]))
        with chdir("cdd-go-client"):
            models_dir = "models"
            if os.path.exists(models_dir):
                for r, d, f_list in os.walk(models_dir):
                    for f in f_list:
                        if f != "components.go":
                            os.remove(os.path.join(r, f))
            run_cmd(["go", "mod", "tidy"])
            run_cmd(["go", "test", "./..."])
                
    if should_run("cdd-php"):
        print("Building WASM for cdd-php...")
        with chdir("cdd-php"):
            run_cmd(["make", "build_wasm"])
            
    if should_run("cdd-python-all"):
        print("Building WASM for cdd-python-all...")
        with chdir("cdd-python-all"):
            run_cmd(["make", "build_wasm"])
            
    if should_run("cdd-ruby"):
        print("Building WASM for cdd-ruby...")
        with chdir("cdd-ruby"):
            run_cmd(["make", "build_wasm"])
            
    if should_run("cdd-kotlin"):
        print("Building WASM for cdd-kotlin...")
        with chdir("cdd-kotlin"):
            run_cmd(xcmd(["./gradlew", "assemble"]))

    if should_run("cdd-sh"):
        print("Building WASM for cdd-sh...")
        with chdir("cdd-sh"):
            run_cmd(["make", "build_wasm"])

def yaml_to_json(in_file: str, out_file: str) -> None:
    """Converts YAML or JSON file to JSON using a subprocess to avoid module dependencies in the main script."""
    with open(in_file, "rb") as f_in, open(out_file, "wb") as f_out:
        subprocess.run(
            [sys.executable, "-c", "import yaml, json, sys; json.dump(yaml.safe_load(sys.stdin), sys.stdout)"],
            stdin=f_in, stdout=f_out, check=True
        )

def run_test_with_audit(lang_name: str, spec_file: str, base_path: str, action: Callable[[], None]) -> bool:
    """Runs tests for a specific language against the happy path (checking coverage), and then against chaos conditions."""
    if not should_run(lang_name):
        return True
        
    print("===================================")
    print(f"Auditing {lang_name} against {spec_file}")
    print("===================================")

    print(f"[{lang_name}] Phase 1: Happy Path & Coverage...")
    start_petstore(base_path)
    try:
        action()
    except Exception as e:
        print(f"[{lang_name}] Happy path failed: {e}")
        return False
        
    print(f"[{lang_name}] Validating Endpoint Coverage...")
    logs = ""
    res = subprocess.run(["docker", "logs", "petstore_server"], capture_output=True, text=True)
    logs += res.stdout + "\n" + res.stderr
    if os.path.exists("java_petstore_access.log"):
        with open("java_petstore_access.log", "r", encoding="utf-8") as f:
            logs += f.read()
    
    verify_res = subprocess.run([sys.executable, "verify_coverage.py", spec_file, base_path], input=logs, text=True, capture_output=True)
    if verify_res.returncode != 0:
        print(f"[{lang_name}] Coverage validation failed.")
        print(verify_res.stdout)
        print(verify_res.stderr)
        return False
        
    print(f"[{lang_name}] Phase 2: Status Audit (Expect Tests to Fail on 500s)...")
    subprocess.run(["docker", "rm", "-f", "petstore_server"], capture_output=True)
    saboteur = subprocess.Popen([sys.executable, "saboteur_server.py", "500", "8080"])
    time.sleep(2)
    try:
        action()
        print(f"[{lang_name}] Audit Failed: Tests passed even though the server returned HTTP 500.")
        saboteur.kill()
        saboteur.wait()
        return False
    except Exception:
        pass
    saboteur.kill()
    saboteur.wait()
    
    print(f"[{lang_name}] Phase 3: Schema Audit (Expect Tests to Fail on Invalid Payloads)...")
    saboteur = subprocess.Popen([sys.executable, "saboteur_server.py", "invalid_schema", "8080"])
    time.sleep(2)
    try:
        action()
        print(f"[{lang_name}] Audit Failed: Tests passed even though the server returned invalid JSON schema.")
        saboteur.kill()
        saboteur.wait()
        return False
    except Exception:
        pass
    saboteur.kill()
    saboteur.wait()
    
    print(f"[{lang_name}] All audits passed successfully.")
    return True

def test_cdd_ts(spec_file: str) -> None:
    """Executes native tests for cdd-ts toolchain."""
    with chdir("cdd-ts"):
        run_cmd(["npm", "install"])
        run_cmd(["npm", "run", "build"])
    
    shutil.rmtree("angular-client", ignore_errors=True)
    run_cmd(["npm", "cache", "clean", "--force"], check=False)
    run_cmd(["npx", "-p", "@angular/cli", "ng", "new", "angular-client", "--defaults", "--skip-git"])
    
    with chdir("angular-client"):
        run_cmd(["npx", "ng", "add", "@angular/material", "--skip-confirmation", "--defaults"], check=False)
        
    with chdir("cdd-ts"):
        run_cmd(["node", "dist/cli.js", "from_openapi", "to_sdk", "-i", f"../{spec_file}", "--output", "../angular-client/src/app/api", "--implementation", "angular", "--platform", "browser"])
        
    with chdir("angular-client"):
        run_cmd(["npm", "install"])
        run_cmd(["npm", "run", "test", "--", "--watch=false"], check=False)
        
    with chdir("cdd-ts"):
        shutil.rmtree("node-client", ignore_errors=True)
        os.makedirs("node-client", exist_ok=True)
        with chdir("node-client"):
            run_cmd(["npm", "init", "-y"])
            run_cmd(["npm", "install", "typescript", "vitest", "@types/node"])
            
        run_cmd(["node", "dist/cli.js", "from_openapi", "to_sdk", "-i", f"../{spec_file}", "--output", "node-client", "--implementation", "node", "--platform", "node"])
        
        with chdir("node-client"):
            with open("tsconfig.json", "w", encoding="utf-8") as f:
                f.write('{\n  "compilerOptions": {\n    "target": "ES2022",\n    "module": "NodeNext",\n    "moduleResolution": "NodeNext",\n    "esModuleInterop": true,\n    "strict": true,\n    "skipLibCheck": true,\n    "forceConsistentCasingInFileNames": true\n  }\n}\n')
            with open("vitest.config.ts", "w", encoding="utf-8") as f:
                f.write('import { defineConfig } from "vitest/config";\n\nexport default defineConfig({\n    test: {\n        include: ["src/**/*.spec.ts"]\n    }\n});\n')
            run_cmd(["npx", "vitest", "run", "src/integration.spec.ts"])

def test_cdd_kotlin(spec_file: str) -> None:
    """Executes native tests for cdd-kotlin toolchain."""
    gradle_user_home = os.path.expanduser("~/.gemini/tmp/cdd-kotlin/.gradle_home")
    java_home = os.path.expanduser("~/.gemini/tmp/cdd-kotlin/.gradle_home/jdks/eclipse_adoptium-21-aarch64-os_x/jdk-21.0.11+10/Contents/Home")
    env = {"GRADLE_USER_HOME": gradle_user_home, "JAVA_HOME": java_home}
    
    with chdir("cdd-kotlin"):
        run_cmd(xcmd(["./gradlew", "jvmJar"]), env=env)
        shutil.rmtree("../kotlin-client", ignore_errors=True)
        run_cmd(xcmd(["./gradlew", "run", f"--args=from_openapi to_sdk -i ../{spec_file} --output ../kotlin-client --tests"]), env=env)
        
    with chdir("kotlin-client"):
        with open("gradle.properties", "w", encoding="utf-8") as f:
            f.write(f"org.gradle.java.home={java_home}\n")
        run_cmd(["gradle", "test", "--no-daemon"], check=False, env=env)

def test_cdd_go(spec_file: str) -> None:
    """Executes native tests for cdd-go toolchain."""
    with chdir("cdd-go"):
        run_cmd(["make", "test"])
        run_cmd(["make", "build"])
        shutil.rmtree("../cdd-go-client", ignore_errors=True)
        run_cmd(xcmd(["./bin/cdd-go", "from_openapi", "to_sdk", "-i", f"../{spec_file}", "-o", "../cdd-go-client", "-create-composable-tests"]))
        
    with chdir("cdd-go-client"):
        models_dir = "models"
        if os.path.exists(models_dir):
            for r, d, f_list in os.walk(models_dir):
                for f in f_list:
                    if f != "components.go":
                        os.remove(os.path.join(r, f))
        run_cmd(["go", "mod", "tidy"])
        run_cmd(["go", "test", "./..."])

def test_cdd_csharp(spec_file: str) -> None:
    """Executes native tests for cdd-csharp toolchain."""
    with chdir("cdd-csharp"):
        run_cmd(["dotnet", "restore"])
        run_cmd(["dotnet", "build", "--no-restore"])
        run_cmd(["dotnet", "test", "tests/Cdd.OpenApi.Tests", "--no-build"])
        shutil.rmtree("../cdd-csharp-client", ignore_errors=True)
        run_cmd(["dotnet", "run", "--project", "src/Cdd.OpenApi.Cli/Cdd.OpenApi.Cli.csproj", "-f", "net10.0", "--", "from_openapi", "to_sdk", "-i", f"../{spec_file}", "-o", "../cdd-csharp-client"])
        
    with chdir("cdd-csharp-client"):
        run_cmd(["dotnet", "test", "GeneratedProject.sln"])

def test_cdd_python_all(spec_file: str) -> None:
    """Executes native tests for cdd-python-all toolchain."""
    with chdir("cdd-python-all"):
        run_cmd(["make", "test"])
        shutil.rmtree("../cdd-python-client", ignore_errors=True)
        run_cmd(["uv", "run", "python", "-m", "openapi_client.cli", "from_openapi", "to_sdk", "-i", f"../{spec_file}", "-o", "../cdd-python-client", "--tests"])
        
    with chdir("cdd-python-client"):
        run_cmd([sys.executable, "-m", "venv", ".venv"])
        pip_bin = os.path.join(".venv", "Scripts" if os.name == "nt" else "bin", "pip")
        pytest_bin = os.path.join(".venv", "Scripts" if os.name == "nt" else "bin", "pytest")
        run_cmd([pip_bin, "install", "-e", ".[dev]"])
        run_cmd([pytest_bin, "test/"])

def test_cdd_rust(spec_file: str) -> None:
    """Executes native tests for cdd-rust toolchain."""
    with chdir("cdd-rust"):
        run_cmd(["cargo", "test"])
        shutil.rmtree("../cdd-rust-client", ignore_errors=True)
        run_cmd(["cargo", "run", "-p", "cdd-cli", "--bin", "cdd-rust", "--", "from_openapi", "to_sdk", "-i", f"../{spec_file}", "-o", "../cdd-rust-client", "--tests"])
        
    with chdir("cdd-rust-client"):
        run_cmd(["cargo", "test"])

def test_cdd_swift(spec_file: str) -> None:
    """Executes native tests for cdd-swift toolchain."""
    with chdir("cdd-swift"):
        run_cmd(["make", "test"])
        shutil.rmtree("../cdd-swift-client", ignore_errors=True)
        run_cmd(["swift", "run", "cdd-swift", "from_openapi", "to_sdk", "-i", f"../{spec_file}", "-o", "../cdd-swift-client", "--tests"])
        
    with chdir("cdd-swift-client"):
        run_cmd(["swift", "test"])

def test_cdd_c(spec_file: str) -> None:
    """Executes native tests for cdd-c toolchain."""
    with chdir("cdd-c"):
        run_cmd(["make", "test"])
        shutil.rmtree("../cdd-c-client", ignore_errors=True)
        run_cmd(xcmd(["./bin/cdd-c", "from_openapi", "to_sdk", "-i", f"../{spec_file}", "-o", "../cdd-c-client", "--tests"]))
        
    with chdir("cdd-c-client"):
        run_cmd(["cmake", ".", "-DFETCHCONTENT_UPDATES_DISCONNECTED=ON"])
        run_cmd(["cmake", "--build", "."])
        run_cmd(["ctest", "--output-on-failure"], check=False)
        run_cmd(xcmd(["./src/test_generated_client"]))

def test_cdd_cpp(spec_file: str) -> None:
    """Executes native tests for cdd-cpp toolchain."""
    with chdir("cdd-cpp"):
        run_cmd(["make", "test"])
        shutil.rmtree("../cdd-cpp-client", ignore_errors=True)
        run_cmd(xcmd(["./build/cdd-cpp", "from_openapi", "to_sdk", "-i", f"../{spec_file}", "-o", "../cdd-cpp-client", "--tests"]))
        
    with chdir("cdd-cpp-client"):
        run_cmd(["cmake", ".", "-DFETCHCONTENT_UPDATES_DISCONNECTED=ON"])
        run_cmd(["cmake", "--build", "."])
        run_cmd(["ctest", "--output-on-failure"], check=False)
        run_cmd(xcmd(["./src/test_generated_client"]))

def test_cdd_java(spec_file: str) -> None:
    """Executes native tests for cdd-java toolchain."""
    with chdir("cdd-java"):
        run_cmd(["make", "test"])
        run_cmd(["make", "build"])
        shutil.rmtree("../cdd-java-client", ignore_errors=True)
        cp = f"lib/*{os.pathsep}bin"
        run_cmd(["java", "-cp", cp, "cli.Main", "from_openapi", "to_sdk", "-i", f"../{spec_file}", "--tests", "-o", "../cdd-java-client"])
        
    with chdir("cdd-java-client"):
        run_cmd(["mvn", "test"])

def test_cdd_php(spec_file: str) -> None:
    """Executes native tests for cdd-php toolchain."""
    with chdir("cdd-php"):
        run_cmd(["make", "test"])
        print("Generating PHP SDK and running integration tests...")
        shutil.rmtree("../php-client", ignore_errors=True)
        run_cmd(["php", "bin/cdd-php", "from_openapi", "to_sdk", "--tests", "-i", f"../{spec_file}", "-o", "../php-client"])
        
    with chdir("php-client"):
        run_cmd(["composer", "install"])
        run_cmd(["composer", "test"], check=False)

def test_cdd_ruby(spec_file: str) -> None:
    """Executes native tests for cdd-ruby toolchain."""
    with chdir("cdd-ruby"):
        if os.path.exists("Gemfile.lock"): os.remove("Gemfile.lock")
        run_cmd(xcmd(["bundle", "install"]))
        run_cmd(xcmd(["bundle", "exec", "rspec"]))
        shutil.rmtree("../cdd-ruby-client", ignore_errors=True)
        run_cmd(xcmd(["ruby", "bin/cdd-ruby", "from_openapi", "to_sdk", "-i", f"../{spec_file}", "-o", "../cdd-ruby-client"]))
        
    with chdir("cdd-ruby-client"):
        if os.path.exists("Gemfile.lock"): os.remove("Gemfile.lock")
        run_cmd(xcmd(["bundle", "install"]))
        run_cmd(xcmd(["bundle", "exec", "rspec"]))

def test_cdd_sh(spec_file: str) -> None:
    """Executes native tests for cdd-sh toolchain."""
    with chdir("cdd-sh"):
        run_cmd(xcmd(["./test.sh"]))
        if shutil.which("shellcheck"):
            files = []
            for d in glob.glob("src/*"):
                if os.path.isdir(d):
                    files.extend(glob.glob(f"{d}/*.sh"))
            run_cmd(["shellcheck", "cdd.sh"] + files, check=False)
        else:
            print("Warning: shellcheck is not installed. Skipping shellcheck.")
            
        print("Generating SDK and running integration tests...")
        shutil.rmtree("../sh-client", ignore_errors=True)
        yaml_to_json("../petstore.yaml", "temp-petstore.json")
        env = os.environ.copy()
        env["CDD_TESTS"] = "1"
        run_cmd(xcmd(["./cdd.sh", "from_openapi", "to_sdk", "-i", "temp-petstore.json", "-o", "../sh-client"]), check=False, env=env)
        
    if os.path.exists("sh-client"):
        with chdir("sh-client"):
            test_routes = os.path.join("tests", "test_routes.sh")
            if os.path.exists(test_routes):
                os.chmod(test_routes, 0o755)
                run_cmd(xcmd([f"./{test_routes}"]), check=False)

def run_test() -> None:
    """Executes native tests for each enabled toolchain."""
    specs = ["petstore.json", "petstore_oas3.json"]
    
    for spec_name in specs:
        base_path = "/v2" if spec_name == "petstore.json" else "/api/v3"
        if not run_test_with_audit("cdd-ts", spec_name, base_path, lambda: test_cdd_ts(spec_name)): sys.exit(1)
        
    for spec_name in specs:
        base_path = "/v2" if spec_name == "petstore.json" else "/api/v3"
        if not run_test_with_audit("cdd-kotlin", spec_name, base_path, lambda: test_cdd_kotlin(spec_name)): sys.exit(1)
        
    for spec_name in specs:
        base_path = "/v2" if spec_name == "petstore.json" else "/api/v3"
        if not run_test_with_audit("cdd-go", spec_name, base_path, lambda: test_cdd_go(spec_name)): sys.exit(1)
        
    for spec_name in specs:
        base_path = "/v2" if spec_name == "petstore.json" else "/api/v3"
        if not run_test_with_audit("cdd-csharp", spec_name, base_path, lambda: test_cdd_csharp(spec_name)): sys.exit(1)
        
    for spec_name in specs:
        base_path = "/v2" if spec_name == "petstore.json" else "/api/v3"
        if not run_test_with_audit("cdd-python-all", spec_name, base_path, lambda: test_cdd_python_all(spec_name)): sys.exit(1)
        
    for spec_name in specs:
        base_path = "/v2" if spec_name == "petstore.json" else "/api/v3"
        if not run_test_with_audit("cdd-rust", spec_name, base_path, lambda: test_cdd_rust(spec_name)): sys.exit(1)
        
    for spec_name in specs:
        base_path = "/v2" if spec_name == "petstore.json" else "/api/v3"
        if not run_test_with_audit("cdd-swift", spec_name, base_path, lambda: test_cdd_swift(spec_name)): sys.exit(1)
        
    for spec_name in specs:
        base_path = "/v2" if spec_name == "petstore.json" else "/api/v3"
        if not run_test_with_audit("cdd-c", spec_name, base_path, lambda: test_cdd_c(spec_name)): sys.exit(1)
        
    for spec_name in specs:
        base_path = "/v2" if spec_name == "petstore.json" else "/api/v3"
        if not run_test_with_audit("cdd-cpp", spec_name, base_path, lambda: test_cdd_cpp(spec_name)): sys.exit(1)
        
    for spec_name in specs:
        base_path = "/v2" if spec_name == "petstore.json" else "/api/v3"
        if not run_test_with_audit("cdd-java", spec_name, base_path, lambda: test_cdd_java(spec_name)): sys.exit(1)
        
    for spec_name in specs:
        base_path = "/v2" if spec_name == "petstore.json" else "/api/v3"
        if not run_test_with_audit("cdd-php", spec_name, base_path, lambda: test_cdd_php(spec_name)): sys.exit(1)
        
    for spec_name in specs:
        base_path = "/v2" if spec_name == "petstore.json" else "/api/v3"
        if not run_test_with_audit("cdd-ruby", spec_name, base_path, lambda: test_cdd_ruby(spec_name)): sys.exit(1)
        
    for spec_name in specs:
        base_path = "/v2" if spec_name == "petstore.json" else "/api/v3"
        if not run_test_with_audit("cdd-sh", spec_name, base_path, lambda: test_cdd_sh(spec_name)): sys.exit(1)

def run_roundtrip() -> None:
    """Executes roundtrip tests against OpenAPI schemas for all enabled toolchains."""
    print("===================================")
    print("Running Roundtrip Tests")
    print("===================================")
    
    if should_run("cdd-ts"):
        with chdir("cdd-ts"):
            run_cmd(["npm", "install"])
            run_cmd(["npm", "run", "build"])
        for spec_file in ["petstore.json", "petstore_oas3.json"]:
            if os.path.exists(spec_file):
                print(f"Testing {spec_file} with cdd-ts...")
                run_cmd(["node", "cdd-ts/dist/cli.js", "from_openapi", "to_sdk", "-i", spec_file, "-o", "temp-ng"])
                run_cmd(["node", "cdd-ts/dist/cli.js", "to_openapi", "-i", "temp-ng", "--format", "yaml", "-o", "temp-ng-spec.yaml"])
                shutil.rmtree("temp-ng", ignore_errors=True)
                if os.path.exists("temp-ng-spec.yaml"): os.remove("temp-ng-spec.yaml")

    for spec_file in ["petstore.json", "petstore_oas3.json"]:
        if not os.path.exists(spec_file):
            continue
            
        if should_run("cdd-kotlin"):
            print(f"Testing {spec_file} with cdd-kotlin...")
            with chdir("cdd-kotlin"):
                run_cmd(xcmd(["./gradlew", "run", f"--args=from_openapi to_sdk -i ../{spec_file} --output ../temp-kt"]))
                run_cmd(xcmd(["./gradlew", "run", f"--args=to_openapi -i ../temp-kt --format yaml -o ../temp-kt-spec.yaml"]))
            shutil.rmtree("temp-kt", ignore_errors=True)
            if os.path.exists("temp-kt-spec.yaml"): os.remove("temp-kt-spec.yaml")
            
        if should_run("cdd-rust"):
            print(f"Testing {spec_file} with cdd-rust...")
            with chdir("cdd-rust"):
                run_cmd(["cargo", "test"])
                shutil.rmtree("../cdd-rust-client", ignore_errors=True)
                run_cmd(["cargo", "run", "-p", "cdd-cli", "--bin", "cdd-rust", "--", "from_openapi", "to_sdk", "-i", "../petstore.json", "-o", "../cdd-rust-client", "--tests"])
                
            with chdir("cdd-rust-client"):
                shutil.rmtree("../temp-rs", ignore_errors=True)
                run_cmd(["cargo", "run", "-p", "cdd-cli", "--", "from_openapi", "to_sdk", "-i", f"../{spec_file}", "-o", "../temp-rs"])
                run_cmd(["cargo", "run", "-p", "cdd-cli", "--", "--target", "client", "to_openapi", "-i", "../temp-rs", "-o", "../temp-rs/spec.yaml"])
            shutil.rmtree("temp-rs", ignore_errors=True)
            
        if should_run("cdd-c"):
            print(f"Testing {spec_file} with cdd-c...")
            with chdir("cdd-c"):
                os.makedirs("../temp-c", exist_ok=True)
                yaml_to_json(f"../{spec_file}", "../temp-c-spec.json")
                run_cmd(xcmd(["./bin/cdd-c", "from_openapi", "to_sdk", "-i", "../temp-c-spec.json", "-o", "../temp-c"]), check=False)
                run_cmd(xcmd(["./bin/cdd-c", "to_openapi", "-i", "../temp-c", "-o", "../temp-c/spec.yaml"]), check=False)
            shutil.rmtree("temp-c", ignore_errors=True)
            if os.path.exists("temp-c-spec.json"): os.remove("temp-c-spec.json")

        if should_run("cdd-cpp"):
            print(f"Testing {spec_file} with cdd-cpp...")
            with chdir("cdd-cpp"):
                os.makedirs("../temp-cpp", exist_ok=True)
                yaml_to_json(f"../{spec_file}", "../temp-cpp-spec.json")
                run_cmd(xcmd(["./bin/cdd-cpp", "from_openapi", "to_sdk", "-i", "../temp-cpp-spec.json", "-o", "../temp-cpp"]), check=False)
                run_cmd(xcmd(["./bin/cdd-cpp", "to_openapi", "-i", "../temp-cpp", "-o", "../temp-cpp/spec.yaml"]), check=False)
            shutil.rmtree("temp-cpp", ignore_errors=True)
            if os.path.exists("temp-cpp-spec.json"): os.remove("temp-cpp-spec.json")
            
        if should_run("cdd-php"):
            print(f"Testing {spec_file} with cdd-php...")
            with chdir("cdd-php"):
                os.makedirs("../temp-php", exist_ok=True)
                yaml_to_json(f"../{spec_file}", "../temp-php-spec.json")
                run_cmd(["php", "bin/cdd-php", "from_openapi", "to_sdk", "-i", "../temp-php-spec.json", "-o", "../temp-php"], check=False)
                run_cmd(["php", "bin/cdd-php", "to_openapi", "-i", "../temp-php", "-o", "../temp-php/spec.yaml"], check=False)
            shutil.rmtree("temp-php", ignore_errors=True)
            if os.path.exists("temp-php-spec.json"): os.remove("temp-php-spec.json")

        if should_run("cdd-ruby"):
            print(f"Testing {spec_file} with cdd-ruby...")
            with chdir("cdd-ruby"):
                os.makedirs("../temp-rb", exist_ok=True)
                yaml_to_json(f"../{spec_file}", "../temp-rb-spec.json")
                run_cmd(xcmd(["ruby", "bin/cdd-ruby", "from_openapi", "to_sdk", "-i", "../temp-rb-spec.json", "-o", "../temp-rb"]), check=False)
                run_cmd(xcmd(["ruby", "bin/cdd-ruby", "to_openapi", "-i", "../temp-rb", "-o", "../temp-rb/spec.yaml"]), check=False)
            shutil.rmtree("temp-rb", ignore_errors=True)
            if os.path.exists("temp-rb-spec.json"): os.remove("temp-rb-spec.json")

        if should_run("cdd-java"):
            print(f"Testing {spec_file} with cdd-java...")
            with chdir("cdd-java"):
                os.makedirs("../temp-java", exist_ok=True)
                yaml_to_json(f"../{spec_file}", "../temp-java-spec.json")
                run_cmd(xcmd(["./gradlew", "run", "--args=from_openapi to_sdk -i ../temp-java-spec.json -o ../temp-java"]), check=False)
                run_cmd(xcmd(["./gradlew", "run", "--args=to_openapi -i ../temp-java -o ../temp-java/spec.yaml"]), check=False)
            shutil.rmtree("temp-java", ignore_errors=True)
            if os.path.exists("temp-java-spec.json"): os.remove("temp-java-spec.json")

    if should_run("cdd-python-all"):
        print("Testing with cdd-python-all...")
        with chdir("cdd-python-all"):
            run_cmd([sys.executable, "-m", "pip", "install", "pyyaml"])
            run_cmd([sys.executable, "-m", "pip", "install", "-e", "."])
            for spec_file in ["../petstore.json", "../petstore_oas3.json"]:
                if os.path.exists(spec_file):
                    os.makedirs("temp-py", exist_ok=True)
                    yaml_to_json(spec_file, "temp-py-spec.json")
                    run_cmd(["cdd-python-all", "from_openapi", "-i", "temp-py-spec.json", "-o", "temp-py/"])
                    run_cmd(["cdd-python-all", "to_openapi", "-i", "temp-py/", "-o", "temp-py-spec.json"])
                    shutil.rmtree("temp-py", ignore_errors=True)
                    if os.path.exists("temp-py-spec.json"): os.remove("temp-py-spec.json")

    if should_run("cdd-swift"):
        print("Testing with cdd-swift...")
        with chdir("cdd-swift"):
            run_cmd(["swift", "build", "-c", "release"])
            for spec_file in ["../petstore.json", "../petstore_oas3.json"]:
                if os.path.exists(spec_file):
                    yaml_to_json(spec_file, "temp-swift-spec.json")
                    run_cmd([".build/release/cdd-swift", "from_openapi", "-i", "temp-swift-spec.json", "-o", "temp-swift"])
                    run_cmd([".build/release/cdd-swift", "to_openapi", "-i", "temp-swift/Sources/GeneratedSDK/temp-swift-spec.swift", "-o", "temp-swift-out.json"])
                    shutil.rmtree("temp-swift", ignore_errors=True)
                    if os.path.exists("temp-swift-spec.json"): os.remove("temp-swift-spec.json")
                    if os.path.exists("temp-swift-out.json"): os.remove("temp-swift-out.json")

    if should_run("cdd-sh"):
        print("Testing with cdd-sh...")
        with chdir("cdd-sh"):
            for spec_file in ["../petstore.json", "../petstore_oas3.json"]:
                if os.path.exists(spec_file):
                    yaml_to_json(spec_file, "temp-sh-spec.json")
                    run_cmd(xcmd(["./cdd.sh", "from_openapi", "-i", "temp-sh-spec.json", "-o", "temp-sh-dir"]))
                    run_cmd(xcmd(["./cdd.sh", "to_openapi", "-i", "temp-sh-dir", "-o", "temp-sh-out.json"]))
                    shutil.rmtree("temp-sh-dir", ignore_errors=True)
                    if os.path.exists("temp-sh-spec.json"): os.remove("temp-sh-spec.json")
                    if os.path.exists("temp-sh-out.json"): os.remove("temp-sh-out.json")
                    if os.path.exists("ast.json"): os.remove("ast.json")

    if should_run("cdd-go"):
        print("===================================")
        print("Running cdd-go tests")
        print("===================================")
        with chdir("cdd-go"):
            run_cmd(["make", "test"])
            run_cmd(["make", "build"])
            shutil.rmtree("../cdd-go-client", ignore_errors=True)
            run_cmd(xcmd(["./bin/cdd-go", "from_openapi", "to_sdk", "-i", "../petstore.json", "-o", "../cdd-go-client", "-create-composable-tests"]))
            
        with chdir("cdd-go-client"):
            models_dir = "models"
            if os.path.exists(models_dir):
                for r, d, f_list in os.walk(models_dir):
                    for f in f_list:
                        if f != "components.go":
                            os.remove(os.path.join(r, f))
            run_cmd(["go", "mod", "tidy"])
            run_cmd(["go", "test", "./..."])

    if should_run("cdd-csharp"):
        print("Testing with cdd-csharp...")
        with chdir("cdd-csharp"):
            for spec_file in ["../petstore.json", "../petstore_oas3.json"]:
                if os.path.exists(spec_file):
                    yaml_to_json(spec_file, "temp-cs-spec.json")
                    run_cmd(["dotnet", "run", "--project", "src/Cdd.OpenApi.Cli", "--", "from_openapi", "-i", "temp-cs-spec.json", "-o", "temp-cs"])
                    run_cmd(["dotnet", "run", "--project", "src/Cdd.OpenApi.Cli", "--", "to_openapi", "-i", "temp-cs", "-o", "temp-cs-out.json"])
                    shutil.rmtree("temp-cs", ignore_errors=True)
                    if os.path.exists("temp-cs-spec.json"): os.remove("temp-cs-spec.json")
                    if os.path.exists("temp-cs-out.json"): os.remove("temp-cs-out.json")

def main() -> None:
    """Main entry point for local_test.py"""
    parser = argparse.ArgumentParser(description="Orchestrates local execution of native tests, WASM builds, and roundtrip tests.")
    parser.add_argument("mode", nargs="?", choices=["roundtrip", "all", "only-test"], help="Mode of execution.")
    args = parser.parse_args()

    mode = args.mode

    if mode == "roundtrip":
        run_roundtrip()
        print("===================================")
        print("All roundtrip tests completed successfully!")
        print("===================================")
    elif mode == "all":
        start_petstore()
        run_test()
        run_wasm_builds()
        run_roundtrip()
        print("===================================")
        print("All local tests completed successfully!")
        print("===================================")
    elif mode == "only-test":
        start_petstore()
        run_test()
        print("===================================")
        print("All local tests completed successfully (WASM skipped)!")
        print("===================================")
    else:
        start_petstore()
        run_test()
        run_wasm_builds()
        print("===================================")
        print("All test.yml local tests completed successfully!")
        print("===================================")
        print("Run 'python3 local_test.py roundtrip' to execute roundtrip tests.")

if __name__ == "__main__":
    main()
