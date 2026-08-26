/* SoAI - Chat page configuration edit session state manager [frontend/assets/ts/pages/chat/controllers/chatconfigurationcontroller/ConfigurationEditSessionStateManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatParameters } from '@features/chat/public.ts';
import type { ConfigurationEditSession } from '@pages/chat/controllers/chatconfigurationcontroller/effects.ts';
import type { FieldStateTracker } from '@core/forms/fieldStateTracker.ts';

type EditableConfigurationSessionState = {
    editingParameters: ChatParameters | null;
    parameterEditBaseline: ChatParameters | null;
    pendingParameterChanges: boolean;
};

const applyConfigurationEditSessionState = (target: EditableConfigurationSessionState, session: ConfigurationEditSession, setParameterChangeTracker: (tracker: FieldStateTracker | null) => void): void => {
    target.parameterEditBaseline = session.parameterEditBaseline;
    target.editingParameters = session.editingParameters;
    target.pendingParameterChanges = session.pendingParameterChanges;
    setParameterChangeTracker(session.parameterChangeTracker);
};

const clearConfigurationEditSessionState = (target: EditableConfigurationSessionState, setParameterChangeTracker: (tracker: FieldStateTracker | null) => void): void => {
    target.editingParameters = null;
    target.parameterEditBaseline = null;
    target.pendingParameterChanges = false;
    setParameterChangeTracker(null);
};

const ConfigurationEditSessionStateManager = {
    applyConfigurationEditSessionState,
    clearConfigurationEditSessionState
};

export { ConfigurationEditSessionStateManager };
export type { EditableConfigurationSessionState };
