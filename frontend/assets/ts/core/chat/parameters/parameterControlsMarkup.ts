/* SoAI - Shared chat request parameter controls markup [frontend/assets/ts/core/chat/parameters/parameterControlsMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { modalUiId } from '@core/modals/uiIds.ts';
import { renderContextWindowPresetsMarkup } from '@core/chat/parameters/contextWindowPresets.ts';
import type { ChatParameterControlsStrings } from '@core/chat/parameters/parameterControlStrings.ts';
import { renderParameterFieldHeader } from '@core/chat/parameters/parameterSendToggleMarkup.ts';
import { renderReasoningEffortOptionsMarkup } from '@core/chat/parameters/reasoningEffortPresentation.ts';
import { uiAttr } from '@core/security/uiHtml.ts';
import { renderToggleSwitch } from '@core/toggleSwitch.ts';
import { renderStandardDropdownSelectControl } from '@core/ui/dropdown/selectControl.ts';

const buildParameterToggleMarkup = (inputArguments: { modalId: string; token: string; inputClassName: string; checked: boolean; trueLabel: string; falseLabel: string; inline?: boolean; dataParameter?: string; dataSetting?: string }): string => {
    const dataset: Record<string, string> = {};
    if (inputArguments.dataParameter) {
        dataset['param'] = inputArguments.dataParameter;
    }
    if (inputArguments.dataSetting) {
        dataset['setting'] = inputArguments.dataSetting;
    }
    return renderToggleSwitch({
        id: modalUiId(inputArguments.modalId, inputArguments.token),
        checked: inputArguments.checked,
        labels: {
            trueLabel: inputArguments.trueLabel,
            falseLabel: inputArguments.falseLabel
        },
        inline: inputArguments.inline,
        inputClassName: inputArguments.inputClassName,
        inputDataset: dataset,
        wrapperTag: 'div'
    });
};

const renderSystemPromptLockMarkup = (modalId: string, strings: ChatParameterControlsStrings): string => `
      <div class="form-col-secondary form-col-toggle">
        <label for="${uiAttr(modalUiId(modalId, 'system-prompt-lock-checkbox')).html}" data-modal-localize="text">${strings.systemPromptLock}</label>
        ${buildParameterToggleMarkup({
            modalId,
            token: 'system-prompt-lock-checkbox',
            inputClassName: 'system-prompt-lock-checkbox',
            checked: false,
            trueLabel: strings.systemPromptLockLocked,
            falseLabel: strings.systemPromptLockUnlocked,
            inline: true,
            dataSetting: 'prompts.user_system_prompt_lock_enabled'
        })}
        <span class="chat-configuration-hint" data-modal-localize="text">${strings.systemPromptLockHint}</span>
      </div>`;

const renderChatParameterControlsMarkup = (inputArguments: { modalId: string; strings: ChatParameterControlsStrings; includeSystemPromptLock?: boolean; includeContextWindowPresets?: boolean }): string => {
    const { modalId, strings } = inputArguments;
    const uiId = (token: string): string => modalUiId(modalId, token);
    const uiIdAttr = (token: string): string => uiAttr(uiId(token)).html;
    const temperatureValueId = uiId('temperature-value');
    const topPValueId = uiId('top-p-value');
    const frequencyPenaltyValueId = uiId('frequency-penalty-value');
    const presencePenaltyValueId = uiId('presence-penalty-value');
    const topPLabel = `${strings.topP} <span id="${uiAttr(topPValueId).html}" class="top-p-value">1.0</span>`;
    const frequencyPenaltyLabel = `${strings.frequencyPenalty} <span id="${uiAttr(frequencyPenaltyValueId).html}" class="freq-penalty-value">0</span>`;
    const presencePenaltyLabel = `${strings.presencePenalty} <span id="${uiAttr(presencePenaltyValueId).html}" class="pres-penalty-value">0</span>`;
    const contextWindowLabel = `<label id="${uiIdAttr('chat-model-context-window-tokens-label')}" for="${uiIdAttr('chat-model-context-window-tokens-input')}" data-modal-localize="text">${strings.modelContextWindowTokensLabel}</label>`;
    const contextWindowHeader = inputArguments.includeContextWindowPresets ? `<div class="chat-config-field-header chat-config-field-header--context-window" data-modal-localize="text">${contextWindowLabel}${renderContextWindowPresetsMarkup(modalId).html}</div>` : contextWindowLabel;
    return `
  <div class="form-group setting-change-surface chat-config-span-2">
    <div class="form-row-split form-row-split--system-prompt">
      <div class="form-col-main">
        <label for="${uiIdAttr('system-prompt-input')}" data-modal-localize="text">${strings.systemPrompt}</label>
        <textarea
          id="${uiIdAttr('system-prompt-input')}"
          class="user-system-prompt-input form-input"
          placeholder="${strings.systemPromptPlaceholder}"
          rows="3"
          data-setting="prompts.user_system_prompt"
         data-modal-localize="placeholder"></textarea>
        <span class="chat-configuration-hint" data-modal-localize="text">${strings.systemPromptHint}</span>
      </div>

      ${inputArguments.includeSystemPromptLock === false ? '' : renderSystemPromptLockMarkup(modalId, strings)}

      <div class="form-col-secondary form-col-toggle">
        <label for="${uiIdAttr('soai-system-prompt-checkbox')}" data-modal-localize="text">${strings.soaiSystemPrompt}</label>
        ${buildParameterToggleMarkup({
            modalId,
            token: 'soai-system-prompt-checkbox',
            inputClassName: 'soai-system-prompt-checkbox',
            checked: true,
            trueLabel: strings.enabledLabel,
            falseLabel: strings.disabledLabel,
            inline: true,
            dataSetting: 'prompts.soai_system_prompt_enabled'
        })}
        <span class="chat-configuration-hint" data-modal-localize="text">${strings.soaiSystemPromptHint}</span>
      </div>
    </div>
  </div>

  <div id="${uiIdAttr('chat-model-context-window-tokens-group')}" class="form-group setting-change-surface" tabindex="-1" data-modal-localize="text">
    ${contextWindowHeader}
    <input
      type="number"
      id="${uiIdAttr('chat-model-context-window-tokens-input')}"
      class="form-input"
      min="1"
      step="1"
      data-param="context_window_tokens"
    >
    <span class="chat-configuration-hint" data-modal-localize="text">${strings.modelContextWindowTokensHint}</span>
  </div>

  <div class="form-group setting-change-surface" data-modal-localize="text">
    ${renderParameterFieldHeader({ modalId, labelFor: 'reasoning-effort-select', label: strings.reasoningEffort, token: 'reasoning-effort-send-toggle', flag: 'reasoning_effort_send_enabled', checked: false, strings })}
    ${renderStandardDropdownSelectControl(`<select id="${uiIdAttr('reasoning-effort-select')}" class="form-input" data-param="reasoning_effort" data-modal-localize="options">
      ${renderReasoningEffortOptionsMarkup(strings)}
    </select>`)}
    <span class="chat-configuration-hint" data-modal-localize="text">${strings.reasoningEffortHint}</span>
    <span id="${uiIdAttr('reasoning-effort-support-error')}" class="chat-configuration-hint" data-reasoning-effort-support-error role="alert" hidden></span>
  </div>

  <div class="form-group setting-change-surface" data-modal-localize="text">
    ${renderParameterFieldHeader({ modalId, labelFor: 'max-completion-tokens-input', label: strings.maxCompletionTokens, token: 'max-completion-tokens-send-toggle', flag: 'max_completion_tokens_send_enabled', checked: false, strings })}
    <input type="number" id="${uiIdAttr('max-completion-tokens-input')}" class="form-input" min="0" data-param="max_completion_tokens">
    <span class="chat-configuration-hint" data-modal-localize="text">${strings.maxCompletionTokensHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('agent-max-iterations-input')}" data-modal-localize="text">${strings.agentMaxIterations}</label>
    <input type="number" id="${uiIdAttr('agent-max-iterations-input')}" class="form-input" min="1" max="1000000000" step="1" required data-param="agent_max_iterations">
    <span class="chat-configuration-hint" data-modal-localize="text">${strings.agentMaxIterationsHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('temperature-slider')}" data-modal-localize="text">
      ${strings.temperature}
      <span id="${uiAttr(temperatureValueId).html}" class="temp-value">0.7</span>
    </label>
    <input type="range" id="${uiIdAttr('temperature-slider')}" class="temperature-slider ui-range" min="0" max="2" step="0.1" value="0.7" data-param="temperature" data-display="#${temperatureValueId}">
    <span class="chat-configuration-hint" data-modal-localize="text">${strings.temperatureHint}</span>
  </div>

  <div class="form-group setting-change-surface" data-modal-localize="text">
    ${renderParameterFieldHeader({ modalId, labelFor: 'top-p-slider', label: topPLabel, token: 'top-p-send-toggle', flag: 'top_p_send_enabled', checked: true, strings })}
    <input type="range" id="${uiIdAttr('top-p-slider')}" class="top-p-slider ui-range" min="0" max="1" step="0.01" value="1" data-param="top_p" data-display="#${topPValueId}">
    <span class="chat-configuration-hint" data-modal-localize="text">${strings.topPHint}</span>
  </div>

  <div class="form-group setting-change-surface" data-modal-localize="text">
    ${renderParameterFieldHeader({ modalId, labelFor: 'freq-penalty-slider', label: frequencyPenaltyLabel, token: 'frequency-penalty-send-toggle', flag: 'frequency_penalty_send_enabled', checked: true, strings })}
    <input type="range" id="${uiIdAttr('freq-penalty-slider')}" class="freq-penalty-slider ui-range" min="-2" max="2" step="0.1" value="0" data-param="frequency_penalty" data-display="#${frequencyPenaltyValueId}">
    <span class="chat-configuration-hint" data-modal-localize="text">${strings.frequencyPenaltyHint}</span>
  </div>

  <div class="form-group setting-change-surface" data-modal-localize="text">
    ${renderParameterFieldHeader({ modalId, labelFor: 'pres-penalty-slider', label: presencePenaltyLabel, token: 'presence-penalty-send-toggle', flag: 'presence_penalty_send_enabled', checked: true, strings })}
    <input type="range" id="${uiIdAttr('pres-penalty-slider')}" class="pres-penalty-slider ui-range" min="-2" max="2" step="0.1" value="0" data-param="presence_penalty" data-display="#${presencePenaltyValueId}">
    <span class="chat-configuration-hint" data-modal-localize="text">${strings.presencePenaltyHint}</span>
  </div>

  <div class="form-group setting-change-surface" data-modal-localize="text">
    ${renderParameterFieldHeader({ modalId, labelFor: 'stop-sequences-input', label: strings.stopSequences, token: 'stop-sequences-send-toggle', flag: 'stop_send_enabled', checked: false, strings })}
    <input type="text" id="${uiIdAttr('stop-sequences-input')}" class="form-input" data-param="stop">
    <span class="chat-configuration-hint" data-modal-localize="text">${strings.stopSequencesHint}</span>
  </div>

  <div class="form-group setting-change-surface" data-modal-localize="text">
    ${renderParameterFieldHeader({ modalId, labelFor: 'top-logprobs-input', label: strings.topLogprobs, token: 'logprobs-send-toggle', flag: 'logprobs_send_enabled', checked: false, strings })}
    <input type="number" id="${uiIdAttr('top-logprobs-input')}" class="form-input" min="0" max="5" data-param="top_logprobs">
    <span class="chat-configuration-hint" data-modal-localize="text">${strings.topLogprobsHint}</span>
  </div>
`;
};

export { renderChatParameterControlsMarkup };
