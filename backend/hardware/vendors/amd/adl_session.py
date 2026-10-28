"""SoAI - ADL context, owned native buffers and explicit adapter observations [backend/hardware/vendors/amd/adl_session.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from threading import RLock

from core.di.validation import require_dependencies
from core.errors.exceptions import StateError, ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.validation.strict_integer import is_strict_int
from hardware.vendors.amd.adl_abi import (
    AdlAdapterInfo,
    AdlAdapterObservation,
    AdlAllocatorCallback,
    AdlControlObservation,
    AdlFeatureObservation,
    AdlInitialSetting,
    AdlSingleSetting,
    load_adl_library,
)
from hardware.vendors.amd.adl_adapter_inventory import decode_adl_adapters
from hardware.vendors.amd.adl_pmlog_abi import AdlPMLogLease

__all__ = (
    "ADL_LIFETIME_FAILURES",
    "AdlSession",
    "AdlRuntimeDependencies",
    "AdlRuntime",
)

ADL_LIFETIME_FAILURES: tuple[type[Exception], ...] = (
    *HANDLED_RUNTIME_EXCEPTIONS,
    ctypes.ArgumentError,
    MemoryError,
)


class AdlSession:
    def __init__(self, library: ctypes.CDLL) -> None:
        self.library = library
        self.context = ctypes.c_void_p()
        self.allocations: list[ctypes.Array[ctypes.c_char]] = []
        self.allocated_bytes = 0
        self.allocation_failure: str | None = None
        self.allocator = AdlAllocatorCallback(self._allocate)
        self.pmlog_leases: list[AdlPMLogLease] = []
        self.destroy_attempted = False
        self.initialized = False

    def initialize(self) -> None:
        if self.initialized:
            raise StateError("ADL context initialization cannot be repeated.")
        self.initialized = True
        status = self.library.ADL2_Main_Control_Create(
            self.allocator, 1, ctypes.byref(self.context)
        )
        if status != 0 or self.context.value is None or self.allocation_failure is not None:
            raise StateError(
                "ADL native context is unavailable.",
                details={"native_status": status, "allocator_failure": self.allocation_failure},
            )

    def release(self) -> int:
        if self.pmlog_leases:
            raise StateError("ADL sensor resources remain owned; context release is unsafe.")
        if self.context.value is None:
            return 0
        if self.destroy_attempted:
            raise StateError("ADL uncertain native context release cannot be retried.")
        self.destroy_attempted = True
        status = self.library.ADL2_Main_Control_Destroy(self.context)
        if not is_strict_int(status):
            raise ValidationError("ADL native release status violates its integer ABI.")
        if status == 0:
            self.context = ctypes.c_void_p()
            self.allocations.clear()
            self.allocated_bytes = 0
        return status

    def _allocate(self, size: int) -> int | None:
        if size <= 0 or self.allocated_bytes + size > 16 * 1024 * 1024:
            self.allocation_failure = "allocation_bounds"
            return None
        try:
            buffer = ctypes.create_string_buffer(size)
        except (MemoryError, OverflowError):
            self.allocation_failure = "allocation_failed"
            return None
        self.allocations.append(buffer)
        self.allocated_bytes += size
        return ctypes.addressof(buffer)

    def _require_live(self) -> None:
        if (
            self.context.value is None
            or self.allocation_failure is not None
            or self.destroy_attempted
        ):
            raise StateError(
                "ADL native resource lifetime is unavailable.",
                details={"allocator_failure": self.allocation_failure},
            )

    def read_adapters(self) -> tuple[AdlAdapterObservation, ...]:
        self._require_live()
        count = ctypes.c_int32()
        status = self.library.ADL2_Adapter_NumberOfAdapters_Get(self.context, ctypes.byref(count))
        if status != 0 or not 1 <= count.value <= 128:
            raise StateError("ADL adapter count is unavailable or outside supported bounds.")
        adapters = (AdlAdapterInfo * count.value)()
        for adapter in adapters:
            adapter.size = ctypes.sizeof(AdlAdapterInfo)
        status = self.library.ADL2_Adapter_AdapterInfo_Get(
            self.context, adapters, ctypes.sizeof(adapters)
        )
        self._require_live()
        if status != 0:
            raise StateError("ADL adapter information is unavailable.")
        return decode_adl_adapters(adapters)

    def read_controls(self, adapter: AdlAdapterObservation) -> AdlControlObservation:
        self._require_live()
        if adapter.vendor != 1002 or not adapter.exists or adapter not in self.read_adapters():
            raise StateError("ADL selected native adapter identity changed or is unavailable.")
        supported, enabled, version = ctypes.c_int32(), ctypes.c_int32(), ctypes.c_int32()
        status = self.library.ADL2_Overdrive_Caps(
            self.context,
            adapter.adapter_index,
            ctypes.byref(supported),
            ctypes.byref(enabled),
            ctypes.byref(version),
        )
        if status != 0 or (supported.value, enabled.value, version.value) != (1, 1, 8):
            raise StateError(
                "ADL OverDrive 8 controls are unavailable.",
                details={"native_status": status},
            )
        capabilities, count, pointer = ctypes.c_int32(), ctypes.c_int32(128), ctypes.c_void_p()
        status = self.library.ADL2_Overdrive8_Init_SettingX2_Get(
            self.context,
            adapter.adapter_index,
            ctypes.byref(capabilities),
            ctypes.byref(count),
            ctypes.byref(pointer),
        )
        if status != 0 or not 1 <= count.value <= 128 or capabilities.value < 0:
            raise StateError("ADL native feature query is unavailable or malformed.")
        buffer, offset = self._owned_buffer(pointer, count.value * 16)
        features: list[AdlFeatureObservation] = []
        for index in range(count.value):
            feature = AdlInitialSetting.from_buffer(buffer, offset + index * 16)
            features.append(
                AdlFeatureObservation(
                    feature.feature_bit, feature.minimum, feature.maximum, feature.default
                )
            )
        current_count, current_pointer = ctypes.c_int32(128), ctypes.c_void_p()
        status = self.library.ADL2_Overdrive8_Current_SettingX2_Get(
            self.context,
            adapter.adapter_index,
            ctypes.byref(current_count),
            ctypes.byref(current_pointer),
        )
        if status != 0 or not 1 <= current_count.value <= 128:
            raise StateError("ADL native current query is unavailable or malformed.")
        current_buffer, current_offset = self._owned_buffer(
            current_pointer, current_count.value * 4
        )
        current = tuple(
            ctypes.c_int32.from_buffer(current_buffer, current_offset + index * 4).value
            for index in range(current_count.value)
        )
        if adapter not in self.read_adapters():
            raise StateError("ADL physical adapter relation changed during observation.")
        return AdlControlObservation(adapter, capabilities.value, tuple(features), current)

    def write_clock(
        self, observation: AdlControlObservation, feature_index: int, value: int
    ) -> int:
        self._require_live()
        count = len(observation.features)
        if not 0 <= feature_index < count <= 128 or not -(2**31) <= value < 2**31:
            raise ValidationError("ADL actuator arguments exceed the observed native ABI bounds.")
        if self.allocated_bytes + 8 + count * 16 > 16 * 1024 * 1024:
            raise StateError("ADL actuator buffer allocation bounds are exhausted.")
        settings = ctypes.create_string_buffer(4 + count * 12)
        current = ctypes.create_string_buffer(4 + count * 4)
        self.allocations.extend((settings, current))
        self.allocated_bytes += ctypes.sizeof(settings) + ctypes.sizeof(current)
        ctypes.c_int32.from_buffer(settings).value = count
        ctypes.c_int32.from_buffer(current).value = count
        selected = AdlSingleSetting.from_buffer(settings, 4 + feature_index * 12)
        selected.value, selected.requested, selected.reset = value, 1, 0
        status = self.library.ADL2_Overdrive8_Setting_Set(
            self.context, observation.adapter.adapter_index, settings, current
        )
        if not is_strict_int(status):
            raise ValidationError("ADL native actuator status violates its integer ABI.")
        return status

    def read_owned_integers(self, pointer: ctypes.c_void_p, count: int) -> tuple[int, ...]:
        if not 1 <= count <= 256:
            raise ValidationError("ADL sensor count exceeds allocated result bounds.")
        buffer, offset = self._owned_buffer(pointer, count * 4)
        return tuple(
            ctypes.c_int32.from_buffer(buffer, offset + index * 4).value for index in range(count)
        )

    def _owned_buffer(
        self, pointer: ctypes.c_void_p, length: int
    ) -> tuple[ctypes.Array[ctypes.c_char], int]:
        self._require_live()
        address = pointer.value
        if address is not None:
            for buffer in self.allocations:
                offset = address - ctypes.addressof(buffer)
                if 0 <= offset and offset + length <= ctypes.sizeof(buffer):
                    return buffer, offset
        raise ValidationError("ADL native result has no proved allocated buffer bounds.")


@dataclass(frozen=True, slots=True)
class AdlRuntimeDependencies:
    library_loader: Callable[[], ctypes.CDLL] = load_adl_library

    def __post_init__(self) -> None:
        require_dependencies(owner="AdlRuntimeDependencies", library_loader=self.library_loader)


class AdlRuntime:
    def __init__(self, dependencies: AdlRuntimeDependencies) -> None:
        require_dependencies(owner="AdlRuntime", dependencies=dependencies)
        self.dependencies = dependencies
        self.library: ctypes.CDLL | None = None
        self.active_sessions: list[AdlSession] = []
        self.failed_sessions: list[AdlSession] = []
        self.lock = RLock()
        self.closed = False

    @contextmanager
    def session(self) -> Generator[AdlSession]:
        with self.lock:
            self.require_available()
            if self.library is None:
                self.library = self.dependencies.library_loader()
            session = AdlSession(self.library)
            self.active_sessions.append(session)
        try:
            session.initialize()
            yield session
        finally:
            with self.lock:
                try:
                    status = session.release()
                except ADL_LIFETIME_FAILURES as exception:
                    self.failed_sessions.append(session)
                    raise StateError(
                        "ADL context release is unknown; native resources remain retained.",
                        details={"possible_effect": "unknown"},
                        cause=exception,
                    ) from exception
                else:
                    if status != 0:
                        self.failed_sessions.append(session)
                        raise StateError(
                            "ADL context release failed; native resources remain retained.",
                            details={"native_status": status, "possible_effect": "unknown"},
                        )
                finally:
                    self.active_sessions.remove(session)

    def require_available(self) -> None:
        if self.closed:
            reason = "native_runtime_closed"
        elif self.failed_sessions:
            reason = "native_lifetime_unverified"
        elif self.active_sessions:
            reason = "native_session_busy"
        else:
            return
        raise StateError(
            "ADL native resources are unavailable pending process recovery.",
            details={"reason_code": reason},
        )

    def shutdown(self) -> None:
        with self.lock:
            if self.active_sessions:
                raise StateError("ADL native operations still own their active contexts.")
            self.closed = True
            if self.failed_sessions:
                raise StateError("ADL context release remains unverified; resources are retained.")
            self.library = None
