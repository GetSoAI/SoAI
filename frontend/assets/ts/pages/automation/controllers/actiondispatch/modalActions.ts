/* SoAI - Automation page modal actions [frontend/assets/ts/pages/automation/controllers/actiondispatch/modalActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AutomationCalendarSettingsController } from '@pages/automation/controllers/AutomationCalendarSettingsController.ts';
import type { AutomationPageActionDispatcherHost } from '@pages/automation/controllers/actiondispatch/AutomationPageActionDispatcherHost.ts';
import { requireEditor } from '@pages/automation/controllers/automationCrudActions.ts';

const requireCalendarSettings = (host: AutomationPageActionDispatcherHost): AutomationCalendarSettingsController => {
    const calendarSettings = host.controllers.getCalendarSettings();
    if (!calendarSettings) {
        throw new Error('Automation calendar settings controller is not initialized');
    }
    return calendarSettings;
};

const handleEnterEditMode = (host: AutomationPageActionDispatcherHost): void => {
    requireEditor(host).enterEditMode();
};

const handleOpenCreate = (host: AutomationPageActionDispatcherHost): void => {
    host.controllers.run('automation:openCreateModal', async () => requireEditor(host).openCreateForSelectedDate());
};

const handleOpenCalendarSettings = (host: AutomationPageActionDispatcherHost): void => {
    requireCalendarSettings(host).open();
};

const handleAddTurn = (host: AutomationPageActionDispatcherHost): void => {
    requireEditor(host).addTurn();
};

const handleRemoveTurn = (host: AutomationPageActionDispatcherHost, element: HTMLElement): void => {
    requireEditor(host).removeTurn(element.dataset['turnIndex'] ?? null);
};

const handleOpenWorkspaceModal = (host: AutomationPageActionDispatcherHost): void => {
    host.controllers.run('automation:openWorkspaceModal', async () => requireEditor(host).openWorkspaceModal());
};

const handleOpenParametersModal = (host: AutomationPageActionDispatcherHost): void => {
    host.controllers.run('automation:openParametersModal', async () => requireEditor(host).openParametersModal());
};

const handleSaveAutomation = (host: AutomationPageActionDispatcherHost): void => {
    host.controllers.run('automation:saveAutomation', async () => requireEditor(host).saveFromModal());
};

const handleRetryEditorPrerequisites = (host: AutomationPageActionDispatcherHost): void => {
    host.controllers.run('automation:retryEditorPrerequisites', async () => requireEditor(host).retryPrerequisites());
};

const handleKeepConflictChanges = (host: AutomationPageActionDispatcherHost): void => {
    requireEditor(host).keepChangesAfterConflict();
};

const handleLoadLatestAfterConflict = (host: AutomationPageActionDispatcherHost): void => {
    requireEditor(host).loadLatestAfterConflict();
};

const handleSaveCalendarSettings = (host: AutomationPageActionDispatcherHost): void => {
    host.controllers.run('automation:saveCalendarSettings', async () => requireCalendarSettings(host).save());
};

export { handleAddTurn, handleEnterEditMode, handleKeepConflictChanges, handleLoadLatestAfterConflict, handleOpenCalendarSettings, handleOpenCreate, handleOpenParametersModal, handleOpenWorkspaceModal, handleRemoveTurn, handleRetryEditorPrerequisites, handleSaveAutomation, handleSaveCalendarSettings };
