/* SoAI - Image widget duration presentation without media rendering [frontend/assets/ts/features/chat/message/messageview/imageWidgetDuration.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { isEpochMsNumber } from '@core/time/epochMs.ts';
import { resolveInlineToolActivityDurationLabel } from '@features/chat/message/messageview/inlineToolDurationLabel.ts';
import type { ChatActivityDurationDisplayMode } from '@features/chat/message/messageview/activityDurationDisplay.ts';

const syncImageWidgetDuration = (widget: HTMLElement, nowMs: number, displayMode: ChatActivityDurationDisplayMode): void => {
    const running = widget.dataset['imageWidgetStatus'] === 'running';
    const startedAtMs = Number(widget.getAttribute('data-started-at-ms'));
    const durationValue = widget.getAttribute('data-settled-duration-ms');
    const durationMs = durationValue === null ? undefined : Number(durationValue);
    const label = running && (displayMode !== 'all' || !isEpochMsNumber(startedAtMs)) ? null : resolveInlineToolActivityDurationLabel({ status: running ? 'running' : 'completed', ...(durationMs === undefined ? {} : { durationMs }), ...(running ? { startedAtMs } : {}), nowMs });
    const timing = dom.resolve(':scope > .assistant-image-widget__header > .assistant-image-widget__timing', widget);
    if (!(timing instanceof HTMLElement)) throw new Error('Image widget duration requires its timing container');
    const existing = dom.resolve(':scope > .assistant-image-widget__duration', timing);
    if (label === null) {
        if (existing instanceof HTMLElement) existing.hidden = true;
        return;
    }
    const node = existing instanceof HTMLElement ? existing : widget.ownerDocument.createElement('span');
    node.className = 'assistant-image-widget__duration';
    if (node.textContent !== label) node.textContent = label;
    node.hidden = false;
    if (node.parentElement !== timing) timing.append(node);
};

export { syncImageWidgetDuration };
