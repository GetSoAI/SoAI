/* SoAI - Authenticated shell entrance motion [frontend/assets/ts/core/layout/shellEntrance.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseMaxCssDurationMs } from '@core/animations/parseMaxCssDurationMs.ts';
import { isReducedAnimationScope } from '@core/animations/speed.ts';
import { measureElementLayoutDimensions } from '@core/layout/elementGeometry.ts';
import { getComputedStyleStrict } from '@core/environment/public.ts';

const entrances = new WeakMap<HTMLElement, Animation>();

const cancelShellEntrance = (elements: readonly HTMLElement[]): void => {
    for (const element of elements) {
        entrances.get(element)?.cancel();
        entrances.delete(element);
    }
};

const animateShellEntrance = (elements: readonly HTMLElement[]): void => {
    for (const element of elements) {
        if (entrances.has(element)) continue;
        if (typeof element.animate !== 'function' || isReducedAnimationScope(element)) continue;
        const style = getComputedStyleStrict(element);
        const duration = parseMaxCssDurationMs(style.getPropertyValue('--motion-shell-enter-duration'));
        if (duration === 0 || style.display === 'none' || style.visibility === 'hidden') continue;
        const sidebar = element.classList.contains('sidebar');
        if (sidebar && (element.getAttribute('aria-hidden') === 'true' || measureElementLayoutDimensions(element).width <= 0)) continue;
        const from = style.getPropertyValue(sidebar ? '--motion-shell-sidebar-from' : '--motion-shell-header-from').trim();
        const animation = element.animate(
            [
                { translate: from, opacity: 0 },
                { translate: '0 0', opacity: 1 }
            ],
            { duration, easing: style.getPropertyValue('--motion-shell-enter-ease').trim(), fill: 'backwards' }
        );
        entrances.set(element, animation);
        const forget = (): void => {
            if (entrances.get(element) === animation) entrances.delete(element);
        };
        animation.addEventListener('finish', forget, { once: true });
        animation.addEventListener('cancel', forget, { once: true });
    }
};

export { animateShellEntrance, cancelShellEntrance };
