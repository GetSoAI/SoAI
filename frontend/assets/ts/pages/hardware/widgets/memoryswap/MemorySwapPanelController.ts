/* SoAI - Hardware page widgets memory swap panel controller [frontend/assets/ts/pages/hardware/widgets/memoryswap/MemorySwapPanelController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { renderContentImmediately, transitionContentElements } from '@core/animations/contentFadeTransition.ts';
import { i18n } from '@core/i18n/index.ts';
import type { HardwareProcessesResource } from '@core/realtime/streammanager/resources/resourceValueContracts.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { buildMemorySwapRenderModel } from '@pages/hardware/widgets/memoryswap/mappers.ts';
import { createMemorySwapPanel, renderMemorySwapPanel } from '@pages/hardware/widgets/memoryswap/view.ts';
import type { HardwarePageSnapshot } from '@pages/hardware/types.ts';
import type { MemorySwapMode, MemorySwapPanelHost, MemorySwapPanelSurfaces } from '@pages/hardware/widgets/memoryswap/types.ts';
import type { ProcessRecord } from '@pages/hardware/widgets/processes/types.ts';

class MemorySwapPanelController {
    readonly #host: MemorySwapPanelHost;
    #mode: MemorySwapMode = 'ram';
    #snapshot: HardwarePageSnapshot | null = null;
    #processes: ProcessRecord[] = [];
    #processDataReady = false;
    #canViewProcesses = false;
    #summary: HTMLElement | null = null;
    #toggle: HTMLElement | null = null;
    #surfaces: MemorySwapPanelSurfaces | null = null;

    constructor(host: MemorySwapPanelHost) {
        this.#host = host;
    }

    initialize(): void {
        const content = this.#host.optionalHTMLElement('hardwareMemorySwapContent');
        const summary = this.#host.optionalHTMLElement('hardwareMemorySwapSummary');
        const toggle = this.#host.optionalHTMLElement('hardwareMemorySwapToggle');
        if (!content || !summary || !toggle) {
            throw new Error('Hardware Memory panel DOM is incomplete');
        }
        this.#summary = summary;
        this.#toggle = toggle;
        this.#surfaces = createMemorySwapPanel(this.#host, content);
        this.#render();
    }

    setProcessPermission(canViewProcesses: boolean): void {
        this.#canViewProcesses = canViewProcesses;
        if (!canViewProcesses) {
            this.#processes = [];
            this.#processDataReady = false;
        }
        this.#render();
    }

    handleSnapshot(snapshot: HardwarePageSnapshot): void {
        this.#snapshot = snapshot;
        this.#render();
    }

    handleProcessResourceUpdate(processes: HardwareProcessesResource): void {
        if (!this.#canViewProcesses) {
            this.#processes = [];
            this.#processDataReady = false;
            this.#render();
            return;
        }
        this.#processes = processes;
        this.#processDataReady = true;
        this.#render();
    }

    resetProcessData(): void {
        this.#processes = [];
        this.#processDataReady = false;
        this.#render();
    }

    toggleMode(): void {
        this.#mode = this.#mode === 'ram' ? 'swap' : 'ram';
        this.#render(true);
    }

    dispose(): void {
        this.#snapshot = null;
        this.#processes = [];
        this.#processDataReady = false;
        this.#summary = null;
        this.#toggle = null;
        this.#surfaces = null;
    }

    #render(animate: boolean = false): void {
        const summary = this.#summary;
        const toggle = this.#toggle;
        const surfaces = this.#surfaces;
        if (!summary || !toggle || !surfaces) {
            return;
        }
        const model = buildMemorySwapRenderModel({
            snapshot: this.#snapshot,
            mode: this.#mode,
            processes: this.#processes,
            processDataReady: this.#processDataReady,
            canViewProcesses: this.#canViewProcesses
        });
        this.#host.updateText(summary, model.summary);
        const toggleLabel = this.#mode === 'ram' ? i18n.t('hardware.cards.memorySwap.actions.showSwap') : i18n.t('hardware.cards.memorySwap.actions.showRam');
        toggle.setAttribute('aria-label', toggleLabel);
        setTooltipText(toggle, toggleLabel);
        toggle.setAttribute('aria-pressed', this.#mode === 'swap' ? 'true' : 'false');
        const render = (): void => renderMemorySwapPanel(this.#host, surfaces, model);
        const elements = [surfaces.gauges, surfaces.processes];
        if (animate) {
            transitionContentElements({ elements, render });
            return;
        }
        renderContentImmediately({ elements, render });
    }
}

export { MemorySwapPanelController };
