/* SoAI - Plugin toggle animation continuity across collection commits [frontend/assets/ts/pages/plugins/rendering/pluginToggleMotionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { optionalPendingPluginToggleSlider } from '@pages/plugins/dom.ts';

const synchronizePluginToggleMotion = (mountedElements: readonly HTMLElement[], startedAtByPlugin: Map<string, number>): void => {
    const pendingPlugins = new Set<string>();
    for (const element of mountedElements) {
        const identifier = element.dataset['collectionId'];
        const slider = optionalPendingPluginToggleSlider(element);
        if (identifier === undefined || slider === null) continue;
        const currentTime = slider.ownerDocument.timeline.currentTime;
        if (typeof currentTime !== 'number') continue;
        pendingPlugins.add(identifier);
        const startedAt = startedAtByPlugin.get(identifier) ?? currentTime;
        startedAtByPlugin.set(identifier, startedAt);
        for (const animation of slider.getAnimations({ subtree: true })) {
            if (animation instanceof CSSAnimation && (animation.animationName === 'spin' || animation.animationName === 'toggle-switch-spinner-reveal')) {
                animation.startTime = startedAt;
            }
        }
    }
    for (const identifier of startedAtByPlugin.keys()) {
        if (!pendingPlugins.has(identifier)) startedAtByPlugin.delete(identifier);
    }
};

export { synchronizePluginToggleMotion };
