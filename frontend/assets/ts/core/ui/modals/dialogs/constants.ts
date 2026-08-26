/* SoAI - Shared UI dialogs constants [frontend/assets/ts/core/ui/modals/dialogs/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const VARIANT_CLASS_MAP: Readonly<Record<string, string>> = Object.freeze({
    accent: 'ui-variant-accent',
    danger: 'ui-variant-danger',
    error: 'ui-variant-danger',
    info: 'ui-variant-neutral',
    neutral: 'ui-variant-neutral',
    primary: 'ui-variant-primary',
    warning: 'ui-variant-warning',
    success: 'ui-variant-success',
    violet: 'ui-variant-violet'
});

const resolveVariantIcon = (variant: string): string => {
    switch (variant) {
        case 'danger':
        case 'error':
            return 'danger-modal';
        case 'warning':
            return 'warning-modal';
        case 'success':
        case 'accent':
            return 'success-modal';
        case 'info':
        default:
            return 'info-modal';
    }
};

export { resolveVariantIcon, VARIANT_CLASS_MAP };
