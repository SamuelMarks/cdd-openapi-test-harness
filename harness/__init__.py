"""CDD OpenAPI Test Harness package.

Provides unified error handling, recursive JSON type definitions, toolchain
specifications, orchestration helpers, conformance detection, endpoint coverage
verification, and reporting utilities.
"""

from harness.errors import (
    AuditFailureError,
    CommandExecutionError,
    ConformanceError,
    CoverageValidationError,
    DashboardError,
    DirectoryMissingError,
    HarnessError,
    JSONDict,
    JSONList,
    JSONScalar,
    JSONValue,
    SpecificationError,
)
from harness.registry import (
    TOOLCHAINS,
    ToolchainSpec,
    build_typescript_toolchain,
    get_toolchain,
    get_toolchains,
    run_c_sdk_test_suite,
    run_typescript_toolchain_tests,
)

__all__ = [
    "TOOLCHAINS",
    "AuditFailureError",
    "CommandExecutionError",
    "ConformanceError",
    "CoverageValidationError",
    "DashboardError",
    "DirectoryMissingError",
    "HarnessError",
    "JSONDict",
    "JSONList",
    "JSONScalar",
    "JSONValue",
    "SpecificationError",
    "ToolchainSpec",
    "build_typescript_toolchain",
    "get_toolchain",
    "get_toolchains",
    "run_c_sdk_test_suite",
    "run_typescript_toolchain_tests",
]
