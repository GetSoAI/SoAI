/* SoAI - Hardware page overflow nav controller [frontend/assets/ts/pages/hardware/controllers/hardwareOverflowNavController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { bindEventGroup } from '@core/dom/eventBindingGroup.ts';
import { dom } from '@core/dom/dom.ts';
import { isHTMLElement } from '@core/typeGuards.ts';
import { OverflowNavController } from '@core/ui/controls/OverflowNav.ts';

type OverflowNavTarget = 'widgets' | 'gpu';

interface OverflowNavTargetConfig {
    target: OverflowNavTarget;
    wrapperSelector: string;
    scrollerSelector: string;
    required: boolean;
}

interface ResolvedOverflowNavTarget {
    target: OverflowNavTarget;
    scroller: HTMLElement;
    leftButton: HTMLElement;
    rightButton: HTMLElement;
}

const OVERFLOW_NAV_TARGETS: readonly OverflowNavTargetConfig[] = Object.freeze([
    {
        target: 'widgets',
        wrapperSelector: '.hardware-overflow-row-wrapper--widgets',
        scrollerSelector: '#hardwareWidgetsContainer',
        required: true
    },
    {
        target: 'gpu',
        wrapperSelector: '.hardware-overflow-row-wrapper--gpu',
        scrollerSelector: '#gpu-controls-container',
        required: false
    }
]);

class HardwareOverflowNavController {
    #widgetsController: OverflowNavController | null = null;
    #gpuController: OverflowNavController | null = null;
    #widgetsMutationObserver: MutationObserver | null = null;
    #gpuMutationObserver: MutationObserver | null = null;

    initialize(root: HTMLElement, signal: AbortSignal): void {
        this.dispose();
        const targets = OVERFLOW_NAV_TARGETS.map((config) => this.#resolveTarget(root, config));
        for (const target of targets) {
            if (target) {
                this.#initializeTarget(target, signal);
            }
        }
    }

    dispose(): void {
        this.#widgetsMutationObserver?.disconnect();
        this.#widgetsMutationObserver = null;
        this.#gpuMutationObserver?.disconnect();
        this.#gpuMutationObserver = null;
        this.#widgetsController?.dispose();
        this.#widgetsController = null;
        this.#gpuController?.dispose();
        this.#gpuController = null;
    }

    #resolveTarget(root: HTMLElement, config: OverflowNavTargetConfig): ResolvedOverflowNavTarget | null {
        const wrapper = dom.resolve(config.wrapperSelector, root);
        const scroller = dom.resolve(config.scrollerSelector, root);
        const leftButton = wrapper ? dom.resolve('.hardware-overflow-nav--left', wrapper) : null;
        const rightButton = wrapper ? dom.resolve('.hardware-overflow-nav--right', wrapper) : null;
        const hasAnyTargetNode = isHTMLElement(wrapper) || isHTMLElement(scroller) || isHTMLElement(leftButton) || isHTMLElement(rightButton);
        if (!config.required && !hasAnyTargetNode) {
            return null;
        }
        if (!isHTMLElement(wrapper) || !isHTMLElement(scroller) || !isHTMLElement(leftButton) || !isHTMLElement(rightButton)) {
            throw new Error(`Hardware overflow navigation requires complete ${config.target} UI`);
        }
        return {
            target: config.target,
            scroller,
            leftButton,
            rightButton
        };
    }

    #initializeTarget(resolved: ResolvedOverflowNavTarget, signal: AbortSignal): void {
        const controller = new OverflowNavController(resolved.scroller, resolved.leftButton, resolved.rightButton);
        controller.initialize((target, event, handler, options) => this.#bindEvent(target, event, handler, options, signal));

        const observer = new MutationObserver(() => controller.update());
        observer.observe(resolved.scroller, { childList: true });

        if (resolved.target === 'widgets') {
            this.#widgetsController = controller;
            this.#widgetsMutationObserver = observer;
            return;
        }
        this.#gpuController = controller;
        this.#gpuMutationObserver = observer;
    }

    #bindEvent(target: EventTarget, event: string, handler: EventListener, options: AddEventListenerOptions | undefined, signal: AbortSignal): () => void {
        return bindEventGroup(
            [
                {
                    target,
                    type: event,
                    listener: handler,
                    options
                }
            ],
            signal
        );
    }
}

export { HardwareOverflowNavController };
