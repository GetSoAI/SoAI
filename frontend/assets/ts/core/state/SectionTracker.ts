/* SoAI - Shared state section tracker [frontend/assets/ts/core/state/SectionTracker.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { getComputedStyleStrict } from '@core/environment/public.ts';
import type { DomService, ErrorHandler } from '@core/state/types.ts';
import { isFunction } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';

interface SectionData {
    section: string | null;
    subsection: string | null;
}

type SectionCallback = (data: SectionData) => void | Promise<void>;

interface SectionTrackerOptions {
    dom: DomService;
    errorHandler: ErrorHandler;
}

class SectionTracker {
    private readonly dom: DomService;
    private readonly errorHandler: ErrorHandler;
    private observer: IntersectionObserver | null;
    private sections: WeakMap<Element, SectionData>;
    currentSection: SectionData | null;
    private scrollContainer: Element | null;
    private callbacks: Set<SectionCallback>;
    private isInitialized: boolean;
    #generation: number;

    constructor({ dom, errorHandler }: SectionTrackerOptions) {
        this.dom = dom;
        this.errorHandler = errorHandler;
        this.observer = null;
        this.sections = new WeakMap();
        this.currentSection = null;
        this.scrollContainer = null;
        this.callbacks = new Set();
        this.isInitialized = false;
        this.#generation = 0;
    }

    private queryUI(selector: string, context: Element | Document | null = null): Element[] {
        return this.dom.resolveAll(selector, context);
    }

    getUI(selector: string, context: Element | Document | null = null): Element | null {
        return this.dom.resolve(selector, context);
    }

    initialize(): void {
        if (this.isInitialized) {
            this.cleanup();
        }
        this.#generation += 1;
        this.scrollContainer = this.findScrollContainer();
        if (!this.scrollContainer) {
            return;
        }
        const rootElement = this.dom.getDocumentElement();
        this.observer = new IntersectionObserver((entries) => this.handleIntersections(entries), {
            root: this.scrollContainer === rootElement ? null : this.scrollContainer,
            rootMargin: '-20% 0px -70% 0px',
            threshold: 0
        });
        this.isInitialized = true;
        this.scanForSections();
    }

    private findScrollContainer(): Element | null {
        const containers = this.dom.resolveAll('.page-scrollable');
        for (const container of containers) {
            if (!(container instanceof HTMLElement)) {
                continue;
            }
            const styles = getComputedStyleStrict(container);
            if (styles.overflowY === 'auto' || styles.overflowY === 'scroll') {
                return container;
            }
        }
        return this.dom.getDocumentElement();
    }

    private handleIntersections(entries: IntersectionObserverEntry[]): void {
        let topSection: Element | null = null;
        let topPosition = Infinity;
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                const rect = measureLayoutBox(entry.target);
                if (rect.top < topPosition && rect.top > -100) {
                    topPosition = rect.top;
                    topSection = entry.target;
                }
            }
        });
        if (topSection) {
            this.updateActiveSection({
                section: this.dom.getData(topSection, 'section') || null,
                subsection: this.dom.getData(topSection, 'subsection') || null
            });
        }
    }

    private scanForSections(): void {
        const observer = this.observer;
        if (!observer) {
            throw new Error('SectionTracker is not initialized');
        }
        this.queryUI('[data-section], [data-subsection]').forEach((element) => {
            observer.observe(element);
            this.sections.set(element, {
                section: this.dom.getData(element, 'section'),
                subsection: this.dom.getData(element, 'subsection')
            });
        });
    }

    private updateActiveSection(sectionData: SectionData): void {
        if (!sectionData || (sectionData.section === this.currentSection?.section && sectionData.subsection === this.currentSection?.subsection)) {
            return;
        }
        this.currentSection = sectionData;
        this.notifyCallbacks(sectionData);
    }

    private notifyCallbacks(sectionData: SectionData): void {
        const generation = this.#generation;
        this.callbacks.forEach((callback) => {
            const invokeCallback = async (): Promise<void> => {
                try {
                    if (!this.isInitialized || generation !== this.#generation) {
                        return;
                    }
                    await Promise.resolve(callback(sectionData));
                } catch (error) {
                    const runtimeError = ensureError(error);
                    this.errorHandler.warn?.('StateManager', 'Section callback failed', runtimeError);
                }
            };
            invokeCallback();
        });
    }

    subscribe(callback: SectionCallback): () => boolean {
        if (isFunction(callback)) {
            this.callbacks.add(callback);
        }
        return () => this.callbacks.delete(callback);
    }

    cleanup(): void {
        if (this.observer) {
            this.observer.disconnect();
            this.observer = null;
        }
        this.sections = new WeakMap();
        this.currentSection = null;
        this.isInitialized = false;
        this.#generation += 1;
    }

    forceUpdate(section: string, subsection: string | null = null): void {
        this.updateActiveSection({ section, subsection });
    }
}

export { SectionTracker };

export type { SectionData, SectionCallback, SectionTrackerOptions };
