/* SoAI - Shared tasks task counter text [frontend/assets/ts/core/tasks/taskCounterText.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { isHTMLElement } from '@core/typeGuards.ts';

const TASK_COUNTER_OUTPUT_SELECTOR = '[data-task-counter-output="true"]';
const ZERO_TASK_COUNTER_HIDE_DELAY_MS = 5000;

const formatTrackedTaskCounter = (count: number): string => i18n.plural('taskManager.header.taskCounter', count, { count });

const resolveTrackedTaskCounterText = (source: HTMLElement | null): string => {
    const text = source?.dataset['taskCounterText']?.trim();
    if (text) {
        return text;
    }
    const count = Number(source?.dataset['taskCount']);
    return formatTrackedTaskCounter(Number.isFinite(count) ? count : 0);
};

const isTrackedTaskCounterVisible = (source: HTMLElement | null): boolean => source?.dataset['taskCounterVisible'] === 'true';

const resolveCounterGeneration = (source: HTMLElement): number => {
    const generation = Number(source.dataset['taskCounterGeneration']);
    return Number.isFinite(generation) ? generation : 0;
};

const applyTrackedTaskCounterOutputs = (root: Document, text: string, visible: boolean): void => {
    for (const counter of dom.resolveAll(TASK_COUNTER_OUTPUT_SELECTOR, root)) {
        if (!isHTMLElement(counter)) {
            throw new Error('Task counter output must be an HTMLElement');
        }
        dom.setText(counter, visible ? text : '');
        counter.hidden = !visible;
    }
};

const scheduleZeroTaskCounterHide = (root: Document, source: HTMLElement, generation: number): void => {
    const win = source.ownerDocument.defaultView;
    if (!win) {
        throw new Error('Task counter source requires a Window');
    }
    win.setTimeout((): void => {
        const latestGeneration = resolveCounterGeneration(source);
        const latestCount = Number(source.dataset['taskCount']);
        if (latestGeneration !== generation || latestCount !== 0) {
            return;
        }
        source.dataset['taskCounterVisible'] = 'false';
        applyTrackedTaskCounterOutputs(root, '', false);
    }, ZERO_TASK_COUNTER_HIDE_DELAY_MS);
};

const syncTrackedTaskCounter = (count: number, root: Document, source: Element | null): void => {
    const text = formatTrackedTaskCounter(count);
    if (!isHTMLElement(source)) {
        throw new Error('Task counter source must be an HTMLElement');
    }
    const previousCount = Number(source.dataset['taskCount']);
    const wasVisible = source.dataset['taskCounterVisible'] === 'true';
    const shouldDelayZero = count === 0 && (wasVisible || previousCount > 0);
    const shouldShow = count > 0 || shouldDelayZero;
    const generation = resolveCounterGeneration(source) + 1;
    source.dataset['taskCount'] = String(count);
    source.dataset['taskCounterText'] = text;
    source.dataset['taskCounterVisible'] = shouldShow ? 'true' : 'false';
    source.dataset['taskCounterGeneration'] = String(generation);
    applyTrackedTaskCounterOutputs(root, text, shouldShow);
    if (shouldDelayZero) {
        scheduleZeroTaskCounterHide(root, source, generation);
    }
};

export { formatTrackedTaskCounter, isTrackedTaskCounterVisible, resolveTrackedTaskCounterText, syncTrackedTaskCounter };
