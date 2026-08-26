/* SoAI - Logs page scroll position ownership [frontend/assets/ts/pages/logs/controllers/page/logsPageScrollController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getPageHeaderAnimator } from '@core/animations/service.ts';

export const scrollLogsToBottom = (root: HTMLElement): void => {
    getPageHeaderAnimator().setScrollTopWithoutReaction(root, root.scrollHeight);
};

export const isLogsAtBottom = (root: HTMLElement, thresholdPx: number): boolean => {
    const distance = root.scrollHeight - root.scrollTop - root.clientHeight;
    return distance <= thresholdPx;
};
