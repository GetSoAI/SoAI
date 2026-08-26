/* SoAI - Shared storage keys [frontend/assets/ts/core/storage/keys.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ANIMATION_SPEED_STORAGE_KEY } from '@core/animations/speed.ts';
import { INTERFACE_SCALE_STORAGE_KEY } from '@core/layout/interfaceScale.ts';

interface StorageLocalKeys {
    theme: string;
    accentColor: string;
    surfaceColor: string;
    language: string;
    animationSpeed: string;
    interfaceScale: string;
    session: string;
    chat: string;
    logs: string;
}

const STORAGE_LOCAL_KEYS: StorageLocalKeys = Object.freeze({
    theme: 'soai.ui.theme',
    accentColor: 'soai.ui.accent_color',
    surfaceColor: 'soai.ui.surface_color',
    language: 'soai.ui.language',
    animationSpeed: ANIMATION_SPEED_STORAGE_KEY,
    interfaceScale: INTERFACE_SCALE_STORAGE_KEY,
    session: 'soai.session',
    chat: 'soai.chat.cache',
    logs: 'soai.logs.preferences'
});

const INTERNAL_REMOTE_KEYS: ReadonlySet<string> = new Set(['soai_chat_preferences', 'soai_hardware_prefs', 'soai_page_controls', 'soai_recent_searches', 'soai_session']);

const LOCAL_ONLY_GROUPS: ReadonlySet<string> = Object.freeze(new Set<string>([]));

export { INTERNAL_REMOTE_KEYS, LOCAL_ONLY_GROUPS, STORAGE_LOCAL_KEYS };
export type { StorageLocalKeys };
