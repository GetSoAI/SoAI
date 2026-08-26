/* SoAI - Automation feature occurrence modal markup [frontend/assets/ts/features/automation/modals/markup/occurrenceModalMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import { renderModalBody, renderModalScaffoldMarkup, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { modalUiId } from '@core/modals/uiIds.ts';

import type { TrustedHtml } from '@core/security/public.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import { AUTOMATION_ACTION_OPEN_CHAT_TRANSCRIPT, AUTOMATION_ACTION_PREVIEW_AUTOMATION, AUTOMATION_ACTION_WINDOW_RUNS_DELETE_OCCURRENCE } from '@features/automation/actions.ts';
import { AUTOMATION_OCCURRENCE_MODAL_ID } from '@features/automation/modals/constants.ts';

const renderAutomationOccurrenceModalMarkup = (): TrustedHtml => {
    const closeLabel = i18n.t('common.close');
    const deleteLabel = i18n.t('common.delete');
    const viewLabel = i18n.t('common.view');
    const openTranscriptText = i18n.t('automation.pane.details.openTranscript');
    const occurrenceTitle = i18n.t('automation.pane.details.title');
    const excerptEmpty = i18n.t('automation.pane.details.noExcerpt');
    const excerptTitle = i18n.t('automation.pane.details.excerptTitle');
    const planTitle = i18n.t('automation.pane.details.planTitle');
    const planEmpty = i18n.t('automation.pane.details.planEmpty');
    const todoTitle = i18n.t('automation.pane.details.todoTitle');
    const todoEmpty = i18n.t('automation.pane.details.todoEmpty');
    const unsetPlaceholder = i18n.t('automation.placeholders.unset');
    const modalId = AUTOMATION_OCCURRENCE_MODAL_ID;

    const titleId = modalUiId(modalId, 'title');
    const header = renderStandardModalHeader({ modalId, title: occurrenceTitle, description: i18n.t('common.modalDescriptions.automationOccurrence'), closeLabel, titleId });
    const body = renderModalBody(
        uiHtml`<div class="automation-occurrence-modal-body">
            <section id="${modalUiId(modalId, 'summary')}" class="automation-occurrence-summary" aria-labelledby="${titleId}">
                <div class="automation-occurrence-summary-main">
                    <div id="${modalUiId(modalId, 'occurrence-title')}" class="automation-occurrence-title">${unsetPlaceholder}</div>
                    <div id="${modalUiId(modalId, 'when')}" class="automation-occurrence-when">${unsetPlaceholder}</div>
                </div>
                <div class="automation-occurrence-summary-side">
                    <span id="${modalUiId(modalId, 'status')}" class="ui-status-badge status-grey">${unsetPlaceholder}</span>
                </div>
            </section>
            <section class="automation-occurrence-excerpt-section" aria-labelledby="${modalUiId(modalId, 'excerpt-title')}">
                <div id="${modalUiId(modalId, 'excerpt-title')}" class="automation-occurrence-excerpt-title">${excerptTitle}</div>
                <div id="${modalUiId(modalId, 'excerpt')}" class="automation-occurrence-excerpt is-empty" aria-live="polite">${excerptEmpty}</div>
            </section>
            <section class="automation-occurrence-plan-section" aria-labelledby="${modalUiId(modalId, 'plan-title')}">
                <div id="${modalUiId(modalId, 'plan-title')}" class="automation-occurrence-plan-title">${planTitle}</div>
                <div id="${modalUiId(modalId, 'plan')}" class="automation-occurrence-plan is-empty" aria-live="polite">${planEmpty}</div>
            </section>
            <section class="automation-occurrence-todo-section" aria-labelledby="${modalUiId(modalId, 'todo-title')}">
                <div id="${modalUiId(modalId, 'todo-title')}" class="automation-occurrence-todo-title">${todoTitle}</div>
                <div id="${modalUiId(modalId, 'todo')}" class="automation-occurrence-todo is-empty" aria-live="polite">${todoEmpty}</div>
            </section>
        </div>`,
        { className: 'modal-body--sectioned' }
    );
    const footer = renderSplitModalFooter({
        left: renderModalFooterCloseButton({ modalId, text: closeLabel }),
        right: uiHtml`${renderModalFooterActionButton({
            text: deleteLabel,
            id: modalUiId(modalId, 'delete-run'),
            variant: 'danger',
            action: AUTOMATION_ACTION_WINDOW_RUNS_DELETE_OCCURRENCE,
            disabled: true,
            attributes: { 'data-zone-key': '' }
        })}${renderModalFooterActionButton({
            text: openTranscriptText,
            id: modalUiId(modalId, 'open-transcript'),
            variant: 'neutral',
            action: AUTOMATION_ACTION_OPEN_CHAT_TRANSCRIPT,
            disabled: true,
            attributes: { 'data-conversation-id': '', 'data-modal-close': modalId }
        })}${renderModalFooterActionButton({
            text: viewLabel,
            id: modalUiId(modalId, 'view-task'),
            variant: 'neutral',
            action: AUTOMATION_ACTION_PREVIEW_AUTOMATION,
            disabled: true,
            attributes: { 'data-automation-id': '', 'data-modal-close': modalId }
        })}`
    });
    return renderModalScaffoldMarkup({ id: modalId, header, body, footer, rootAttributes: { 'data-page-scope': 'automation' } });
};

export { renderAutomationOccurrenceModalMarkup };
