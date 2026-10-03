/* SoAI - Wizard AI setup source selection view [frontend/assets/ts/pages/wizard/rendering/aisetup/sources/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { AiSetupSourcesView } from '@pages/wizard/contracts/aisetup/types.ts';
import { renderAiSetupChoiceCard, renderAiSetupHeading, renderAiSetupHint, renderFreeApiKeyLink } from '@pages/wizard/rendering/aisetup/view.ts';
import type { WizardViewContext } from '@pages/wizard/types.ts';

const AI_SOURCE_INPUT_NAME = 'wizard-ai-source';

const renderAiSourcesStep = (context: WizardViewContext, view: AiSetupSourcesView): string => {
    const heading = i18n.t('wizard.aiSetup.sources.heading');
    const limitedHint = view.limitedMessage === null ? '' : renderAiSetupHint(context, 'warning', view.limitedMessage);
    const recommended = view.limitedMessage === null ? '' : `<span class="ui-badge ui-badge--compact wizard-ai-recommended">${context.sanitizer.html(i18n.t('wizard.aiSetup.sources.cloud.recommended'))}</span>`;
    const localCard = renderAiSetupChoiceCard(context, {
        type: 'checkbox',
        name: AI_SOURCE_INPUT_NAME,
        value: 'local',
        selected: view.sources.local,
        icon: 'device-local',
        title: i18n.t('wizard.aiSetup.sources.local.title'),
        description: i18n.t('wizard.aiSetup.sources.local.description'),
        extraMarkup: limitedHint
    });
    const cloudCard = renderAiSetupChoiceCard(context, {
        type: 'checkbox',
        name: AI_SOURCE_INPUT_NAME,
        value: 'cloud',
        selected: view.sources.cloud,
        icon: 'weather-cloud',
        title: i18n.t('wizard.aiSetup.sources.cloud.title'),
        description: i18n.t('wizard.aiSetup.sources.cloud.description'),
        cornerBadgeMarkup: recommended
    });
    return `<div class="wizard-step wizard-step--ai">${renderAiSetupHeading(context, heading, i18n.t('wizard.aiSetup.sources.description'))}<div class="wizard-choice-grid wizard-ai-sources" role="group" aria-label="${context.sanitizer.attribute(heading)}"><div class="wizard-ai-source-cell">${localCard}</div><div class="wizard-ai-source-cell wizard-ai-source-cell--cloud">${cloudCard}<span class="wizard-ai-source-key">${renderFreeApiKeyLink(context)}</span></div></div></div>`;
};

export { AI_SOURCE_INPUT_NAME, renderAiSourcesStep };
