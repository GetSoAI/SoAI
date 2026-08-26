/* SoAI - Shared collection page recent item tracker [frontend/assets/ts/core/collectionpage/recentItemTracker.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';
import { isString } from '@core/typeGuards.ts';
import { collectRecentItemDiffIds } from '@core/collectionpage/recentItemSnapshot.ts';
import { i18n } from '@core/i18n/index.ts';

interface RecentItemTracker {
    beginSync(): number;
    armSync(sequence: number): boolean;
    consumeSnapshot(snapshot: JsonObject | null | undefined, acceptAddedIdentifier?: (identifier: string) => boolean): void;
    markMany(identifiers: readonly string[]): void;
    unmarkMany(identifiers: readonly string[]): void;
    listMarked(): string[];
    resolveRevealIdentifiers(orderedIdentifiers: readonly string[]): string[];
    consumeRevealIdentifiers(orderedIdentifiers: readonly string[]): string[];
    isMarked(identifier: string | null | undefined): boolean;
    clear(): void;
}

const normalizeRecentItemIdentifier = (value: string | null | undefined): string => {
    return isString(value) ? value.trim() : '';
};

const renderRecentItemBadge = (sanitize: (value: string) => string): string => {
    const label = sanitize(i18n.t('common.new'));
    return `<span class="new-item-badge">${label}</span>`;
};

const createRecentItemTracker = (): RecentItemTracker => {
    const marked = new Set<string>();
    const pendingReveal = new Set<string>();
    let armed = false;
    let syncSequence = 0;

    const normalizeIdentifiers = (identifiers: readonly string[]): string[] => {
        const normalized: string[] = [];
        for (const value of identifiers) {
            const identifier = normalizeRecentItemIdentifier(value);
            if (identifier) {
                normalized.push(identifier);
            }
        }
        return normalized;
    };

    const addIdentifiers = (identifiers: readonly string[]): void => {
        for (const identifier of normalizeIdentifiers(identifiers)) {
            marked.add(identifier);
        }
    };

    const addRevealIdentifiers = (identifiers: readonly string[]): void => {
        for (const identifier of normalizeIdentifiers(identifiers)) {
            pendingReveal.add(identifier);
        }
    };

    const deleteIdentifiers = (identifiers: readonly string[]): void => {
        for (const identifier of normalizeIdentifiers(identifiers)) {
            marked.delete(identifier);
            pendingReveal.delete(identifier);
        }
    };

    return {
        beginSync: (): number => {
            syncSequence += 1;
            armed = false;
            return syncSequence;
        },
        armSync: (sequence: number): boolean => {
            if (sequence === syncSequence) {
                armed = true;
                return true;
            }
            return false;
        },
        consumeSnapshot: (snapshot: JsonObject | null | undefined, acceptAddedIdentifier?: (identifier: string) => boolean): void => {
            deleteIdentifiers(collectRecentItemDiffIds(snapshot, 'removed'));
            if (!armed) {
                return;
            }
            const added = collectRecentItemDiffIds(snapshot, 'added').filter((identifier) => acceptAddedIdentifier?.(identifier) ?? true);
            addIdentifiers(added);
            addRevealIdentifiers(added);
        },
        markMany: (identifiers: readonly string[]): void => {
            addIdentifiers(identifiers);
        },
        unmarkMany: (identifiers: readonly string[]): void => {
            deleteIdentifiers(identifiers);
        },
        listMarked: (): string[] => {
            return [...marked.values()];
        },
        resolveRevealIdentifiers: (orderedIdentifiers: readonly string[]): string[] => {
            const revealed: string[] = [];
            for (const identifier of normalizeIdentifiers(orderedIdentifiers)) {
                if (!pendingReveal.has(identifier)) {
                    continue;
                }
                revealed.push(identifier);
            }
            return revealed;
        },
        consumeRevealIdentifiers: (orderedIdentifiers: readonly string[]): string[] => {
            const revealed: string[] = [];
            for (const identifier of normalizeIdentifiers(orderedIdentifiers)) {
                if (!pendingReveal.has(identifier)) {
                    continue;
                }
                pendingReveal.delete(identifier);
                revealed.push(identifier);
            }
            return revealed;
        },
        isMarked: (identifier: string | null | undefined): boolean => {
            const normalized = normalizeRecentItemIdentifier(identifier);
            return normalized ? marked.has(normalized) : false;
        },
        clear: (): void => {
            syncSequence += 1;
            marked.clear();
            pendingReveal.clear();
            armed = false;
        }
    };
};

export { createRecentItemTracker, renderRecentItemBadge };
export type { RecentItemTracker };
