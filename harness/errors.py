"""Unified error hierarchy for the CDD OpenAPI test harness.

Defines a single structured exception hierarchy replacing ad-hoc `sys.exit`
and bare `Exception` handlers across the codebase.
"""

from typing import List, Optional


class HarnessError(Exception):
    """Base exception for all errors raised by the CDD OpenAPI test harness.

    Attributes:
        message: Human-readable description of the error.
        code: Numeric exit code associated with the error.
    """

    def __init__(self, message: str, code: int = 1) -> None:
        """Initialize a HarnessError.

        Args:
            message: Human-readable description of the error.
            code: Process exit code associated with the error. Defaults to 1.
        """
        super().__init__(message)
        self.message: str = message
        self.code: int = code


class CommandExecutionError(HarnessError):
    """Raised when an external subprocess command fails.

    Attributes:
        cmd: The command argument list that failed.
        returncode: Exit code returned by the subprocess.
        stdout: Captured standard output, if any.
        stderr: Captured standard error, if any.
    """

    def __init__(
        self,
        cmd: List[str],
        returncode: int,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None,
    ) -> None:
        """Initialize a CommandExecutionError.

        Args:
            cmd: The command list that was executed.
            returncode: The non-zero exit code returned by the command.
            stdout: Optional captured standard output from the command.
            stderr: Optional captured standard error from the command.
        """
        message = f"Command '{' '.join(cmd)}' failed with exit code {returncode}"
        super().__init__(message, code=returncode if returncode != 0 else 1)
        self.cmd: List[str] = list(cmd)
        self.returncode: int = returncode
        self.stdout: Optional[str] = stdout
        self.stderr: Optional[str] = stderr


class DirectoryMissingError(HarnessError):
    """Raised when a required project or toolchain directory does not exist.

    Attributes:
        path: The missing filesystem path.
    """

    def __init__(self, path: str) -> None:
        """Initialize a DirectoryMissingError.

        Args:
            path: The directory path that could not be found.
        """
        super().__init__(f"Error: Directory '{path}' not found.", code=1)
        self.path: str = path


class SpecificationError(HarnessError):
    """Raised when an OpenAPI or Swagger specification cannot be parsed or validated.

    Attributes:
        spec_path: Path to the specification file that caused the error.
    """

    def __init__(self, spec_path: str, reason: str) -> None:
        """Initialize a SpecificationError.

        Args:
            spec_path: File path to the specification.
            reason: Explanation of why the specification failed to load or validate.
        """
        super().__init__(f"Error reading specification {spec_path}: {reason}", code=1)
        self.spec_path: str = spec_path
        self.reason: str = reason


class CoverageValidationError(HarnessError):
    """Raised when endpoint coverage validation fails for a test run.

    Attributes:
        unhit_endpoints: List of formatted `METHOD /path` strings not exercised.
    """

    def __init__(self, unhit_endpoints: List[str]) -> None:
        """Initialize a CoverageValidationError.

        Args:
            unhit_endpoints: List of endpoints that were not hit during testing.
        """
        joined = ", ".join(unhit_endpoints)
        super().__init__(f"Coverage validation failed for endpoints: {joined}", code=1)
        self.unhit_endpoints: List[str] = list(unhit_endpoints)


class AuditFailureError(HarnessError):
    """Raised when a toolchain fails a happy-path, status, or schema audit phase.

    Attributes:
        toolchain: Name of the toolchain under audit.
        phase: Name of the audit phase ('happy_path', 'coverage', 'status_500', 'invalid_schema').
    """

    def __init__(self, toolchain: str, phase: str, details: str) -> None:
        """Initialize an AuditFailureError.

        Args:
            toolchain: Name of the toolchain being audited.
            phase: Audit phase identifier where the failure occurred.
            details: Detailed message describing the audit failure.
        """
        super().__init__(f"[{toolchain}] Audit failed in phase '{phase}': {details}", code=1)
        self.toolchain: str = toolchain
        self.phase: str = phase
        self.details: str = details


class ConformanceError(HarnessError):
    """Raised when conformance detection or markdown matrix updating fails."""

    def __init__(self, message: str) -> None:
        """Initialize a ConformanceError.

        Args:
            message: Explanation of the conformance failure.
        """
        super().__init__(message, code=1)


class DashboardError(HarnessError):
    """Raised when README or compliance dashboard table generation fails."""

    def __init__(self, message: str) -> None:
        """Initialize a DashboardError.

        Args:
            message: Explanation of the dashboard or README update failure.
        """
        super().__init__(message, code=1)
