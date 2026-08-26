/* SoAI - Shared DOM rebind button [frontend/assets/ts/core/dom/rebindButton.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const rebindButton = (button: HTMLButtonElement, contextMessage: string): HTMLButtonElement => {
    const cloned = button.cloneNode(true);
    if (!(cloned instanceof HTMLButtonElement)) {
        throw new Error(`${contextMessage}: failed to clone button`);
    }
    button.replaceWith(cloned);
    return cloned;
};

export { rebindButton };
