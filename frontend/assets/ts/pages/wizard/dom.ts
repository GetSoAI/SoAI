/* SoAI - Wizard page DOM contracts [frontend/assets/ts/pages/wizard/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { narrowButton, narrowForm, narrowImage } from '@core/dom/narrowElement.ts';
import type { WizardAccountUi, WizardUi } from '@pages/wizard/types.ts';

export const requireWizardUi = (dependencies: { requireHTMLElement: (selector: string, context?: ParentNode) => HTMLElement }): WizardUi => {
    const root = dependencies.requireHTMLElement('.wizard-container');
    const logo = narrowImage(dependencies.requireHTMLElement('.wizard-logo', root), 'Wizard logo');
    const content = dependencies.requireHTMLElement('#wizard-content', root);
    const progressFill = dependencies.requireHTMLElement('.wizard-progress .progress-fill', root);
    const progressText = dependencies.requireHTMLElement('.wizard-progress .wizard-progress-text', root);
    const navBackButton = narrowButton(dependencies.requireHTMLElement('#wizard-back', root), 'Wizard back button');
    const navNextButton = narrowButton(dependencies.requireHTMLElement('#wizard-next', root), 'Wizard next button');

    return { root, logo, content, progressFill, progressText, navBackButton, navNextButton };
};

export const requireWizardAccountUi = (dependencies: { requireHTMLElement: (selector: string, context?: ParentNode) => HTMLElement }): WizardAccountUi => {
    const root = dependencies.requireHTMLElement('.wizard-container');
    const form = narrowForm(dependencies.requireHTMLElement('#admin-user-form', root), 'Wizard account form');
    const errorBox = dependencies.requireHTMLElement('#user-creation-error', form);
    return { form, errorBox };
};

export const optionalWizardElement = (dependencies: { optionalHTMLElement: (selector: string, context?: ParentNode) => HTMLElement | null }, selector: string, context?: ParentNode): HTMLElement | null => {
    return dependencies.optionalHTMLElement(selector, context);
};
