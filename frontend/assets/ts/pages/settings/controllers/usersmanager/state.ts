/* SoAI - Settings page users manager state [frontend/assets/ts/pages/settings/controllers/usersmanager/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { WebuiUser } from '@core/api/contracts/webuiUserContracts.ts';
import { compareWebuiUserRevision } from '@core/users/userRevision.ts';
import type { UserStats } from '@pages/settings/controllers/usersmanager/types.ts';

const getUserById = (users: readonly WebuiUser[], userId: string): WebuiUser | null => users.find((user) => String(user.id) === userId) ?? null;

const isCurrentUser = (currentUserId: string | null, user: WebuiUser): boolean => currentUserId !== null && String(user.id) === currentUserId;

const getUserStats = (users: readonly WebuiUser[]): UserStats => {
    const adminCount = users.filter((user) => user.isAdmin).length;
    return {
        totalUsers: users.length,
        adminCount
    };
};

const shouldPreventAdminDemotion = (users: readonly WebuiUser[], userId: string): boolean => {
    const user = getUserById(users, userId);
    if (!user || !user.isAdmin) {
        return false;
    }
    return getUserStats(users).adminCount <= 1;
};

const shouldPreventUserDeletion = (users: readonly WebuiUser[], userId: string): boolean => {
    const stats = getUserStats(users);
    return stats.totalUsers <= 1 || shouldPreventAdminDemotion(users, userId);
};

const mergeUserMutationResult = (users: readonly WebuiUser[], incoming: WebuiUser): WebuiUser[] =>
    users.map((current) => {
        if (current.id !== incoming.id) return current;
        const decision = compareWebuiUserRevision(current, incoming);
        if (decision === 'integrity_error') throw new Error('User mutation result conflicts with the current identity revision.');
        return decision === 'newer' ? incoming : current;
    });

export { getUserById, isCurrentUser, getUserStats, mergeUserMutationResult, shouldPreventAdminDemotion, shouldPreventUserDeletion };
