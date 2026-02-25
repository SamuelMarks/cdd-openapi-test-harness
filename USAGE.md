# Test OpenAPI Suites Usage

## 1. Initial Setup

Since this suite tests isolated generation engines, you must pull down their respective git submodules:

```sh
git submodule update --init --recursive
```

## 2. Generate and Run Tests Locally

### Pre-requisites

You must start the target backend server locally via Docker for the integration tests to perform real network requests:

```sh
docker run -d --name petstore-server -e SWAGGER_HOST=http://localhost:8080 -e SWAGGER_BASE_PATH=/v2 -p 8080:8080 swaggerapi/petstore
```

*(Note: the Angular tests are currently pointed to the public `https://petstore.swagger.io/v2` API server as a fallback).*

### Running the Angular Generation Tests (`cdd-web-ng`)

First, ensure dependencies are installed:
```sh
cd cdd-web-ng
npm install
npm run build
```

The Angular test suite tests the generated output logic:
```sh
cd ../angular-client
npm install
npm run test -- --include="**/integration.spec.ts" --watch=false
```

### Running the Kotlin Generation Tests (`cdd-kotlin`)

```sh
cd cdd-kotlin
./gradlew run --args="from_openapi -i ../petstore.json --clientName MyKotlinClient"
./gradlew test
```

## 3. Creating a new Target Language

To orchestrate a new codegen repository into this suite:

1. Create a `<language>-client` directory in this repository for generated code tests.
2. Ensure your language repository exposes a CLI executable.
3. Your CLI MUST support the following two arguments (with identical names):
   * `from_openapi` (e.g. `cdd-lang from_openapi -i spec.json`)
   * `to_openapi` 
4. Add the submodule: `git submodule add <remote-url> cdd-<language>`
5. Integrate it into `.github/workflows/test.yml`.