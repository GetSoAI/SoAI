/* SoAI - Chat feature tool approval DOM contracts [frontend/assets/ts/features/chat/toolapproval/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';

const TOOL_APPROVAL_REMEMBER_TOGGLE_SELECTOR = '.tool-approval-remember-toggle';

const optionalToolApprovalRememberToggle = (preview: Element): HTMLInputElement | null => {
    const element = dom.resolve(TOOL_APPROVAL_REMEMBER_TOGGLE_SELECTOR, preview);
    if (element === null) {
        return null;
    }
    if (!(element instanceof HTMLInputElement)) {
        throw new Error('Tool approval remember toggle must be an HTMLInputElement');
    }
    return element;
};

const focusToolApprovalPrompt = (preview: Element | null): void => {
    if (!(preview instanceof HTMLElement)) {
        return;
    }
    if (!preview.hasAttribute('tabindex')) {
        preview.setAttribute('tabindex', '-1');
    }
    preview.focus({ preventScroll: true });
};

export { focusToolApprovalPrompt, optionalToolApprovalRememberToggle };
