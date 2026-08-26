/* SoAI - About page easter egg controller [frontend/assets/ts/pages/about/controllers/EasterEggController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { scaleAnimationDurationMs } from '@core/animations/speed.ts';
import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { EASTER_EGG_MODAL_ID } from '@features/about/public.ts';
import { EasterEggAnimation } from '@pages/about/controllers/service.ts';
import type { AnimationHost } from '@pages/about/controllers/types.ts';

const CLICK_THRESHOLD = 5;
const RESET_TIMEOUT_MS = 2000;
const LOGO_FLASH_CLASS = 'logo-easter-activated';
const LOGO_FLASH_DURATION_MS = 1000;
const MODAL_OPEN_DELAY_MS = 450;

export class EasterEggController {
    readonly #resources = new ResourceTracker();
    #clickCount = 0;
    #resetTimer: number | null = null;
    #animation: EasterEggAnimation | null = null;
    #logoSection: HTMLElement | null = null;
    #resolveVersion: (() => string | null) | null = null;

    attach(logoSection: HTMLElement, resolveVersion: () => string | null): void {
        this.#logoSection = logoSection;
        this.#resolveVersion = resolveVersion;
        this.#resources.addEventListener(logoSection, 'click', () => this.#handleClick());
    }

    cleanup(): void {
        this.#animation?.cleanup();
        this.#animation = null;
        this.#resources.cleanup();
        this.#clickCount = 0;
        this.#logoSection = null;
        this.#resolveVersion = null;
    }

    #handleClick(): void {
        this.#clickCount += 1;
        if (this.#resetTimer !== null) {
            this.#resources.clearTimeout(this.#resetTimer);
        }
        this.#resetTimer = this.#resources.setTimeout(() => {
            this.#clickCount = 0;
            this.#resetTimer = null;
        }, RESET_TIMEOUT_MS);
        if (this.#clickCount >= CLICK_THRESHOLD) {
            this.#clickCount = 0;
            if (this.#resetTimer !== null) {
                this.#resources.clearTimeout(this.#resetTimer);
                this.#resetTimer = null;
            }
            this.#triggerEasterEgg();
        }
    }

    #triggerEasterEgg(): void {
        this.#flashLogo();
        this.#resources.setTimeout(
            () => {
                this.#openEasterEggModal();
            },
            scaleAnimationDurationMs(MODAL_OPEN_DELAY_MS, this.#logoSection)
        );
    }

    #flashLogo(): void {
        const logoSection = this.#logoSection;
        if (!logoSection) {
            return;
        }
        const logo = dom.resolve('.logo-ui-about', logoSection);
        if (!(logo instanceof HTMLElement) || logo.classList.contains(LOGO_FLASH_CLASS)) {
            return;
        }
        logo.classList.add(LOGO_FLASH_CLASS);
        this.#resources.setTimeout(
            () => {
                logo.classList.remove(LOGO_FLASH_CLASS);
            },
            scaleAnimationDurationMs(LOGO_FLASH_DURATION_MS, logo)
        );
    }

    #openEasterEggModal(): void {
        const presenter = requireModalPresenter();
        const modal = presenter.requireElement(EASTER_EGG_MODAL_ID);
        this.#applyVersionDescription(modal);
        presenter.open(EASTER_EGG_MODAL_ID);
        this.#resources.setTimeout(
            () => {
                this.#resources.requestAnimationFrame(() => {
                    this.#initializeAnimation();
                });
            },
            scaleAnimationDurationMs(250, modal)
        );
    }

    #applyVersionDescription(modal: HTMLElement): void {
        const version = this.#resolveVersion ? this.#resolveVersion() : null;
        if (!version) {
            throw new Error('SoAI version unavailable for easter egg modal description');
        }
        const description = dom.resolve(modalUiSelector(EASTER_EGG_MODAL_ID, 'description'), modal);
        if (!(description instanceof HTMLElement)) {
            throw new Error('Easter egg modal description element missing');
        }
        description.textContent = i18n.t('about.easterEgg.version', { version });
        description.classList.remove('u-hidden');
    }

    #initializeAnimation(): void {
        const modal = dom.resolve(`#${EASTER_EGG_MODAL_ID}`);
        if (!(modal instanceof HTMLElement)) {
            return;
        }
        if (this.#animation) {
            this.#animation.cleanup();
        }
        this.#animation = new EasterEggAnimation();
        const animationHost: AnimationHost = {
            getScene: () => {
                const candidate = dom.resolve('.easter-egg-scene', modal);
                return candidate instanceof HTMLElement ? candidate : null;
            },
            getOrb: () => {
                const candidate = dom.resolve('.easter-egg-orb', modal);
                return candidate instanceof HTMLElement ? candidate : null;
            },
            getParticleCanvas: () => {
                const candidate = dom.resolve('.easter-egg-particles', modal);
                return candidate instanceof HTMLCanvasElement ? candidate : null;
            },
            getGlowElement: () => {
                const candidate = dom.resolve('.easter-egg-glow', modal);
                return candidate instanceof HTMLElement ? candidate : null;
            },
            onCelebrationComplete: () => {}
        };
        this.#animation.initialize(animationHost);
    }
}
