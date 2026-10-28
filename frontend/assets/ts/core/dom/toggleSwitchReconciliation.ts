/* SoAI - Preserve toggle switch label fades and handle motion across element replacement [frontend/assets/ts/core/dom/toggleSwitchReconciliation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseMaxCssDurationMs } from '@core/animations/parseMaxCssDurationMs.ts';
import { isReducedAnimationScope } from '@core/animations/speed.ts';
import { syncElementShell } from '@core/dom/patching.ts';
import { applyTextContent } from '@core/dom/textContent.ts';
import { getComputedStyleStrict } from '@core/environment/public.ts';

const TOGGLE_MOTION_DURATION_PROPERTY = '--toggle-motion-duration';
const TOGGLE_MOTION_EASE_PROPERTY = '--toggle-motion-ease';
const TOGGLE_HANDLE_PSEUDO_ELEMENT = '::before';
const TOGGLE_SLIDER_SELECTOR = '.toggle-switch:not([data-toggle-dragging], [data-toggle-drag-settling]) > .slider';
type ToggleMotionProperty = 'transform' | 'boxShadow' | 'backgroundColor' | 'borderColor';

const TOGGLE_HANDLE_PROPERTIES: readonly ToggleMotionProperty[] = ['transform', 'boxShadow'];
const TOGGLE_TRACK_PROPERTIES: readonly ToggleMotionProperty[] = ['backgroundColor', 'borderColor'];
type ToggleMotionValues = Partial<Record<ToggleMotionProperty, string>>;

interface ToggleSliderSnapshot {
    handle: ToggleMotionValues;
    track: ToggleMotionValues;
}

interface ToggleSwitchContinuity {
    restore(current: Element): void;
}

const resolveToggleIdentity = (toggle: Element | null, input: Element | null | undefined): string => toggle?.id || input?.id || input?.getAttribute('name') || toggle?.getAttribute('data-action') || '';

const indexToggleSliders = (root: Element): Map<string, HTMLElement | null> => {
    const sliders = new Map<string, HTMLElement | null>();
    let ordinal = 0;
    for (const slider of root.querySelectorAll(TOGGLE_SLIDER_SELECTOR)) {
        const toggle = slider.parentElement;
        if (!(slider instanceof HTMLElement) || toggle === null) continue;
        const identity = resolveToggleIdentity(toggle, toggle.querySelector(':scope > input')) || `toggle-switch-${ordinal}`;
        ordinal += 1;
        sliders.set(identity, sliders.has(identity) ? null : slider);
    }
    return sliders;
};

const indexToggleLabels = (root: Element): Map<string, HTMLElement | null> => {
    const labels = new Map<string, HTMLElement | null>();
    for (const label of root.querySelectorAll('.toggle-switch .toggle-label')) {
        if (!(label instanceof HTMLElement)) continue;
        const toggle = label.closest('.toggle-switch');
        const input = toggle?.querySelector('input');
        const identity = label.id || resolveToggleIdentity(toggle, input) || label.className;
        labels.set(identity, labels.has(identity) ? null : label);
    }
    return labels;
};

const transplantToggleLabels = (previousLabels: ReadonlyMap<string, HTMLElement | null>, current: Element): void => {
    for (const [identity, currentLabel] of indexToggleLabels(current)) {
        const previousLabel = previousLabels.get(identity);
        if (!currentLabel || !previousLabel || previousLabel === currentLabel || previousLabel.tagName !== currentLabel.tagName) continue;
        const text = currentLabel.textContent ?? '';
        syncElementShell({ target: previousLabel, source: currentLabel });
        currentLabel.replaceWith(previousLabel);
        applyTextContent(previousLabel, text);
    }
};

const readMotionValues = (style: CSSStyleDeclaration, properties: readonly ToggleMotionProperty[]): ToggleMotionValues => Object.fromEntries(properties.map((property) => [property, style[property]]));

const snapshotToggleSlider = (slider: HTMLElement): ToggleSliderSnapshot => ({
    handle: readMotionValues(getComputedStyleStrict(slider, TOGGLE_HANDLE_PSEUDO_ELEMENT), TOGGLE_HANDLE_PROPERTIES),
    track: readMotionValues(getComputedStyleStrict(slider), TOGGLE_TRACK_PROPERTIES)
});

const resolveChangedKeyframes = (from: ToggleMotionValues, to: ToggleMotionValues): Keyframe[] | null => {
    const changed = [...TOGGLE_HANDLE_PROPERTIES, ...TOGGLE_TRACK_PROPERTIES].filter((property) => Object.hasOwn(to, property) && from[property] !== to[property]);
    if (changed.length === 0) return null;
    return [Object.fromEntries(changed.map((property) => [property, from[property]])), Object.fromEntries(changed.map((property) => [property, to[property]]))];
};

const continueToggleSliderMotion = (slider: HTMLElement, snapshot: ToggleSliderSnapshot): void => {
    const style = getComputedStyleStrict(slider);
    const duration = parseMaxCssDurationMs(style.getPropertyValue(TOGGLE_MOTION_DURATION_PROPERTY));
    const easing = style.getPropertyValue(TOGGLE_MOTION_EASE_PROPERTY).trim();
    if (duration <= 0 || easing === '') return;
    const current = snapshotToggleSlider(slider);
    const handleKeyframes = resolveChangedKeyframes(snapshot.handle, current.handle);
    const trackKeyframes = resolveChangedKeyframes(snapshot.track, current.track);
    if (handleKeyframes !== null) slider.animate(handleKeyframes, { duration, easing, pseudoElement: TOGGLE_HANDLE_PSEUDO_ELEMENT });
    if (trackKeyframes !== null) slider.animate(trackKeyframes, { duration, easing });
};

const canContinueToggleMotion = (element: Element): boolean => element.isConnected && typeof element.animate === 'function' && !isReducedAnimationScope(element);

const captureToggleSwitchContinuity = (previous: Element): ToggleSwitchContinuity => {
    const labels = indexToggleLabels(previous);
    const snapshots = new Map<string, ToggleSliderSnapshot>();
    if (canContinueToggleMotion(previous)) {
        for (const [identity, slider] of indexToggleSliders(previous)) {
            if (slider !== null) snapshots.set(identity, snapshotToggleSlider(slider));
        }
    }
    return {
        restore: (current: Element): void => {
            transplantToggleLabels(labels, current);
            if (snapshots.size === 0 || !canContinueToggleMotion(current)) return;
            for (const [identity, slider] of indexToggleSliders(current)) {
                const snapshot = snapshots.get(identity);
                if (slider !== null && snapshot !== undefined) continueToggleSliderMotion(slider, snapshot);
            }
        }
    };
};

export { captureToggleSwitchContinuity };
export type { ToggleSwitchContinuity };
