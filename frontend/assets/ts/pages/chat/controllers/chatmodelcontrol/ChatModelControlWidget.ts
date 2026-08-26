/* SoAI - Markup builder for the unified chat model control surfaces [frontend/assets/ts/pages/chat/controllers/chatmodelcontrol/ChatModelControlWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { resolveModelTypeLabel } from '@core/models/modelTypeLabel.ts';
import type { SanitizerApi } from '@core/pagecontext/public.ts';
import { renderLabelAttributes, toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import type { ModelData } from '@core/types/modelTypes.ts';
import { getBadgeColorClass } from '@core/ui/badgeColors.ts';
import { renderDropdownChevron } from '@core/ui/dropdown/chevron.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { CHAT_COMPARISON_MAX_EFFECTIVE_MODELS } from '@core/chat/comparisonModels.ts';
import { renderAuthorityLockMarkupAttributes, resolveAuthorityLockedControlLabels, type ConversationAuthorityControlLabels, type ConversationAuthorityLock } from '@core/chat/conversationAuthorityLock.ts';
import { normalizeChatModelId, type EffectiveModels } from '@pages/chat/controllers/chatmodelcontrol/chatModelControlStateManager.ts';
import { buildChatModelMenuOptionGroups, type ChatModelMenuOption, type ChatModelMenuOptionGroup } from '@pages/chat/controllers/chatmodelcontrol/ChatModelControlMenuOptionsWidget.ts';
import { renderChatModelMenuEmpty, renderChatModelMenuSearch } from '@pages/chat/controllers/chatmodelcontrol/ChatModelControlMenuSearchWidget.ts';

export const CHAT_MODEL_CONTROL_ACTION_TOGGLE_MENU = 'chat:model-control-toggle-menu';
export const CHAT_MODEL_CONTROL_ACTION_SELECT_MODEL = 'chat:model-control-select-model';
export const CHAT_MODEL_CONTROL_ACTION_ADD_MODEL = 'chat:model-control-add-model';
export const CHAT_MODEL_CONTROL_ACTION_REMOVE_MODEL = 'chat:model-control-remove-model';

type ModelControlScope = 'sidebar' | 'header' | 'empty-state' | 'configuration';

type ModelControlMenuOpenState = { scope: ModelControlScope; slotIndex: number } | null;

type ModelControlRenderArguments = {
    scope: ModelControlScope;
    sanitizer: SanitizerApi;
    getCachedIcon: (name: IconName, options?: IconOptions) => TrustedHtml;
    models: ModelData[];
    modelIndex: Map<string, ModelData>;
    modelStreamHasPayload: boolean;
    hasSelectableModels: boolean;
    effectiveModels: EffectiveModels;
    isExecuting: boolean;
    authorityLock: ConversationAuthorityLock | null;
    openMenu: ModelControlMenuOpenState;
    menuSearchQuery: string;
};

type ModelControlAvailability = Pick<ModelControlRenderArguments, 'isExecuting' | 'authorityLock'>;

const renderModelControlStateAttributes = (availability: ModelControlAvailability, nativeDisabled: boolean): string => {
    if (availability.authorityLock !== null) {
        return renderAuthorityLockMarkupAttributes(availability.authorityLock);
    }
    if (availability.isExecuting) {
        return 'aria-disabled="true" data-toggle-disabled="true"';
    }
    return nativeDisabled ? 'disabled' : '';
};

const resolveModelControlLabels = (availability: ModelControlAvailability, actionLabel: string): ConversationAuthorityControlLabels => resolveAuthorityLockedControlLabels(availability.authorityLock, actionLabel, availability.isExecuting ? i18n.t('chat.modelControl.executionDisabledTooltip') : actionLabel);

const resolveEffectiveModelIds = (effectiveModels: EffectiveModels): string[] => {
    const primary = normalizeChatModelId(effectiveModels.primary);
    const comparison = effectiveModels.comparison.map((match) => normalizeChatModelId(match)).filter((match): match is string => match !== null);
    return primary ? [primary, ...comparison] : [...comparison];
};

const resolveSelectedModelIdForSlot = (effectiveModels: EffectiveModels, slotIndex: number): string | null => {
    if (slotIndex === 0) {
        return normalizeChatModelId(effectiveModels.primary);
    }
    const comparisonIndex = slotIndex - 1;
    const candidate = effectiveModels.comparison[comparisonIndex] ?? null;
    return normalizeChatModelId(candidate);
};

const resolveIsMultiModel = (effectiveModels: EffectiveModels): boolean => {
    const ids = resolveEffectiveModelIds(effectiveModels);
    return ids.length > 1;
};

const buildMenuMarkup = (inputArguments: ModelControlRenderArguments & { slotIndex: number; selectedModelId: string | null }): string => {
    const stringValue = inputArguments.sanitizer;
    const isOpen = inputArguments.openMenu !== null && inputArguments.openMenu.scope === inputArguments.scope && inputArguments.openMenu.slotIndex === inputArguments.slotIndex;
    const menuClass = `chat-model-menu${isOpen ? ' is-open' : ''}`;

    const effectiveIds = resolveEffectiveModelIds(inputArguments.effectiveModels);
    const hasRoomForAnotherModel = effectiveIds.length < CHAT_COMPARISON_MAX_EFFECTIVE_MODELS;
    const canAddModel = !inputArguments.hasSelectableModels || (hasRoomForAnotherModel && normalizeChatModelId(inputArguments.effectiveModels.primary) !== null);
    const compareLabel = inputArguments.hasSelectableModels ? i18n.t('chat.modelControl.compareModels') : i18n.t('models.actions.addModel');
    const compareIcon = inputArguments.getCachedIcon('add', { size: 12, strokeWidth: 2 });

    const addDisabled = inputArguments.hasSelectableModels ? !canAddModel : false;

    const groups = buildChatModelMenuOptionGroups({ models: inputArguments.models, selectedModelId: inputArguments.selectedModelId });
    const selectedModelId = normalizeChatModelId(inputArguments.selectedModelId);
    const hasSelectedInList = selectedModelId ? inputArguments.models.some((model) => model.id === selectedModelId) : false;

    const renderOption = (option: ChatModelMenuOption): string => {
        const stateAttrs = renderModelControlStateAttributes(inputArguments, option.disabled);
        const currentAttr = option.selected ? `aria-current="true"` : '';
        return `<button type="button" class="chat-model-menu-option" data-action="${CHAT_MODEL_CONTROL_ACTION_SELECT_MODEL}" data-model-id="${stringValue.attribute(option.id)}" data-slot-index="${String(inputArguments.slotIndex)}" data-search-index="${stringValue.attribute(option.searchIndex)}" ${renderLabelAttributes(resolveModelControlLabels(inputArguments, option.label))} ${currentAttr} ${stateAttrs}>${stringValue.html(option.label)}</button>`;
    };

    const renderGroup = (group: ChatModelMenuOptionGroup): string => {
        const header = group.label ? `<div class="chat-model-menu-group-label">${stringValue.html(group.label)}</div>` : '';
        return `<div class="chat-model-menu-group">${header}${group.options.map(renderOption).join('')}</div>`;
    };

    const actionsMarkup = (() => {
        if (effectiveIds.length > 1) {
            const slotLabel = i18n.t('chat.modelControl.slotLabel', { index: inputArguments.slotIndex + 1 });
            const model = inputArguments.selectedModelId ? (inputArguments.modelIndex.get(inputArguments.selectedModelId) ?? null) : null;
            const modeLabel = resolveModelTypeLabel(model);
            const badgeClass = getBadgeColorClass(inputArguments.selectedModelId ?? String(inputArguments.slotIndex + 1));
            const modeMarkup = modeLabel ? `<span class="chat-model-menu-slot-label-right">${stringValue.html(modeLabel)}</span>` : '';
            return `<div class="chat-model-menu-actions">` + `<span class="chat-model-menu-slot-label ui-model-type-badge ${badgeClass}">` + `<span class="chat-model-menu-slot-label-left">${stringValue.html(slotLabel)}</span>` + `${modeMarkup}` + `</span>` + `</div>`;
        }
        return `<div class="chat-model-menu-actions">` + `<button type="button" class="chat-model-menu-action ui-button ui-button--sm ui-variant-accent" data-action="${CHAT_MODEL_CONTROL_ACTION_ADD_MODEL}" ${renderLabelAttributes(resolveModelControlLabels(inputArguments, compareLabel))} ${renderModelControlStateAttributes(inputArguments, addDisabled)}>` + `<span class="ui-icon chat-action-icon" aria-hidden="true">${compareIcon}</span>` + `<span class="chat-action-label">${stringValue.html(compareLabel)}</span>` + `</button>` + `</div>`;
    })();

    const preservedMarkup = (() => {
        if (!inputArguments.modelStreamHasPayload || !selectedModelId || hasSelectedInList) {
            return '';
        }
        const missingLabel = i18n.t('chat.modelControl.missingModel', { model: selectedModelId });
        return `<div class="chat-model-menu-preserved">` + `<button type="button" class="chat-model-menu-option" aria-current="true" disabled data-search-index="${stringValue.attribute(selectedModelId)}" ${renderLabelAttributes(missingLabel)}>${stringValue.html(missingLabel)}</button>` + `</div>`;
    })();

    const searchMarkup = renderChatModelMenuSearch({
        sanitizer: stringValue,
        getCachedIcon: inputArguments.getCachedIcon,
        query: inputArguments.menuSearchQuery
    });
    const emptyMarkup = renderChatModelMenuEmpty({ sanitizer: stringValue, hidden: true });

    return `<div class="${menuClass}" role="menu" aria-hidden="${isOpen ? 'false' : 'true'}">${searchMarkup}${actionsMarkup}${preservedMarkup}${groups.map(renderGroup).join('')}${emptyMarkup}</div>`;
};

const resolveMissingSuffix = (inputArguments: { modelStreamHasPayload: boolean; modelIndex: Map<string, ModelData>; modelId: string | null }): string => {
    if (!inputArguments.modelStreamHasPayload) {
        return '';
    }
    const modelId = normalizeChatModelId(inputArguments.modelId);
    if (!modelId) {
        return '';
    }
    if (inputArguments.modelIndex.has(modelId)) {
        return '';
    }
    return i18n.t('chat.modelControl.missingSuffix');
};

const renderSingleModelControls = (inputArguments: ModelControlRenderArguments): string => {
    const stringValue = inputArguments.sanitizer;
    const isMenuOpen = inputArguments.openMenu !== null && inputArguments.openMenu.scope === inputArguments.scope && inputArguments.openMenu.slotIndex === 0;
    const selectedModelId = resolveSelectedModelIdForSlot(inputArguments.effectiveModels, 0);
    const missingSuffix = resolveMissingSuffix({ modelStreamHasPayload: inputArguments.modelStreamHasPayload, modelIndex: inputArguments.modelIndex, modelId: selectedModelId });
    const modelLabel = selectedModelId ? `${inputArguments.modelIndex.get(selectedModelId)?.name ?? selectedModelId}${missingSuffix ? ` ${missingSuffix}` : ''}` : '';
    const label = selectedModelId ? i18n.t('chat.modelControl.configureModel', { model: modelLabel }) : i18n.t('chat.sidebar.selectModel');
    const chevron = renderDropdownChevron(inputArguments.getCachedIcon, 'chat-model-control-primary-chevron');

    const primaryText = selectedModelId ? stringValue.html(modelLabel) : stringValue.html(i18n.t('chat.sidebar.selectModel'));
    const primaryButton = `<button type="button" class="chat-model-control-primary ui-button${isMenuOpen ? ' is-open' : ''}" data-action="${CHAT_MODEL_CONTROL_ACTION_TOGGLE_MENU}" data-slot-index="0" ${renderLabelAttributes(resolveModelControlLabels(inputArguments, label))} ${renderModelControlStateAttributes(inputArguments, false)}>` + `<span class="chat-model-control-primary-text">${primaryText}</span>` + `${chevron}` + `</button>`;

    const menu = isMenuOpen
        ? buildMenuMarkup({
              ...inputArguments,
              slotIndex: 0,
              selectedModelId
          })
        : '';

    return `<div class="chat-model-control chat-model-control--single" data-scope="${inputArguments.scope}">${primaryButton}${menu}</div>`;
};

const renderMultiModelControls = (inputArguments: ModelControlRenderArguments): string => {
    const effective = resolveEffectiveModelIds(inputArguments.effectiveModels);
    const openMenu = inputArguments.openMenu;
    let openSlotIndex = -1;
    if (openMenu !== null && openMenu.scope === inputArguments.scope) {
        openSlotIndex = openMenu.slotIndex;
    }
    const isMenuOpenForScope = openSlotIndex >= 0;
    const slotIndex = openSlotIndex >= 0 && openSlotIndex < effective.length ? openSlotIndex : 0;
    const openSlotIndexNormalized = isMenuOpenForScope ? slotIndex : -1;

    const canAddModel = normalizeChatModelId(inputArguments.effectiveModels.primary) !== null;
    const hasRoomForAnotherModel = effective.length < CHAT_COMPARISON_MAX_EFFECTIVE_MODELS;
    const addDisabled = !canAddModel || !hasRoomForAnotherModel;
    const addLabel = i18n.t('models.actions.addModel');
    const addIcon = inputArguments.getCachedIcon('add', { size: 18, strokeWidth: 2 }).html;

    const slotButtons = Array.from({ length: CHAT_COMPARISON_MAX_EFFECTIVE_MODELS }, (_unusedValue, index) => {
        const modelId = effective[index] ?? null;
        if (!modelId) {
            const button = `<button type="button" class="chat-model-slot chat-model-slot--placeholder ui-icon-button ui-variant-accent" data-action="${CHAT_MODEL_CONTROL_ACTION_ADD_MODEL}" data-slot-index="${String(index)}" ${renderLabelAttributes(resolveModelControlLabels(inputArguments, addLabel))} ${renderModelControlStateAttributes(inputArguments, addDisabled)}>` + `${addIcon}` + `</button>`;
            return `<div class="chat-model-slot-wrap chat-model-slot-wrap--placeholder">${button}</div>`;
        }

        const missingSuffix = resolveMissingSuffix({ modelStreamHasPayload: inputArguments.modelStreamHasPayload, modelIndex: inputArguments.modelIndex, modelId });
        const modelLabel = `${inputArguments.modelIndex.get(modelId)?.name ?? modelId}${missingSuffix ? ` ${missingSuffix}` : ''}`;
        const label = i18n.t('chat.modelControl.configureSlot', { index: index + 1, model: modelLabel });
        const isOpen = openSlotIndexNormalized === index;
        const cube = inputArguments.getCachedIcon('model-default', { size: 20, strokeWidth: 1.5 }).html;
        const removeLabel = i18n.t('chat.attachments.removeTooltip');
        const removeIcon = inputArguments.getCachedIcon('close', { size: 12, strokeWidth: 2.2 }).html;
        const slotButton = `<button type="button" class="chat-model-slot ui-icon-button${isOpen ? ' is-open' : ''}" data-action="${CHAT_MODEL_CONTROL_ACTION_TOGGLE_MENU}" data-slot-index="${String(index)}" ${renderLabelAttributes(resolveModelControlLabels(inputArguments, label))} ${renderModelControlStateAttributes(inputArguments, false)}>` + `${cube}` + `</button>`;
        const removeButton = `<button type="button" class="chat-model-slot-remove ui-corner-badge ui-corner-badge--danger" data-action="${CHAT_MODEL_CONTROL_ACTION_REMOVE_MODEL}" data-slot-index="${String(index)}" ${renderLabelAttributes(resolveModelControlLabels(inputArguments, removeLabel))} ${renderModelControlStateAttributes(inputArguments, false)}>` + `${removeIcon}` + `</button>`;
        return `<div class="chat-model-slot-wrap">${slotButton}${removeButton}</div>`;
    }).join('');

    const selectedModelId = resolveSelectedModelIdForSlot(inputArguments.effectiveModels, slotIndex);

    const menuOpenState: ModelControlMenuOpenState = isMenuOpenForScope ? { scope: inputArguments.scope, slotIndex } : null;
    const menu = isMenuOpenForScope
        ? buildMenuMarkup({
              ...inputArguments,
              openMenu: menuOpenState,
              slotIndex,
              selectedModelId
          })
        : '';

    return `<div class="chat-model-control chat-model-control--multi" data-scope="${inputArguments.scope}"><div class="chat-model-slots">${slotButtons}</div>${menu}</div>`;
};

export const renderChatModelControlMarkup = (inputArguments: ModelControlRenderArguments): TrustedHtml => {
    if (resolveIsMultiModel(inputArguments.effectiveModels)) {
        return toTrustedUiHtml(renderMultiModelControls(inputArguments));
    }
    return toTrustedUiHtml(renderSingleModelControls(inputArguments));
};

const isChatModelControlAction = (action: string | undefined): boolean => {
    return action === CHAT_MODEL_CONTROL_ACTION_TOGGLE_MENU || action === CHAT_MODEL_CONTROL_ACTION_SELECT_MODEL || action === CHAT_MODEL_CONTROL_ACTION_ADD_MODEL || action === CHAT_MODEL_CONTROL_ACTION_REMOVE_MODEL;
};

export { isChatModelControlAction };
export type { ModelControlScope, ModelControlMenuOpenState, EffectiveModels };
