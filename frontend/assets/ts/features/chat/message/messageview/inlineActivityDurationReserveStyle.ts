/* SoAI - Inline activity duration reserve width ownership [frontend/assets/ts/features/chat/message/messageview/inlineActivityDurationReserveStyle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { INLINE_ACTIVITY_DURATION_RESERVE_PROPERTY, resolveInlineActivityDurationReserveCharacters, type InlineActivityDurationArguments } from '@features/chat/message/messageview/inlineActivityDuration.ts';

const syncInlineActivityDurationReserveStyle = (durationNode: HTMLElement, inputArguments: InlineActivityDurationArguments): boolean => {
    const reserveCharacters = resolveInlineActivityDurationReserveCharacters(inputArguments);
    const currentValue = durationNode.style.getPropertyValue(INLINE_ACTIVITY_DURATION_RESERVE_PROPERTY).trim();
    if (reserveCharacters === null || reserveCharacters <= 0) {
        if (currentValue === '') {
            return false;
        }
        durationNode.style.removeProperty(INLINE_ACTIVITY_DURATION_RESERVE_PROPERTY);
        return true;
    }
    const nextValue = String(Math.floor(reserveCharacters));
    if (currentValue === nextValue) {
        return false;
    }
    durationNode.style.setProperty(INLINE_ACTIVITY_DURATION_RESERVE_PROPERTY, nextValue);
    return true;
};

export { syncInlineActivityDurationReserveStyle };
