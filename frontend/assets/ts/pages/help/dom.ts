/* SoAI - Help page DOM contracts [frontend/assets/ts/pages/help/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { HelpUiRefs } from '@pages/help/types.ts';

interface HelpDomHost {
    requireHTMLElement: (selector: string, context?: Element | undefined) => HTMLElement;
}

export const requireHelpRoot = (host: HelpDomHost): HTMLElement => host.requireHTMLElement('#help-root');
export const requireHelpLogo = (host: HelpDomHost): HTMLElement => host.requireHTMLElement('.logo-ui-help');

export const optionalHelpRoot = (host: HelpDomHost): HTMLElement | null => {
    try {
        return requireHelpRoot(host);
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.debug('HelpPage', 'optionalHelpRoot: help root not present', runtimeError);
        return null;
    }
};

export const requireHelpUi = (host: HelpDomHost): HelpUiRefs => {
    return {
        root: requireHelpRoot(host),
        logo: requireHelpLogo(host)
    };
};
