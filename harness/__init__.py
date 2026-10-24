"""CDD OpenAPI Test Harness package.

Provides unified error handling, toolchain specifications, orchestration,
conformance detection, endpoint coverage verification, and reporting utilities.
"""

from harness.errors import (
    AuditFailureError,
    CommandExecutionError,
    ConformanceError,
    CoverageValidationError,
    DashboardError,
    DirectoryMissingError,
    HarnessError,
    SpecificationError,
)
from harness.registry import TOOLCHAINS, ToolchainSpec, get_toolchain, get_toolchains

__all__ = [
    "AuditFailureError",
    "CommandExecutionError",
    "ConformanceError",
    "CoverageValidationError",
    "DashboardError",
    "DirectoryMissingError",
    "HarnessError",
    "SpecificationError",
    "TOOLCHAINS",
    "ToolchainSpec",
    "get_toolchain",
    "get_toolchains",
]
