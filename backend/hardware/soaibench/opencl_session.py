"""SoAI - SoAIBench child-owned OpenCL execution session [backend/hardware/soaibench/opencl_session.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, field

from hardware.soaibench.errors import SoAIBenchUnsupported
from hardware.soaibench.opencl_program import (
    create_buffer,
    create_kernel,
    create_program,
    release_buffer,
    release_kernel,
    release_program,
    set_buffer_arg,
)
from hardware.soaibench.opencl_runtime import (
    OpenCLRuntime,
    build_opencl_runtime,
    release_opencl_runtime,
)
from hardware.soaibench.types import SoAIBenchGpuIdentity

__all__ = ("OpenCLExecutionSession", "OpenCLWorkloadResources")


@dataclass(frozen=True, slots=True)
class OpenCLWorkloadResources:
    runtime: OpenCLRuntime
    program: int
    kernel: int
    initialization_kernel: int
    buffer: int
    element_count: int


@dataclass(slots=True)
class OpenCLExecutionSession:
    identity: SoAIBenchGpuIdentity
    runtime: OpenCLRuntime | None = None
    resources: dict[tuple[str, str, str | None, int], OpenCLWorkloadResources] = field(
        default_factory=dict[tuple[str, str, str | None, int], OpenCLWorkloadResources]
    )
    closed: bool = False

    def acquire(
        self,
        *,
        identity: SoAIBenchGpuIdentity,
        source: str,
        kernel_name: str,
        initialization_kernel_name: str | None,
        element_count: int,
        buffer_size_bytes: int,
    ) -> OpenCLWorkloadResources:
        self.validate_identity(identity)
        runtime = self.runtime_for(identity)
        key = (source, kernel_name, initialization_kernel_name, element_count)
        existing = self.resources.get(key)
        if existing is not None:
            return existing
        program = 0
        kernel = 0
        initialization_kernel = 0
        buffer = 0
        try:
            program = create_program(runtime, source)
            kernel = create_kernel(runtime, program, kernel_name)
            if initialization_kernel_name is not None:
                initialization_kernel = create_kernel(runtime, program, initialization_kernel_name)
            buffer = create_buffer(runtime, buffer_size_bytes)
            set_buffer_arg(runtime, kernel, 0, buffer)
            if initialization_kernel:
                set_buffer_arg(runtime, initialization_kernel, 0, buffer)
            created = OpenCLWorkloadResources(
                runtime=runtime,
                program=program,
                kernel=kernel,
                initialization_kernel=initialization_kernel,
                buffer=buffer,
                element_count=element_count,
            )
            self.resources[key] = created
            return created
        except SoAIBenchUnsupported as exception:
            self._release_handles(
                runtime,
                buffer,
                initialization_kernel,
                kernel,
                program,
                exception,
            )
            raise

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        primary_exception = sys.exception()
        cleanup_failure: SoAIBenchUnsupported | None = None
        for resources in reversed(tuple(self.resources.values())):
            cleanup_failure = self._release_handles(
                resources.runtime,
                resources.buffer,
                resources.initialization_kernel,
                resources.kernel,
                resources.program,
                primary_exception,
                cleanup_failure,
            )
        self.resources.clear()
        if self.runtime is not None:
            try:
                release_opencl_runtime(self.runtime)
            except SoAIBenchUnsupported as exception:
                cleanup_failure = self._record_cleanup_failure(
                    exception, primary_exception, cleanup_failure
                )
            self.runtime = None
        if cleanup_failure is not None and primary_exception is None:
            raise cleanup_failure

    def runtime_for(self, identity: SoAIBenchGpuIdentity) -> OpenCLRuntime:
        self.validate_identity(identity)
        if self.closed:
            raise SoAIBenchUnsupported(
                reason="opencl_session_closed",
                message="The SoAIBench OpenCL execution session is closed.",
            )
        if self.runtime is None:
            self.runtime = build_opencl_runtime(self.identity)
        return self.runtime

    def validate_identity(self, identity: SoAIBenchGpuIdentity) -> None:
        if identity != self.identity:
            raise SoAIBenchUnsupported(
                reason="opencl_identity_changed",
                message="The selected GPU identity changed during the benchmark lease.",
            )

    def _release_handles(
        self,
        runtime: OpenCLRuntime,
        buffer: int,
        initialization_kernel: int,
        kernel: int,
        program: int,
        primary_exception: BaseException | None,
        cleanup_failure: SoAIBenchUnsupported | None = None,
    ) -> SoAIBenchUnsupported | None:
        for release, handle in (
            (release_buffer, buffer),
            (release_kernel, initialization_kernel),
            (release_kernel, kernel),
            (release_program, program),
        ):
            if handle:
                cleanup_failure = self._release_handle(
                    release, runtime, handle, primary_exception, cleanup_failure
                )
        return cleanup_failure

    def _release_handle(
        self,
        release: Callable[[OpenCLRuntime, int], None],
        runtime: OpenCLRuntime,
        handle: int,
        primary_exception: BaseException | None,
        cleanup_failure: SoAIBenchUnsupported | None,
    ) -> SoAIBenchUnsupported | None:
        try:
            release(runtime, handle)
        except SoAIBenchUnsupported as exception:
            return self._record_cleanup_failure(exception, primary_exception, cleanup_failure)
        return cleanup_failure

    def _record_cleanup_failure(
        self,
        exception: SoAIBenchUnsupported,
        primary_exception: BaseException | None,
        cleanup_failure: SoAIBenchUnsupported | None,
    ) -> SoAIBenchUnsupported:
        if primary_exception is not None:
            primary_exception.add_note(
                f"OpenCL cleanup failed: {exception.reason}: {exception.message}"
            )
        return cleanup_failure or exception
