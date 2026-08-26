/* SoAI - Settings token-flow modal scaffolding [frontend/assets/ts/features/settings/tokenflow/modalScaffold.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireModalPresenter, type ModalDefinition } from '@core/modals/modalPresenter.ts';
import { runModalSession, type ModalSessionInitializer } from '@core/modals/modalSession.ts';
import { createModalElement } from '@core/modals/scaffoldDom.ts';
import type { ModalOpenOptions } from '@core/modals/types.ts';
import type { TrustedHtml } from '@core/security/public.ts';

interface SettingsTokenModalDefinitionOptions<TConfig> {
    modalId: string;
    initialFocusSelector: string;
    configFactory: () => TConfig;
    createElement: (config: TConfig) => HTMLElement;
}

interface SettingsTokenModalElementOptions {
    modalId: string;
    title: string | TrustedHtml;
    body: TrustedHtml;
    footer: TrustedHtml;
    className?: string;
}

interface SettingsTokenModalSessionOptions<TResult> {
    modalId: string;
    initialResult: TResult;
    initialize: ModalSessionInitializer<TResult>;
}

const buildSettingsTokenModalDefinition = <TConfig>(options: SettingsTokenModalDefinitionOptions<TConfig>): ModalDefinition => ({
    id: options.modalId,
    layout: 'md',
    initialFocusSelector: options.initialFocusSelector,
    createElement: (_modalOptions: ModalOpenOptions): HTMLElement => options.createElement(options.configFactory())
});

const createSettingsTokenModalElement = (options: SettingsTokenModalElementOptions): HTMLElement => {
    return createModalElement({
        id: options.modalId,
        className: options.className ?? 'settings-token-flow-modal',
        header: options.title,
        body: options.body,
        footer: options.footer,
        contentClassName: 'prompt-modal-content',
        rootAttributes: { 'data-page-scope': 'settings' }
    });
};

const runSettingsTokenModalSession = async <TResult>(options: SettingsTokenModalSessionOptions<TResult>): Promise<TResult> => {
    return await runModalSession<TResult>({
        presenter: requireModalPresenter(),
        modalId: options.modalId,
        onAlreadyOpen: 'replace',
        initialResult: options.initialResult,
        initialize: options.initialize
    });
};

const bindModalEnterSubmit = (element: HTMLInputElement, submit: (event: Event) => void, signal: AbortSignal): void => {
    element.addEventListener(
        'keydown',
        (event: Event): void => {
            if (!(event instanceof KeyboardEvent) || event.key !== 'Enter') {
                return;
            }
            submit(event);
        },
        { signal }
    );
};

export { bindModalEnterSubmit, buildSettingsTokenModalDefinition, createSettingsTokenModalElement, runSettingsTokenModalSession };
