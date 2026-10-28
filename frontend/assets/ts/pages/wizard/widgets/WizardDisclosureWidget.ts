/* SoAI - Wizard disclosure presentation and expansion [frontend/assets/ts/pages/wizard/widgets/WizardDisclosureWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireRootHTMLElement } from '@core/dom/typedElementResolver.ts';
import { isReducedAnimationScope } from '@core/animations/speed.ts';
import { scrollElementIntoView } from '@core/scroll.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { uiAttr, uiAttributes, uiHtml } from '@core/security/uiHtml.ts';
import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';

const renderWizardDisclosure = (id: string, label: string, body: string, expanded = false, className = '', heading: TrustedHtml | null = null): string => uiHtml`<div class="wizard-disclosure ${uiAttr(className)}"><button type="button" class="wizard-disclosure-toggle" aria-label="${uiAttr(label)}" data-tooltip="${uiAttr(label)}" data-action="wizard-toggle-disclosure" aria-controls="${uiAttr(id)}" aria-expanded="${expanded ? 'true' : 'false'}"><span class="wizard-disclosure-chevron" aria-hidden="true">${getIconSync('chevron-right', { size: 14, strokeWidth: 4 })}</span><span class="wizard-disclosure-label">${heading ?? label}</span></button><div id="${uiAttr(id)}" class="wizard-reveal-region${expanded ? ' is-expanded' : ''}" aria-hidden="${expanded ? 'false' : 'true'}"${uiAttributes({ inert: !expanded })}><div class="wizard-reveal-region-inner">${toTrustedUiHtml(body)}</div></div></div>`.html;

const setWizardDisclosureExpanded = (button: HTMLElement, expanded: boolean): void => {
    const disclosure = button.closest('.wizard-disclosure');
    if (disclosure === null) throw new Error('Wizard disclosure is missing');
    const region = requireRootHTMLElement(disclosure, '.wizard-reveal-region', 'Wizard disclosure region');
    button.setAttribute('aria-expanded', String(expanded));
    region.setAttribute('aria-hidden', String(!expanded));
    region.toggleAttribute('inert', !expanded);
    region.classList.toggle('is-expanded', expanded);
    if (expanded && isReducedAnimationScope(region)) scrollElementIntoView(region);
};

export { renderWizardDisclosure, setWizardDisclosureExpanded };
