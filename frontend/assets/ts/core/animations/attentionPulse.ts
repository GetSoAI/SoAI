/* SoAI - Shared cancellable attention pulse [frontend/assets/ts/core/animations/attentionPulse.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isReducedAnimationScope } from '@core/animations/speed.ts';

const ATTENTION_PULSE_DURATION_MS = 900;
const ATTENTION_PULSE_CLASS = 'ui-attention-pulse';
const ATTENTION_PULSE_REDUCED_CLASS = 'ui-attention-pulse--reduced';

interface AttentionPulseHandle {
    cancel(): void;
}

const playAttentionPulse = (element: HTMLElement, durationMs: number = ATTENTION_PULSE_DURATION_MS): AttentionPulseHandle => {
    const view = element.ownerDocument.defaultView;
    if (!view) throw new Error('Attention pulse requires an owning window');
    let active = true;
    let timer = 0;
    const cancel = (): void => {
        if (!active) return;
        active = false;
        view.clearTimeout(timer);
        element.classList.remove(ATTENTION_PULSE_CLASS, ATTENTION_PULSE_REDUCED_CLASS);
        element.style.removeProperty('--attention-pulse-duration');
    };
    element.classList.remove(ATTENTION_PULSE_CLASS, ATTENTION_PULSE_REDUCED_CLASS);
    void element.offsetWidth;
    element.style.setProperty('--attention-pulse-duration', `${durationMs}ms`);
    element.classList.add(ATTENTION_PULSE_CLASS);
    if (isReducedAnimationScope(element)) element.classList.add(ATTENTION_PULSE_REDUCED_CLASS);
    timer = view.setTimeout(cancel, durationMs);
    return { cancel };
};

export { ATTENTION_PULSE_DURATION_MS, playAttentionPulse };
export type { AttentionPulseHandle };
