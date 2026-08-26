/* SoAI - Automation page modal actions [frontend/assets/ts/pages/automation/controllers/actiondispatch/modalActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AutomationPageActionDispatcherHost } from '@pages/automation/controllers/actiondispatch/AutomationPageActionDispatcherHost.ts';

const handleEnterEditMode = (host: AutomationPageActionDispatcherHost): void => {
    const editor = host.controllers.getEditor();
    if (!editor) {
        throw new Error('Automation editor is not initialized');
    }
    editor.enterEditMode();
};

const handleOpenCreate = (host: AutomationPageActionDispatcherHost): void => {
    host.controllers.run('automation:openCreateModal', async () => {
        const editor = host.controllers.getEditor();
        if (!editor) {
            throw new Error('Automation editor is not initialized');
        }
        await editor.openCreateForSelectedDate();
    });
};

const handleOpenCalendarSettings = (host: AutomationPageActionDispatcherHost): void => {
    const calendarSettings = host.controllers.getCalendarSettings();
    if (!calendarSettings) {
        throw new Error('Automation calendar settings controller is not initialized');
    }
    calendarSettings.open();
};

const handleAddTurn = (host: AutomationPageActionDispatcherHost): void => {
    const editor = host.controllers.getEditor();
    if (!editor) {
        throw new Error('Automation editor is not initialized');
    }
    editor.addTurn();
};

const handleRemoveTurn = (host: AutomationPageActionDispatcherHost, element: HTMLElement): void => {
    const editor = host.controllers.getEditor();
    if (!editor) {
        throw new Error('Automation editor is not initialized');
    }
    editor.removeTurn(element.dataset['turnIndex'] ?? null);
};

const handleOpenWorkspaceModal = (host: AutomationPageActionDispatcherHost): void => {
    host.controllers.run('automation:openWorkspaceModal', async () => {
        const editor = host.controllers.getEditor();
        if (!editor) {
            throw new Error('Automation editor is not initialized');
        }
        await editor.openWorkspaceModal();
    });
};

const handleOpenParametersModal = (host: AutomationPageActionDispatcherHost): void => {
    host.controllers.run('automation:openParametersModal', async () => {
        const editor = host.controllers.getEditor();
        if (!editor) {
            throw new Error('Automation editor is not initialized');
        }
        await editor.openParametersModal();
    });
};

const handleSaveAutomation = (host: AutomationPageActionDispatcherHost): void => {
    host.controllers.run('automation:saveAutomation', async () => {
        const editor = host.controllers.getEditor();
        if (!editor) {
            throw new Error('Automation editor is not initialized');
        }
        await editor.saveFromModal();
    });
};

const handleSaveCalendarSettings = (host: AutomationPageActionDispatcherHost): void => {
    host.controllers.run('automation:saveCalendarSettings', async () => {
        const calendarSettings = host.controllers.getCalendarSettings();
        if (!calendarSettings) {
            throw new Error('Automation calendar settings controller is not initialized');
        }
        await calendarSettings.save();
    });
};

export { handleAddTurn, handleEnterEditMode, handleOpenCalendarSettings, handleOpenCreate, handleOpenParametersModal, handleOpenWorkspaceModal, handleRemoveTurn, handleSaveAutomation, handleSaveCalendarSettings };
