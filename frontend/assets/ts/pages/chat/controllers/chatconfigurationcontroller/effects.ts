/* SoAI - Chat configuration controller effects [frontend/assets/ts/pages/chat/controllers/chatconfigurationcontroller/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { cloneChatParameters } from '@core/chat/parameters/chatParameterDefaults.ts';
import { CHAT_PARAMETER_WIRE_KEYS, LOCAL_ONLY_CHAT_PARAMETER_KEYS, STORED_CHAT_PARAMETER_KEYS } from '@core/chat/parameters/chatParameterKeySets.ts';
import { dom } from '@core/dom/dom.ts';
import { FieldStateTracker } from '@core/forms/fieldStateTracker.ts';
import { isNumber } from '@core/typeGuards.ts';
import { isJsonValue, type JsonValue } from '@core/types/jsonValues.ts';
import type { ChatParameters } from '@features/chat/public.ts';
import { areParameterSetsEqual, areParameterValuesEqual } from '@pages/chat/controllers/chatconfigurationcontroller/configurationChangeTracking.ts';
import type { ConfigurationControllerHost, ConfigurationControllerStateAccess } from '@pages/chat/controllers/chatconfigurationcontroller/types.ts';

type ChatParameterKey = Extract<keyof ChatParameters, string>;

const INPUT_ACTION_PARAMETER_KEYS = Object.freeze(['inputActionVoiceEnabled', 'inputActionCallEnabled', 'inputActionFileUploadEnabled', 'inputActionCameraEnabled', 'inputActionPromptsEnabled', 'inputActionTokenCounterEnabled', 'inputActionNewConversationEnabled', 'inputActionCharacterMapEnabled', 'inputActionSketchEnabled', 'inputActionFindEnabled', 'inputActionMobileAuxiliaryAction'] satisfies ReadonlyArray<ChatParameterKey>);

const SEND_HOTKEY_PARAMETER_KEYS = Object.freeze(['ctrlEnterSendEnabled'] satisfies ReadonlyArray<ChatParameterKey>);

const BACKEND_OWNED_NO_CONVERSATION_PARAMETER_KEYS = Object.freeze(['new_conversation_inherit_last_settings', 'tools_enabled', 'tool_approval_required'] satisfies ReadonlyArray<ChatParameterKey>);
const BACKEND_DEFAULT_PARAMETER_KEYS = Object.freeze([...STORED_CHAT_PARAMETER_KEYS, ...BACKEND_OWNED_NO_CONVERSATION_PARAMETER_KEYS]);

const requireComparableJsonValue = <T>(value: T): JsonValue | undefined => {
    if (value === undefined) {
        return undefined;
    }
    if (isJsonValue(value)) {
        return value;
    }
    throw new TypeError('Chat configuration change tracking value must be JSON-compatible');
};

const hasMatchingKey = (candidate: string, keys: ReadonlyArray<string>): boolean => {
    return keys.some((key) => key === candidate);
};

const isInputActionParameter = (parameter: string): parameter is (typeof INPUT_ACTION_PARAMETER_KEYS)[number] => {
    return hasMatchingKey(parameter, INPUT_ACTION_PARAMETER_KEYS);
};

const isBackendOwnedNoConversationParameter = (parameter: string): boolean => {
    return hasMatchingKey(parameter, BACKEND_DEFAULT_PARAMETER_KEYS);
};

const haveParametersChanged = (previousParameters: ChatParameters, nextParameters: ChatParameters, keys: ReadonlyArray<ChatParameterKey>): boolean => {
    return keys.some((key) => !areParameterValuesEqual(key, previousParameters[key], nextParameters[key]));
};

interface ConfigurationEditSession {
    editingParameters: ChatParameters;
    parameterEditBaseline: ChatParameters;
    pendingParameterChanges: boolean;
    parameterChangeTracker: FieldStateTracker;
}

interface CommitConfigurationEditStateOptions {
    stateAccess: ConfigurationControllerStateAccess;
    host: Pick<ConfigurationControllerHost, 'applyTextZoom'>;
    editingParameters: ChatParameters | null;
    parameterEditBaseline: ChatParameters | null;
}

interface CommitConfigurationEditStateResult {
    committed: boolean;
    backendDefaultsChanged: boolean;
    richTextChanged: boolean;
    senderLabelChanged: boolean;
    inputActionsChanged: boolean;
    sendHotkeyChanged: boolean;
    toolsEnabledChanged: boolean;
    toolApprovalRequiredChanged: boolean;
    conversationListFiltersChanged: boolean;
    activityDurationDisplayChanged: boolean;
}

const createConfigurationEditSession = (host: Pick<ConfigurationControllerHost, 'pageDom' | 'root'>, stateAccess: ConfigurationControllerStateAccess): ConfigurationEditSession => {
    const parameterEditBaseline = cloneChatParameters(stateAccess.getParameters());
    parameterEditBaseline.textZoom = stateAccess.getTextZoom();
    const editingParameters = cloneChatParameters(parameterEditBaseline);
    const resolveParameterElements = (key: string): Element[] => dom.resolveAll(`[data-param="${CHAT_PARAMETER_WIRE_KEYS[key] ?? key}"]`, host.root);
    const parameterChangeTracker = new FieldStateTracker({
        getElement: (key: string) => resolveParameterElements(key)[0] ?? null,
        getElements: resolveParameterElements,
        getCurrentValue: (key: string) => editingParameters[key],
        getOriginalValue: (key: string) => parameterEditBaseline[key],
        comparator: (current, original, key: string) => areParameterValuesEqual(key, requireComparableJsonValue(current), requireComparableJsonValue(original))
    });
    return {
        editingParameters,
        parameterEditBaseline,
        pendingParameterChanges: false,
        parameterChangeTracker
    };
};

const commitConfigurationEditState = ({ stateAccess, host, editingParameters, parameterEditBaseline }: CommitConfigurationEditStateOptions): CommitConfigurationEditStateResult => {
    if (!editingParameters) {
        return {
            committed: false,
            backendDefaultsChanged: false,
            richTextChanged: false,
            senderLabelChanged: false,
            inputActionsChanged: false,
            sendHotkeyChanged: false,
            toolsEnabledChanged: false,
            toolApprovalRequiredChanged: false,
            conversationListFiltersChanged: false,
            activityDurationDisplayChanged: false
        };
    }

    const previousParameters = stateAccess.getParameters();
    const previousPresentationParameters = parameterEditBaseline ?? previousParameters;
    const previousRichText = parameterEditBaseline ? parameterEditBaseline.richTextEnabled !== false : stateAccess.isRichTextEnabled();
    const previousHideRealModel = previousPresentationParameters.hideRealModel === true;
    const previousHideAutomationRuns = previousPresentationParameters.hideAutomationRuns === true;
    const previousHideMessagingConversations = previousPresentationParameters.hideMessagingConversations === true;
    const previousToolsEnabled = previousParameters.toolsEnabled === true;
    const previousToolApprovalRequired = previousParameters.toolApprovalRequired === true;
    const previousNewConversationInheritLastSettings = previousParameters.newConversationInheritLastSettings === true;
    const previousShowActivityElapsedTime = previousPresentationParameters.showActivityElapsedTime !== false;

    const editedTextZoom = editingParameters.textZoom;
    if (isNumber(editedTextZoom) && editedTextZoom !== stateAccess.getTextZoom()) {
        stateAccess.setTextZoom(editedTextZoom);
        const textZoomController = stateAccess.getTextZoomController();
        if (textZoomController) {
            textZoomController.currentZoom = editedTextZoom;
            textZoomController.persistZoom(editedTextZoom);
        }
        host.applyTextZoom();
    }

    const committedParameters = cloneChatParameters(editingParameters);
    if (parameterEditBaseline) {
        for (const key of LOCAL_ONLY_CHAT_PARAMETER_KEYS) {
            if (areParameterValuesEqual(key, editingParameters[key], parameterEditBaseline[key])) committedParameters[key] = previousParameters[key];
        }
    }
    stateAccess.setParameters(committedParameters);

    const nextParameters = stateAccess.getParameters();
    const nextHideRealModel = nextParameters.hideRealModel === true;
    const nextHideAutomationRuns = nextParameters.hideAutomationRuns === true;
    const nextHideMessagingConversations = nextParameters.hideMessagingConversations === true;
    const nextToolsEnabled = nextParameters.toolsEnabled === true;
    const nextToolApprovalRequired = nextParameters.toolApprovalRequired === true;
    const nextNewConversationInheritLastSettings = nextParameters.newConversationInheritLastSettings === true;
    const nextShowActivityElapsedTime = nextParameters.showActivityElapsedTime !== false;

    return {
        committed: true,
        backendDefaultsChanged: previousToolsEnabled !== nextToolsEnabled || previousToolApprovalRequired !== nextToolApprovalRequired || previousNewConversationInheritLastSettings !== nextNewConversationInheritLastSettings || haveParametersChanged(previousParameters, nextParameters, STORED_CHAT_PARAMETER_KEYS),
        richTextChanged: previousRichText !== stateAccess.isRichTextEnabled(),
        senderLabelChanged: previousHideRealModel !== nextHideRealModel,
        inputActionsChanged: haveParametersChanged(previousPresentationParameters, nextParameters, INPUT_ACTION_PARAMETER_KEYS),
        sendHotkeyChanged: haveParametersChanged(previousPresentationParameters, nextParameters, SEND_HOTKEY_PARAMETER_KEYS),
        toolsEnabledChanged: previousToolsEnabled !== nextToolsEnabled,
        toolApprovalRequiredChanged: previousToolApprovalRequired !== nextToolApprovalRequired,
        conversationListFiltersChanged: previousHideAutomationRuns !== nextHideAutomationRuns || previousHideMessagingConversations !== nextHideMessagingConversations,
        activityDurationDisplayChanged: previousShowActivityElapsedTime !== nextShowActivityElapsedTime
    };
};

const hasPendingConfigurationParameterChanges = (editingParameters: ChatParameters | null, parameterEditBaseline: ChatParameters | null): boolean => {
    return !areParameterSetsEqual(editingParameters, parameterEditBaseline);
};

export { commitConfigurationEditState, createConfigurationEditSession, hasPendingConfigurationParameterChanges };
export { isBackendOwnedNoConversationParameter, isInputActionParameter };
export type { CommitConfigurationEditStateOptions, CommitConfigurationEditStateResult, ConfigurationEditSession };
