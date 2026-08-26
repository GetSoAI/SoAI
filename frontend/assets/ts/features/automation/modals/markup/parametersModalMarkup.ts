/* SoAI - Automation parameters modal markup [frontend/assets/ts/features/automation/modals/markup/parametersModalMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { renderChatParameterEditorModalMarkup } from '@core/chat/parameters/parameterEditorModalMarkup.ts';
import { i18n } from '@core/i18n/index.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { AUTOMATION_PARAMETERS_MODAL_ID } from '@features/automation/modals/constants.ts';

const renderAutomationParametersModalMarkup = (): TrustedHtml =>
    renderChatParameterEditorModalMarkup({
        modalId: AUTOMATION_PARAMETERS_MODAL_ID,
        title: i18n.t('automation.modal.parameters.title'),
        description: i18n.t('automation.modal.parameters.description'),
        closeLabel: i18n.t('common.close'),
        cancelLabel: i18n.t('common.cancel'),
        saveLabel: i18n.t('common.save'),
        pageScope: 'automation',
        includeSystemPromptLock: true
    });

export { renderAutomationParametersModalMarkup };
