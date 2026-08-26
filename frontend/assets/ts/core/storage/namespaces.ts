/* SoAI - Shared storage namespaces [frontend/assets/ts/core/storage/namespaces.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AnimationType, SyncGroup } from '@core/storage/types.ts';

type LocalStorageGroup = 'ui' | 'chat' | 'logs' | 'misc';

const LOG_LINE_LIMITS: readonly number[] = Object.freeze([100, 250, 500, 1000, 2000, 5000]);

const CROSS_TAB_SYNC_GROUPS: ReadonlySet<SyncGroup> = Object.freeze(new Set<SyncGroup>(['ui', 'logs', 'terminal', 'search', 'hardware', 'filters', 'wizard', 'settings']));

const ANIMATION_EFFECTS: readonly AnimationType[] = Object.freeze(['fade', 'slide', 'scale', 'zoom', 'lateral']);

const LOCAL_STORAGE_GROUPS: readonly LocalStorageGroup[] = ['ui', 'chat', 'logs', 'misc'];

export { ANIMATION_EFFECTS, CROSS_TAB_SYNC_GROUPS, LOCAL_STORAGE_GROUPS, LOG_LINE_LIMITS };
export type { LocalStorageGroup };
