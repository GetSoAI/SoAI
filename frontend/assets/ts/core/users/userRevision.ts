/* SoAI - WebUI user identity revision ordering [frontend/assets/ts/core/users/userRevision.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { WebuiUser } from '@core/api/contracts/webuiUserContracts.ts';

type WebuiUserRevisionDecision = 'newer' | 'equal' | 'stale' | 'integrity_error';

const hasEqualRevisionOwnedFields = (left: WebuiUser, right: WebuiUser): boolean => left.id === right.id && left.username === right.username && left.isAdmin === right.isAdmin && left.workspacePath === right.workspacePath && left.defaultWorkspacePath === right.defaultWorkspacePath;

const compareWebuiUserRevision = (current: WebuiUser, incoming: WebuiUser): WebuiUserRevisionDecision => {
    if (current.id !== incoming.id) return 'integrity_error';
    if (incoming.identityRevision > current.identityRevision) return 'newer';
    if (incoming.identityRevision < current.identityRevision) return 'stale';
    return hasEqualRevisionOwnedFields(current, incoming) ? 'equal' : 'integrity_error';
};

export { compareWebuiUserRevision };
export type { WebuiUserRevisionDecision };
