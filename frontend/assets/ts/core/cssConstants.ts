/* SoAI - Shared frontend CSS constants [frontend/assets/ts/core/cssConstants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const CSS_CLASSES = Object.freeze({
    HIDDEN: 'u-hidden',
    VISIBLE: 'is-visible',
    COLLAPSED: 'is-collapsed',
    EXPANDED: 'is-expanded',
    ENABLED: 'is-enabled',
    ACTIVE: 'is-active',
    INACTIVE: 'inactive',
    LOADING: 'is-loading',
    ERROR: 'is-error',
    SUCCESS: 'is-success',
    WARNING: 'is-warning',
    SELECTED: 'is-selected',
    FOCUSED: 'is-focused',
    HOVER: 'is-hover',
    READONLY: 'is-readonly',
    REQUIRED: 'is-required',
    INVALID: 'is-invalid',
    VALID: 'is-valid'
});

type CSSClassKey = keyof typeof CSS_CLASSES;
type CSSClassValue = (typeof CSS_CLASSES)[CSSClassKey];

export { CSS_CLASSES };

export type { CSSClassKey, CSSClassValue };
