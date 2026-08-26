/* SoAI - Shared tasks operation dry run rendering [frontend/assets/ts/core/tasks/operationDryRunRendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { narrowTextarea } from '@core/dom/narrowElement.ts';
import { parseOperationDryRunPayload, type OperationDryRunPayload } from '@core/tasks/operationPayloads.ts';

type RequireElement = (selector: string, context?: Element) => Element;

interface OperationDryRunTextareaIds {
    plan: string;
    effects: string;
    warnings: string;
}

interface OperationDryRunRenderOptions {
    requireElement: RequireElement;
    root: HTMLElement;
    payload: ApiResponsePayload;
    label: string;
    textareas: OperationDryRunTextareaIds;
    unavailableLabel: string;
    noWarningsLabel: string;
}

interface OperationDryRunDisplayLabels {
    unavailableLabel: string;
    noWarningsLabel: string;
}

interface OperationDryRunDisplayText {
    plan: string;
    effects: string;
    warnings: string;
}

interface OperationDryRunTextElements {
    plan: HTMLElement;
    effects: HTMLElement;
    warnings: HTMLElement;
}

const formatOperationDryRunDisplayText = (payload: OperationDryRunPayload, labels: OperationDryRunDisplayLabels): OperationDryRunDisplayText => ({
    plan: payload.plannedCommands.join('\n') || labels.unavailableLabel,
    effects: payload.predictedEffects.join('\n') || labels.unavailableLabel,
    warnings: payload.warnings.join('\n') || labels.noWarningsLabel
});

const parseOperationDryRunDisplayText = (payload: ApiResponsePayload, label: string, labels: OperationDryRunDisplayLabels): OperationDryRunDisplayText => {
    return formatOperationDryRunDisplayText(parseOperationDryRunPayload(payload, label), labels);
};

const writeTextarea = (options: OperationDryRunRenderOptions, selector: string, value: string): void => {
    const element = options.requireElement(selector, options.root);
    narrowTextarea(element, `${options.label} ${selector}`).value = value;
};

const renderOperationDryRunTextareas = (options: OperationDryRunRenderOptions): void => {
    const displayText = parseOperationDryRunDisplayText(options.payload, options.label, {
        unavailableLabel: options.unavailableLabel,
        noWarningsLabel: options.noWarningsLabel
    });
    writeTextarea(options, options.textareas.plan, displayText.plan);
    writeTextarea(options, options.textareas.effects, displayText.effects);
    writeTextarea(options, options.textareas.warnings, displayText.warnings);
};

const renderOperationDryRunTextElements = (elements: OperationDryRunTextElements, displayText: OperationDryRunDisplayText): void => {
    elements.plan.textContent = displayText.plan;
    elements.effects.textContent = displayText.effects;
    elements.warnings.textContent = displayText.warnings;
};

export { formatOperationDryRunDisplayText, parseOperationDryRunDisplayText, renderOperationDryRunTextareas, renderOperationDryRunTextElements };
export type { OperationDryRunDisplayLabels, OperationDryRunDisplayText, OperationDryRunRenderOptions, OperationDryRunTextareaIds, OperationDryRunTextElements, RequireElement };
