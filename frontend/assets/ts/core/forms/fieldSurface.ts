/* SoAI - Shared forms field surface [frontend/assets/ts/core/forms/fieldSurface.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const FIELD_CHANGE_SURFACE_CLASS = 'setting-change-surface';
const FIELD_CHANGE_SURFACE_SELECTOR = `.${FIELD_CHANGE_SURFACE_CLASS}`;
const FIELD_MODIFIED_CLASS = 'modified';
const FIELD_INVALID_CLASS = 'is-invalid';

const resolveFieldSurface = (element: Element): Element | null => element.closest(FIELD_CHANGE_SURFACE_SELECTOR);

const requireFieldSurface = (element: Element): Element => {
    const surface = resolveFieldSurface(element);
    if (!surface) {
        throw new Error('Field state target is missing a setting-change-surface owner');
    }
    return surface;
};

const setFieldSurfaceModified = (element: Element | null, isModified: boolean): void => {
    if (!element) {
        return;
    }
    requireFieldSurface(element).classList.toggle(FIELD_MODIFIED_CLASS, isModified);
};

const setFieldSurfaceInvalid = (element: Element | null, isInvalid: boolean): void => {
    if (!element) {
        return;
    }
    const surface = requireFieldSurface(element);
    surface.classList.toggle(FIELD_INVALID_CLASS, isInvalid);
    if (surface instanceof HTMLElement) {
        if (isInvalid) {
            surface.setAttribute('aria-invalid', 'true');
        } else {
            surface.removeAttribute('aria-invalid');
        }
    }
};

export { FIELD_CHANGE_SURFACE_CLASS, FIELD_INVALID_CLASS, FIELD_MODIFIED_CLASS, requireFieldSurface, resolveFieldSurface, setFieldSurfaceInvalid, setFieldSurfaceModified };
