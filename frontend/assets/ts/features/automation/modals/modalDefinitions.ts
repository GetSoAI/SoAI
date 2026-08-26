/* SoAI - Automation modal definitions registered by app bootstrap [frontend/assets/ts/features/automation/modals/modalDefinitions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { MODAL_HEADER_CLOSE_SELECTOR } from '@core/modals/headerButtons.ts';
import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import type { ModalOpenOptions } from '@core/modals/types.ts';
import { createModalElementFromMarkup } from '@core/modals/scaffoldDom.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { AUTOMATION_CALENDAR_SETTINGS_MODAL_ID, AUTOMATION_CONFIGURATION_MODAL_ID, AUTOMATION_OCCURRENCE_MODAL_ID, AUTOMATION_PARAMETERS_MODAL_ID } from '@features/automation/modals/constants.ts';
import { renderAutomationCalendarSettingsModalMarkup } from '@features/automation/modals/markup/calendarSettingsModalMarkup.ts';
import { renderAutomationConfigurationModalMarkup } from '@features/automation/modals/markup/configurationModalMarkup.ts';
import { renderAutomationOccurrenceModalMarkup } from '@features/automation/modals/markup/occurrenceModalMarkup.ts';
import { renderAutomationParametersModalMarkup } from '@features/automation/modals/markup/parametersModalMarkup.ts';

const automationConfigurationModalDefinition: ModalDefinition = Object.freeze({
    id: AUTOMATION_CONFIGURATION_MODAL_ID,
    layout: 'lg',
    initialFocusSelector: modalUiSelector(AUTOMATION_CONFIGURATION_MODAL_ID, 'title-input'),
    createElement: (_options: ModalOpenOptions): HTMLElement => createModalElementFromMarkup(AUTOMATION_CONFIGURATION_MODAL_ID, renderAutomationConfigurationModalMarkup())
});

const automationCalendarSettingsModalDefinition: ModalDefinition = Object.freeze({
    id: AUTOMATION_CALENDAR_SETTINGS_MODAL_ID,
    layout: 'md',
    initialFocusSelector: modalUiSelector(AUTOMATION_CALENDAR_SETTINGS_MODAL_ID, 'first-day-select'),
    createElement: (_options: ModalOpenOptions): HTMLElement => createModalElementFromMarkup(AUTOMATION_CALENDAR_SETTINGS_MODAL_ID, renderAutomationCalendarSettingsModalMarkup())
});

const automationParametersModalDefinition: ModalDefinition = Object.freeze({
    id: AUTOMATION_PARAMETERS_MODAL_ID,
    layout: 'lg',
    initialFocusSelector: modalUiSelector(AUTOMATION_PARAMETERS_MODAL_ID, 'system-prompt-input'),
    createElement: (_options: ModalOpenOptions): HTMLElement => createModalElementFromMarkup(AUTOMATION_PARAMETERS_MODAL_ID, renderAutomationParametersModalMarkup())
});

const automationOccurrenceModalDefinition: ModalDefinition = Object.freeze({
    id: AUTOMATION_OCCURRENCE_MODAL_ID,
    layout: 'md',
    initialFocusSelector: MODAL_HEADER_CLOSE_SELECTOR,
    createElement: (_options: ModalOpenOptions): HTMLElement => createModalElementFromMarkup(AUTOMATION_OCCURRENCE_MODAL_ID, renderAutomationOccurrenceModalMarkup()),
    onOpen: (modal: HTMLElement): void => {
        const transcript = dom.resolve(modalUiSelector(AUTOMATION_OCCURRENCE_MODAL_ID, 'open-transcript'), modal);
        const viewTask = dom.resolve(modalUiSelector(AUTOMATION_OCCURRENCE_MODAL_ID, 'view-task'), modal);
        const candidates = [transcript, viewTask];
        const target = candidates.find((candidate) => candidate instanceof HTMLElement && !candidate.classList.contains('u-hidden'));
        if (target instanceof HTMLElement) {
            target.focus({ preventScroll: true });
        }
    }
});

const AUTOMATION_MODAL_DEFINITIONS: readonly ModalDefinition[] = Object.freeze([automationConfigurationModalDefinition, automationCalendarSettingsModalDefinition, automationParametersModalDefinition, automationOccurrenceModalDefinition]);

export { AUTOMATION_MODAL_DEFINITIONS };
