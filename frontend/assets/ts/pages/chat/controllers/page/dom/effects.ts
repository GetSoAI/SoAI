/* SoAI - Chat page DOM effects [frontend/assets/ts/pages/chat/controllers/page/dom/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { resolve, resolveAll } from '@core/dom/dom.ts';
import { resolveModelTypeLabel } from '@core/models/modelTypeLabel.ts';
import { isHTMLElement } from '@core/typeGuards.ts';
import type { ModelData } from '@core/types/modelTypes.ts';
import { clearAssistantHeaderActivityCatalogStatus, syncAssistantHeaderActivityCatalogStatus } from '@features/chat/public.ts';

const ASSISTANT_ACTIVITY_SELECTOR = '.message-role-activity.inline-activity[data-model-id]';
const ACTIVITY_LED_SELECTOR = '[data-model-status-led="true"]';
const ACTIVITY_SEPARATOR_DOT_SELECTOR = '.inline-activity-separator-dot[data-inline-activity-separator="true"]';
const ACTIVITY_MODE_ROOT_SELECTOR = '[data-model-mode="true"]';
const ACTIVITY_MODE_TEXT_SELECTOR = '[data-model-mode-text="true"]';

const applyActivityModeLabel = (activity: HTMLElement, model: ModelData | null): void => {
    const modeRoot = resolve(ACTIVITY_MODE_ROOT_SELECTOR, activity);
    if (!isHTMLElement(modeRoot)) {
        return;
    }
    const modeText = resolve(ACTIVITY_MODE_TEXT_SELECTOR, modeRoot);
    if (!isHTMLElement(modeText)) {
        return;
    }
    const separatorDot = resolve(ACTIVITY_SEPARATOR_DOT_SELECTOR, activity);
    const label = resolveModelTypeLabel(model);
    modeText.textContent = label ?? '';
    modeRoot.hidden = label === null;
    if (isHTMLElement(separatorDot)) {
        separatorDot.hidden = modeRoot.hidden;
    }
};

const applyActivityStatusLed = (activity: HTMLElement, model: ModelData | null, statusManager: { normalizeStatus(status: JsonValue): string }): void => {
    const led = resolve(ACTIVITY_LED_SELECTOR, activity);
    if (!isHTMLElement(led)) {
        return;
    }
    if (!model) {
        clearAssistantHeaderActivityCatalogStatus(activity);
        return;
    }
    syncAssistantHeaderActivityCatalogStatus({ activity, model, statusManager });
};

const syncAssistantHeaderActivities = (inputArguments: { root: Element; modelIndex: Map<string, ModelData>; statusManager: { normalizeStatus(status: JsonValue): string } }): void => {
    const activities = resolveAll(ASSISTANT_ACTIVITY_SELECTOR, inputArguments.root);
    for (const activity of activities) {
        if (!isHTMLElement(activity)) {
            continue;
        }
        const modelId = activity.getAttribute('data-model-id');
        const normalizedModelId = modelId && modelId.trim() ? modelId.trim() : '';
        const model = normalizedModelId ? (inputArguments.modelIndex.get(normalizedModelId) ?? null) : null;
        applyActivityStatusLed(activity, model, inputArguments.statusManager);
        applyActivityModeLabel(activity, model);
    }
};

export { syncAssistantHeaderActivities };
