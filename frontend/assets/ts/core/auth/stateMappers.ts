/* SoAI - Shared auth state mappers [frontend/assets/ts/core/auth/stateMappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeWebuiUser, type WebuiUser } from '@core/api/contracts/webuiUserContracts.ts';
import { normalizeCrossTabRevision, serializeCrossTabRevision } from '@core/crosstab/revision.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { SessionPayload, SharedAuthState } from '@core/auth/types.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

const buildSessionPayload = (user: WebuiUser | null): SessionPayload | null =>
    user
        ? {
              userId: String(user.id),
              username: user.username,
              isAdmin: user.isAdmin,
              loginTime: new Date().toISOString()
          }
        : null;

const extractUserFields = (source: WebuiUser): WebuiUser => ({ ...source });

const serializeUser = async (source: WebuiUser): Promise<WebuiUser> => extractUserFields(source);

const parseAuthUser = (value: JsonValue | undefined): WebuiUser | null => {
    if (!isJsonObject(value)) {
        return null;
    }
    try {
        return decodeWebuiUser(value, 'Shared authenticated user');
    } catch (error) {
        errorHandler.debug('Auth', 'Discarded malformed shared authenticated user', ensureError(error));
        return null;
    }
};

const serializeAuthUser = (user: WebuiUser): JsonObject => ({
    id: user.id,
    username: user.username,
    'is_admin': user.isAdmin,
    'workspace_path': user.workspacePath,
    'workspace_path_resolved': user.workspacePathResolved,
    'default_workspace_path': user.defaultWorkspacePath,
    'identity_revision': user.identityRevision
});

const parseSharedAuthState = (value: JsonValue | undefined): SharedAuthState | null => {
    if (!isJsonObject(value)) return null;
    const revision = normalizeCrossTabRevision(value['revision']);
    if (revision === null) return null;
    const isAuthenticated = value['is_authenticated'] === true;
    const user = isAuthenticated ? parseAuthUser(value['user']) : null;
    if (isAuthenticated && user === null) return null;
    return { revision, isAuthenticated, user };
};

const serializeSharedAuthState = (state: SharedAuthState): JsonObject => ({
    revision: serializeCrossTabRevision(state.revision),
    'is_authenticated': state.isAuthenticated,
    user: state.user ? serializeAuthUser(state.user) : null
});

export { buildSessionPayload, extractUserFields, parseSharedAuthState, serializeAuthUser, serializeSharedAuthState, serializeUser };
