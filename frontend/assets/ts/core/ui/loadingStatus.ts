/* SoAI - Shared frontend UI loading status [frontend/assets/ts/core/ui/loadingStatus.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type InlineLoadingStatusOptions = {
    text: string;
    loading: boolean;
};

const resolveInlineStatusChild = (element: HTMLElement, className: string): HTMLElement | null => {
    for (const child of element.children) {
        if (child instanceof HTMLElement && child.classList.contains(className)) {
            return child;
        }
    }
    return null;
};

const renderInlineLoadingStatus = (element: HTMLElement, options: InlineLoadingStatusOptions): void => {
    const text = options.text.trim();
    element.classList.toggle('u-hidden', text.length === 0);
    element.classList.toggle('is-loading', options.loading && text.length > 0);
    const spinner = resolveInlineStatusChild(element, 'inline-loading-status-spinner');
    const textElement = resolveInlineStatusChild(element, 'inline-loading-status-text');
    if (text.length === 0) {
        spinner?.remove();
        if (textElement) {
            textElement.textContent = '';
        }
        return;
    }
    const documentRef = element.ownerDocument;
    if (options.loading) {
        if (!spinner) {
            const nextSpinner = documentRef.createElement('span');
            nextSpinner.className = 'loading-spinner inline-loading-status-spinner';
            nextSpinner.setAttribute('aria-hidden', 'true');
            element.prepend(nextSpinner);
        }
    } else {
        spinner?.remove();
    }
    const activeTextElement = textElement ?? documentRef.createElement('span');
    activeTextElement.className = 'inline-loading-status-text';
    activeTextElement.textContent = text;
    if (!textElement) {
        element.append(activeTextElement);
    }
};

export { renderInlineLoadingStatus };
