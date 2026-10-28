"""SoAI - Fresh owned-session exit observations [backend/core/process/group_exit_observation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from enum import StrEnum
from typing import TYPE_CHECKING

import psutil

from core.errors.exceptions import ProcessError

if TYPE_CHECKING:
    from core.concurrency.deadlines import MonotonicDeadline

__all__ = ("OwnedGroupExitObservation", "observe_owned_process_group")


class OwnedGroupExitObservation(StrEnum):
    TERMINAL = "terminal"
    LIVE = "live"
    UNVERIFIED = "unverified"


def observe_owned_process_group(
    group_id: int, *, deadline: MonotonicDeadline | None = None
) -> OwnedGroupExitObservation:
    session_id = os.getsid(group_id)
    identities = _current_process_ids()
    if group_id not in identities:
        return OwnedGroupExitObservation.UNVERIFIED
    sessions: dict[int, int] = {}
    owned_members: dict[int, psutil.Process] = {}
    absent: set[int] = set()
    absence_observed = False
    for identity in sorted(identities):
        try:
            member_session = os.getsid(identity)
            sessions[identity] = member_session
            if member_session == session_id:
                member = psutil.Process(identity)
                owned_members[identity] = member
                member_state = _member_exit_state(member)
                if member_state != OwnedGroupExitObservation.TERMINAL:
                    return member_state
        except (ProcessLookupError, psutil.NoSuchProcess):
            if _current_absence_census(identity) is None:
                return OwnedGroupExitObservation.UNVERIFIED
            absent.add(identity)
            absence_observed = True
        except psutil.Error as exception:
            raise ProcessError(
                "Owned process identity query failed.", cause=exception
            ) from exception
        if deadline is not None and deadline.expired():
            return OwnedGroupExitObservation.UNVERIFIED
    closing_identities = _current_process_ids()
    if absent & closing_identities:
        return OwnedGroupExitObservation.UNVERIFIED
    pending = closing_identities - identities
    for identity, previous_session in sessions.items():
        if identity in absent:
            continue
        if identity not in closing_identities:
            if previous_session == session_id:
                return OwnedGroupExitObservation.UNVERIFIED
            continue
        try:
            current_session = os.getsid(identity)
            if previous_session == session_id:
                if current_session != previous_session:
                    return OwnedGroupExitObservation.UNVERIFIED
                member_state = _member_exit_state(owned_members[identity])
                if member_state != OwnedGroupExitObservation.TERMINAL:
                    return member_state
            elif current_session == session_id:
                return OwnedGroupExitObservation.UNVERIFIED
        except (ProcessLookupError, psutil.NoSuchProcess):
            if previous_session == session_id:
                return OwnedGroupExitObservation.UNVERIFIED
            current_identities = _current_absence_census(identity)
            if current_identities is None or absent & current_identities:
                return OwnedGroupExitObservation.UNVERIFIED
            absent.add(identity)
            pending.update(current_identities)
            absence_observed = True
        except psutil.Error as exception:
            raise ProcessError(
                "Owned process identity query failed.", cause=exception
            ) from exception
        if deadline is not None and deadline.expired():
            return OwnedGroupExitObservation.UNVERIFIED
    if absence_observed:
        pending.update(closing_identities)
    checked: set[int] = set() if absence_observed else identities - absent
    while pending:
        if deadline is not None and deadline.expired():
            return OwnedGroupExitObservation.UNVERIFIED
        identity = pending.pop()
        if identity in checked or identity in absent:
            continue
        if identity in owned_members:
            member_state = _owned_member_observation(owned_members[identity], session_id)
            if member_state != OwnedGroupExitObservation.TERMINAL:
                return member_state
        elif not (
            _enumerated_process_is_outside_session(identity, session_id)
            if identity in sessions
            else _fresh_process_is_outside_session(identity, session_id)
        ):
            current_identities = _current_absence_census(identity)
            if current_identities is None or absent & current_identities:
                return OwnedGroupExitObservation.UNVERIFIED
            absent.add(identity)
            checked.clear()
            pending.update(current_identities)
            absence_observed = True
        checked.add(identity)
    if deadline is not None and deadline.expired():
        return OwnedGroupExitObservation.UNVERIFIED
    if os.getsid(group_id) != session_id:
        raise ProcessError("Owned process-group session identity changed during observation.")
    for member in owned_members.values():
        member_state = _owned_member_observation(member, session_id)
        if member_state != OwnedGroupExitObservation.TERMINAL:
            return member_state
    if os.getsid(group_id) != session_id:
        raise ProcessError("Owned process-group session identity changed during observation.")
    if deadline is not None and deadline.expired():
        return OwnedGroupExitObservation.UNVERIFIED
    return OwnedGroupExitObservation.TERMINAL


def _current_process_ids() -> set[int]:
    try:
        identities = psutil.pids()
    except psutil.Error as exception:
        raise ProcessError("Owned process-group census failed.", cause=exception) from exception
    unique_identities = set(identities)
    if len(identities) != len(unique_identities):
        raise ProcessError("Owned process-group census contains ambiguous identities.")
    return unique_identities


def _current_absence_census(identity: int) -> set[int] | None:
    try:
        os.getsid(identity)
    except ProcessLookupError:
        identities = _current_process_ids()
        if identity in identities:
            return None
        try:
            os.getsid(identity)
        except ProcessLookupError:
            return identities
    return None


def _member_exit_state(member: psutil.Process) -> OwnedGroupExitObservation:
    if not member.is_running():
        return OwnedGroupExitObservation.UNVERIFIED
    if member.status() != psutil.STATUS_ZOMBIE:
        return OwnedGroupExitObservation.LIVE
    return OwnedGroupExitObservation.TERMINAL


def _owned_member_observation(member: psutil.Process, session_id: int) -> OwnedGroupExitObservation:
    try:
        if os.getsid(member.pid) != session_id:
            return OwnedGroupExitObservation.UNVERIFIED
        member_state = _member_exit_state(member)
        if member_state != OwnedGroupExitObservation.TERMINAL:
            return member_state
        if os.getsid(member.pid) != session_id or not member.is_running():
            return OwnedGroupExitObservation.UNVERIFIED
    except (ProcessLookupError, psutil.NoSuchProcess):
        return OwnedGroupExitObservation.UNVERIFIED
    except psutil.Error as exception:
        raise ProcessError("Owned process identity query failed.", cause=exception) from exception
    return OwnedGroupExitObservation.TERMINAL


def _enumerated_process_is_outside_session(identity: int, session_id: int) -> bool:
    try:
        return os.getsid(identity) != session_id
    except ProcessLookupError:
        return False


def _fresh_process_is_outside_session(identity: int, session_id: int) -> bool:
    try:
        member = psutil.Process(identity)
        if not member.is_running():
            return False
        outside = os.getsid(identity) != session_id
        return outside and member.is_running()
    except (ProcessLookupError, psutil.NoSuchProcess):
        return False
    except psutil.Error as exception:
        raise ProcessError("Owned process identity query failed.", cause=exception) from exception
