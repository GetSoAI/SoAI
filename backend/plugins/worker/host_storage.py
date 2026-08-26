"""SoAI - Plugin worker host disk reservation registry [backend/plugins/worker/host_storage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.protocols_storage import (
    DiskSpaceReservationLeaseProtocol,
    DiskSpaceWriteClaimProtocol,
)
from core.types.json import JSONDict
from plugins.worker.payload_fields import (
    read_dict_field,
    read_required_int_field,
    read_required_named_str_field,
)

if TYPE_CHECKING:
    from core.hardware.protocols_storage import StorageManagerProtocol

__all__ = ("PluginWorkerHostStorageReservations",)

HOST_FIELD_LABEL = "Worker host storage request field"


class PluginWorkerHostStorageReservations:
    def __init__(self) -> None:
        self._leases_by_worker: dict[int, dict[str, DiskSpaceReservationLeaseProtocol]] = {}
        self._claims_by_worker: dict[int, dict[str, DiskSpaceWriteClaimProtocol]] = {}
        self._claim_reservation_ids_by_worker: dict[int, dict[str, str]] = {}

    def reserve_disk_space(
        self,
        *,
        worker_id: int,
        storage_manager: StorageManagerProtocol,
        payload: JSONDict,
    ) -> str:
        lease = storage_manager.reserve_disk_space(
            path=read_required_named_str_field(payload, "path", label=HOST_FIELD_LABEL),
            required_bytes=read_required_int_field(
                payload,
                "required_bytes",
                label=HOST_FIELD_LABEL,
            ),
            operation=read_required_named_str_field(payload, "operation", label=HOST_FIELD_LABEL),
            details=read_dict_field(payload, "details", label=HOST_FIELD_LABEL),
        )
        reservation_id = secrets.token_hex(24)
        worker_leases = self._leases_by_worker.get(worker_id)
        if worker_leases is None:
            worker_leases = {}
            self._leases_by_worker[worker_id] = worker_leases
        worker_leases[reservation_id] = lease
        return reservation_id

    def register_reservation(
        self,
        *,
        worker_id: int,
        lease: DiskSpaceReservationLeaseProtocol,
    ) -> str:
        reservation_id = secrets.token_hex(24)
        worker_leases = self._leases_by_worker.get(worker_id)
        if worker_leases is None:
            worker_leases = {}
            self._leases_by_worker[worker_id] = worker_leases
        worker_leases[reservation_id] = lease
        return reservation_id

    def claim_reservation(self, *, worker_id: int, payload: JSONDict) -> str:
        reservation_id = read_required_named_str_field(
            payload,
            "reservation_id",
            label=HOST_FIELD_LABEL,
        )
        lease = self._require_lease(
            worker_id,
            reservation_id,
        )
        claim = lease.claim_write_bytes(
            read_required_int_field(payload, "bytes_to_write", label=HOST_FIELD_LABEL),
        )
        claim_id = secrets.token_hex(24)
        worker_claims = self._claims_by_worker.get(worker_id)
        if worker_claims is None:
            worker_claims = {}
            self._claims_by_worker[worker_id] = worker_claims
        worker_claims[claim_id] = claim
        worker_claim_reservation_ids = self._claim_reservation_ids_by_worker.get(worker_id)
        if worker_claim_reservation_ids is None:
            worker_claim_reservation_ids = {}
            self._claim_reservation_ids_by_worker[worker_id] = worker_claim_reservation_ids
        worker_claim_reservation_ids[claim_id] = reservation_id
        return claim_id

    def commit_claim(self, *, worker_id: int, payload: JSONDict) -> None:
        claim_id = read_required_named_str_field(payload, "claim_id", label=HOST_FIELD_LABEL)
        claim = self._require_claim(worker_id, claim_id)
        claim.commit()
        self._drop_claim(worker_id, claim_id)

    def rollback_claim(self, *, worker_id: int, payload: JSONDict) -> None:
        claim_id = read_required_named_str_field(payload, "claim_id", label=HOST_FIELD_LABEL)
        claim = self._require_claim(worker_id, claim_id)
        claim.rollback()
        self._drop_claim(worker_id, claim_id)

    def release_reservation(self, *, worker_id: int, payload: JSONDict) -> None:
        reservation_id = read_required_named_str_field(
            payload,
            "reservation_id",
            label=HOST_FIELD_LABEL,
        )
        self.release_reservation_id(
            worker_id=worker_id,
            reservation_id=reservation_id,
            require_active=True,
        )

    def release_reservation_id(
        self,
        *,
        worker_id: int,
        reservation_id: str,
        require_active: bool = False,
    ) -> None:
        worker_leases = self._leases_by_worker.get(worker_id)
        if worker_leases is None:
            if require_active:
                raise ValidationError("Storage reservation is not active for worker.")
            return
        lease = worker_leases.get(reservation_id)
        if lease is None:
            if require_active:
                raise ValidationError("Storage reservation is not active for worker.")
            return
        self._rollback_claims_for_reservation(worker_id=worker_id, reservation_id=reservation_id)
        lease.release()
        worker_leases.pop(reservation_id)
        if not worker_leases:
            self._leases_by_worker.pop(worker_id, None)

    def release_worker_reservations(self, worker_id: int) -> None:
        worker_claims = self._claims_by_worker.pop(worker_id, {})
        self._claim_reservation_ids_by_worker.pop(worker_id, None)
        for claim in worker_claims.values():
            claim.rollback()
        worker_leases = self._leases_by_worker.pop(worker_id, {})
        for lease in worker_leases.values():
            lease.release()

    def _require_lease(
        self,
        worker_id: int,
        reservation_id: str,
    ) -> DiskSpaceReservationLeaseProtocol:
        worker_leases = self._leases_by_worker.get(worker_id)
        if worker_leases is None:
            raise ValidationError("Storage reservation is not active for worker.")
        lease = worker_leases.get(reservation_id)
        if lease is None:
            raise ValidationError("Storage reservation is not active for worker.")
        return lease

    def _require_claim(self, worker_id: int, claim_id: str) -> DiskSpaceWriteClaimProtocol:
        worker_claims = self._claims_by_worker.get(worker_id)
        if worker_claims is None:
            raise ValidationError("Storage write claim is not active for worker.")
        claim = worker_claims.get(claim_id)
        if claim is None:
            raise ValidationError("Storage write claim is not active for worker.")
        return claim

    def _drop_claim(self, worker_id: int, claim_id: str) -> None:
        worker_claims = self._claims_by_worker.get(worker_id)
        if worker_claims is None:
            return
        worker_claims.pop(claim_id, None)
        if not worker_claims:
            self._claims_by_worker.pop(worker_id, None)
        worker_claim_reservation_ids = self._claim_reservation_ids_by_worker.get(worker_id)
        if worker_claim_reservation_ids is not None:
            worker_claim_reservation_ids.pop(claim_id, None)
            if not worker_claim_reservation_ids:
                self._claim_reservation_ids_by_worker.pop(worker_id, None)

    def _rollback_claims_for_reservation(self, *, worker_id: int, reservation_id: str) -> None:
        worker_claim_reservation_ids = self._claim_reservation_ids_by_worker.get(worker_id)
        if worker_claim_reservation_ids is None:
            return
        claim_ids = [
            claim_id
            for claim_id, claim_reservation_id in worker_claim_reservation_ids.items()
            if claim_reservation_id == reservation_id
        ]
        for claim_id in claim_ids:
            claim = self._require_claim(worker_id, claim_id)
            claim.rollback()
            self._drop_claim(worker_id, claim_id)
