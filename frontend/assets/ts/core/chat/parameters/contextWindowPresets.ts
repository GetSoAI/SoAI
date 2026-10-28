/* SoAI - Context-window preset controls [frontend/assets/ts/core/chat/parameters/contextWindowPresets.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { narrowButton } from '@core/dom/narrowElement.ts';
import { formatInvariantNumber } from '@core/localization/public.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { renderLabelAttributes, type TrustedHtml } from '@core/security/public.ts';
import { joinUiHtml, uiAttr, uiHtml } from '@core/security/uiHtml.ts';

const CONTEXT_WINDOW_PRESET_ACTION = 'chat-parameters:set-context-window-preset';
const CONTEXT_WINDOW_PRESETS: readonly number[] = Object.freeze([65_536, 98_304, 131_072, 262_144]);

const isContextWindowPresetAction = (value: string | undefined): value is typeof CONTEXT_WINDOW_PRESET_ACTION => value === CONTEXT_WINDOW_PRESET_ACTION;

const readContextWindowPreset = (element: Element): number => {
    const button = narrowButton(element, 'Context-window preset');
    const preset = CONTEXT_WINDOW_PRESETS.find((tokens) => String(tokens) === button.value);
    if (preset === undefined) throw new Error('Context-window preset value is invalid');
    return preset;
};

const renderContextWindowPresetsMarkup = (modalId: string): TrustedHtml => {
    const buttons = joinUiHtml(
        CONTEXT_WINDOW_PRESETS.map((tokens) => {
            const label = `${formatInvariantNumber(tokens / 1024)}k`;
            return uiHtml`<button type="button" class="ui-button ui-button-xs" data-action="${uiAttr(CONTEXT_WINDOW_PRESET_ACTION)}" value="${uiAttr(tokens)}" dir="ltr" ${renderLabelAttributes(label)} data-modal-localize="text">${label}</button>`;
        })
    );
    return uiHtml`<div class="chat-context-window-presets" role="group" aria-labelledby="${uiAttr(modalUiId(modalId, 'chat-model-context-window-tokens-label'))}">${buttons}</div>`;
};

export { CONTEXT_WINDOW_PRESET_ACTION, isContextWindowPresetAction, readContextWindowPreset, renderContextWindowPresetsMarkup };
