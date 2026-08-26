/* SoAI - Chat feature stream message spinner status text [frontend/assets/ts/features/chat/stream/streamMessageSpinnerStatusText.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { ChatStreamTranslationKey } from '@core/i18n/translationkeys/chat/stream.generated.ts';

type StreamStatusMessageKey = Extract<ChatStreamTranslationKey, `chat.stream.statusMessages.${number}`>;

const STATUS_MESSAGE_KEYS: readonly StreamStatusMessageKey[] = ['chat.stream.statusMessages.1', 'chat.stream.statusMessages.2', 'chat.stream.statusMessages.3', 'chat.stream.statusMessages.4', 'chat.stream.statusMessages.5', 'chat.stream.statusMessages.6', 'chat.stream.statusMessages.7', 'chat.stream.statusMessages.8', 'chat.stream.statusMessages.9', 'chat.stream.statusMessages.10', 'chat.stream.statusMessages.11', 'chat.stream.statusMessages.12', 'chat.stream.statusMessages.13', 'chat.stream.statusMessages.14', 'chat.stream.statusMessages.15', 'chat.stream.statusMessages.16', 'chat.stream.statusMessages.17', 'chat.stream.statusMessages.18', 'chat.stream.statusMessages.19', 'chat.stream.statusMessages.20', 'chat.stream.statusMessages.21', 'chat.stream.statusMessages.22', 'chat.stream.statusMessages.23', 'chat.stream.statusMessages.24', 'chat.stream.statusMessages.25'];
const RECENT_STATUS_MESSAGE_KEY_LIMIT = 3;

let statusMessageKeyBag: StreamStatusMessageKey[] = [];
const recentStatusMessageKeys: StreamStatusMessageKey[] = [];

const getStatusMessageText = (key: StreamStatusMessageKey): string => {
    switch (key) {
        case 'chat.stream.statusMessages.1':
            return i18n.t('chat.stream.statusMessages.1');
        case 'chat.stream.statusMessages.2':
            return i18n.t('chat.stream.statusMessages.2');
        case 'chat.stream.statusMessages.3':
            return i18n.t('chat.stream.statusMessages.3');
        case 'chat.stream.statusMessages.4':
            return i18n.t('chat.stream.statusMessages.4');
        case 'chat.stream.statusMessages.5':
            return i18n.t('chat.stream.statusMessages.5');
        case 'chat.stream.statusMessages.6':
            return i18n.t('chat.stream.statusMessages.6');
        case 'chat.stream.statusMessages.7':
            return i18n.t('chat.stream.statusMessages.7');
        case 'chat.stream.statusMessages.8':
            return i18n.t('chat.stream.statusMessages.8');
        case 'chat.stream.statusMessages.9':
            return i18n.t('chat.stream.statusMessages.9');
        case 'chat.stream.statusMessages.10':
            return i18n.t('chat.stream.statusMessages.10');
        case 'chat.stream.statusMessages.11':
            return i18n.t('chat.stream.statusMessages.11');
        case 'chat.stream.statusMessages.12':
            return i18n.t('chat.stream.statusMessages.12');
        case 'chat.stream.statusMessages.13':
            return i18n.t('chat.stream.statusMessages.13');
        case 'chat.stream.statusMessages.14':
            return i18n.t('chat.stream.statusMessages.14');
        case 'chat.stream.statusMessages.15':
            return i18n.t('chat.stream.statusMessages.15');
        case 'chat.stream.statusMessages.16':
            return i18n.t('chat.stream.statusMessages.16');
        case 'chat.stream.statusMessages.17':
            return i18n.t('chat.stream.statusMessages.17');
        case 'chat.stream.statusMessages.18':
            return i18n.t('chat.stream.statusMessages.18');
        case 'chat.stream.statusMessages.19':
            return i18n.t('chat.stream.statusMessages.19');
        case 'chat.stream.statusMessages.20':
            return i18n.t('chat.stream.statusMessages.20');
        case 'chat.stream.statusMessages.21':
            return i18n.t('chat.stream.statusMessages.21');
        case 'chat.stream.statusMessages.22':
            return i18n.t('chat.stream.statusMessages.22');
        case 'chat.stream.statusMessages.23':
            return i18n.t('chat.stream.statusMessages.23');
        case 'chat.stream.statusMessages.24':
            return i18n.t('chat.stream.statusMessages.24');
        case 'chat.stream.statusMessages.25':
            return i18n.t('chat.stream.statusMessages.25');
    }
};

const assertStatusMessageKeysAvailable = (): void => {
    if (STATUS_MESSAGE_KEYS.length < 1) {
        throw new Error('Streaming spinner status keys are missing.');
    }
};

const shuffleStatusMessageKeys = (): StreamStatusMessageKey[] => {
    assertStatusMessageKeysAvailable();
    const keys = [...STATUS_MESSAGE_KEYS];
    for (let index = keys.length - 1; index > 0; index -= 1) {
        const swapIndex = Math.floor(Math.random() * (index + 1));
        const current = keys[index];
        const swap = keys[swapIndex];
        if (current === undefined || swap === undefined) {
            throw new Error('Streaming spinner status key shuffle failed.');
        }
        keys[index] = swap;
        keys[swapIndex] = current;
    }
    return keys;
};

const refillStatusMessageKeyBag = (): void => {
    statusMessageKeyBag = shuffleStatusMessageKeys();
};

const isRecentlyIssuedStatusMessageKey = (key: StreamStatusMessageKey, previousKey: StreamStatusMessageKey | null): boolean => {
    return key === previousKey || recentStatusMessageKeys.includes(key);
};

const takeStatusMessageKeyFromBag = (previousKey: StreamStatusMessageKey | null): StreamStatusMessageKey => {
    if (statusMessageKeyBag.length === 0) {
        refillStatusMessageKeyBag();
    }
    let selectedIndex = statusMessageKeyBag.length - 1;
    for (let index = statusMessageKeyBag.length - 1; index >= 0; index -= 1) {
        const candidate = statusMessageKeyBag[index];
        if (candidate !== undefined && !isRecentlyIssuedStatusMessageKey(candidate, previousKey)) {
            selectedIndex = index;
            break;
        }
    }
    const selected = statusMessageKeyBag[selectedIndex];
    if (selected === undefined) {
        throw new Error('Streaming spinner status key bag is empty.');
    }
    statusMessageKeyBag.splice(selectedIndex, 1);
    return selected;
};

const recordIssuedStatusMessageKey = (key: StreamStatusMessageKey): void => {
    recentStatusMessageKeys.push(key);
    while (recentStatusMessageKeys.length > RECENT_STATUS_MESSAGE_KEY_LIMIT) {
        recentStatusMessageKeys.shift();
    }
};

const chooseNextKey = (previousKey: StreamStatusMessageKey | null): StreamStatusMessageKey => {
    const key = takeStatusMessageKeyFromBag(previousKey);
    recordIssuedStatusMessageKey(key);
    return key;
};

export type { StreamStatusMessageKey };
export { STATUS_MESSAGE_KEYS, chooseNextKey, getStatusMessageText };
