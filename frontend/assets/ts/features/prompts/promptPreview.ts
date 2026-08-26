/* SoAI - Prompt content preview launcher [frontend/assets/ts/features/prompts/promptPreview.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PromptRequest, PromptResponse } from '@core/api/contracts/promptContracts.ts';
import { dom } from '@core/dom/dom.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { downloadFile, sanitizeDownloadFilename } from '@core/primitives/download.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { CONTENT_PREVIEW_MODAL_ID } from '@core/ui/modals/contentpreview/constants.ts';
import { createTextContentPreviewRequest } from '@core/ui/modals/contentpreview/requestFactories.ts';
import { requireContentPreviewModalService } from '@core/ui/modals/contentpreview/service.ts';
import type { ContentPreviewTextBaseline, ContentPreviewTextDraftSnapshot, ContentPreviewTextSaveResult } from '@core/ui/modals/contentpreview/types.ts';
import { copyTextWithBrowserClipboardFeedback } from '@core/ui/notifications/clipboardCopy.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import { ColorToolkit } from '@features/prompts/colorToolkit.ts';
import { buildPromptDownloadText, normalizePromptRecord, type PromptRecord } from '@features/prompts/promptRecords.ts';

interface PromptPreviewApi {
    get(id: string): Promise<PromptResponse>;
    create(data: PromptRequest): Promise<PromptResponse>;
    update(id: string, data: PromptRequest): Promise<PromptResponse>;
}

interface PromptPreviewSession {
    promptId: string | null;
    prompt: PromptRecord | null;
}

interface PromptPreviewHost {
    promptsApi: PromptPreviewApi;
    findPromptById?: (id: string | number) => PromptRecord | JsonValue | null | undefined;
    upsertPromptRecord?: (record: PromptResponse) => PromptRecord | null | undefined;
    requireModalElement: (id: string) => HTMLElement;
    getDocument: () => Document;
    showNotification: (message: string, type?: NotificationType, duration?: number) => void;
    runTask?: <T>(name: string, task: () => Promise<T>, options?: JsonObject) => Promise<T | null>;
    notifySaveChanged?: () => void;
    promptEnhancer?: { openFromPrompt(promptId: string | number): Promise<void> } | null;
}

interface OpenPromptPreviewOptions {
    edit?: boolean | undefined;
}

let promptPreviewSequence = 0;

const resolvePromptBaseline = (prompt: PromptRecord): ContentPreviewTextBaseline =>
    Object.freeze({
        title: prompt.name.trim() ? prompt.name : i18n.t('prompts.untitled'),
        content: prompt.content,
        promptColor: prompt.color
    });

const buildPromptFilename = (name: string): string => {
    const fallback = i18n.t('prompts.unnamedPrompt');
    return `${sanitizeDownloadFilename(name || fallback, fallback)}.txt`;
};

const createPromptPreviewColorToolkit = (host: PromptPreviewHost): ColorToolkit =>
    new ColorToolkit({
        queryUI: (selector, container) => dom.resolveAll(selector, container ?? host.getDocument()),
        toggleClassName: (element, className, force) => element.classList.toggle(className, force),
        optionalUI: (selector, container) => {
            const candidate = dom.resolve(selector, container ?? host.getDocument());
            return candidate instanceof Element ? candidate : null;
        },
        dom: { getDocument: () => host.getDocument() }
    });

const resolvePromptForPreview = async (host: PromptPreviewHost, promptId: string): Promise<PromptRecord> => {
    const local = host.findPromptById?.(promptId);
    if (local) {
        return normalizePromptRecord(local);
    }
    const remote = await host.promptsApi.get(promptId);
    host.upsertPromptRecord?.(remote);
    return normalizePromptRecord(remote);
};

const runPromptPreviewTask = async <T>(host: PromptPreviewHost, name: string, task: () => Promise<T>): Promise<T | null> => {
    if (host.runTask) {
        return await host.runTask(name, task, { rethrow: false });
    }
    return await task();
};

const presentPromptContentPreview = (host: PromptPreviewHost, session: PromptPreviewSession, baseline: ContentPreviewTextBaseline, options: OpenPromptPreviewOptions): boolean => {
    const colorToolkit = createPromptPreviewColorToolkit(host);
    const service = requireContentPreviewModalService();
    service.open(
        createTextContentPreviewRequest({
            scope: 'prompts',
            type: 'text',
            headerDescription: null,
            baseline,
            editable: true,
            isUnsavedDraft: session.promptId === null,
            languageMode: 'plaintextIfSql',
            disableCopyWhenEmpty: true,
            disableDownloadWhenEmpty: true,
            hideActionsWhenEmpty: true,
            colorToolkit: {
                mountHeaderColorToolkit: (container: HTMLElement): void => {
                    const modalRoot = host.requireModalElement(CONTENT_PREVIEW_MODAL_ID);
                    const currentColor = colorToolkit.normalize(modalRoot.dataset['promptColor'] ?? null);
                    const picker = colorToolkit.renderPicker(currentColor, 'modal');
                    picker.addEventListener('click', (event) => {
                        const target = event.target;
                        const button = target instanceof Element ? target.closest('.prompt-color-option') : null;
                        if (!(button instanceof HTMLElement)) {
                            return;
                        }
                        event.preventDefault();
                        event.stopPropagation();
                        const latestRoot = host.requireModalElement(CONTENT_PREVIEW_MODAL_ID);
                        const current = colorToolkit.normalize(latestRoot.dataset['selectedColor']);
                        const requested = colorToolkit.normalize(button.dataset['color']);
                        const next = current && requested && current === requested ? null : requested;
                        colorToolkit.applyToModal(latestRoot, next);
                        service.setTextSelectedColor(next);
                    });
                    container.textContent = '';
                    container.appendChild(picker);
                    colorToolkit.updatePicker(picker, currentColor);
                },
                unmountHeaderColorToolkit: (): void => {}
            },
            onRequestSave: async (draft: ContentPreviewTextDraftSnapshot): Promise<ContentPreviewTextSaveResult | null> => {
                const payload: PromptRequest = {
                    name: draft.title.trim(),
                    content: draft.content,
                    color: draft.selectedColor
                };
                const savedId = session.promptId;
                let saved: PromptResponse | null;
                try {
                    saved = savedId ? await runPromptPreviewTask(host, 'prompts.update', () => host.promptsApi.update(savedId, payload)) : await runPromptPreviewTask(host, 'prompts.create', () => host.promptsApi.create(payload));
                } catch (error) {
                    host.showNotification(i18n.t('prompts.notifications.saveFailed'), 'error');
                    throw ensureError(error);
                }
                if (!saved) {
                    return null;
                }
                const upserted = host.upsertPromptRecord?.(saved) ?? saved;
                const latest = normalizePromptRecord(upserted);
                session.promptId = latest.id;
                session.prompt = latest;
                host.showNotification(i18n.t('prompts.notifications.promptSaved'), 'success');
                host.notifySaveChanged?.();
                return Object.freeze({
                    baseline: resolvePromptBaseline(latest),
                    sourceReference: null
                });
            },
            onRequestDownload: (): void => {
                const activeId = session.promptId;
                const latest = activeId ? host.findPromptById?.(activeId) : null;
                const snapshot = latest ? normalizePromptRecord(latest) : session.prompt;
                if (!snapshot) {
                    throw new Error('Prompt preview cannot download an unsaved prompt');
                }
                downloadFile(buildPromptDownloadText(snapshot), buildPromptFilename(snapshot.name), 'text/plain');
            },
            onSaveComplete: null,
            onRequestCopy: async (text: string): Promise<void> => {
                try {
                    await copyTextWithBrowserClipboardFeedback(
                        {
                            showNotification: (message, type, duration): void => {
                                host.showNotification(message, type, duration);
                            }
                        },
                        {
                            text,
                            successMessage: i18n.t('prompts.notifications.promptCopied'),
                            errorMessage: i18n.t('prompts.notifications.copyFailed'),
                            unavailableMessage: i18n.t('common.clipboard.copyUnavailable'),
                            preserveText: true
                        }
                    );
                } catch (error) {
                    throw ensureError(error);
                }
            },
            enhance: host.promptEnhancer
                ? {
                      isEnabledForBaseline: (nextBaseline: ContentPreviewTextBaseline): boolean => session.promptId !== null && Boolean(nextBaseline.content && nextBaseline.content.trim().length > 0),
                      disabledTitle: i18n.t('prompts.enhancer.disabled.empty'),
                      onRequestEnhance: async (): Promise<void> => {
                          const activeId = session.promptId;
                          if (!activeId) {
                              throw new Error('Prompt enhancer requires a saved prompt');
                          }
                          await host.promptEnhancer?.openFromPrompt(activeId);
                      }
                  }
                : null,
            openSourceUrl: null,
            onStatePotentiallyChanged: () => host.notifySaveChanged?.()
        })
    );
    if (options.edit === true) {
        service.enterEditMode();
    }
    return true;
};

const openPromptContentPreview = async (host: PromptPreviewHost, promptId: string | number, options: OpenPromptPreviewOptions = {}): Promise<boolean> => {
    const normalizedId = String(promptId ?? '').trim();
    if (!normalizedId) {
        throw new Error('Prompt preview requires a prompt id');
    }
    const sequence = promptPreviewSequence + 1;
    promptPreviewSequence = sequence;
    const prompt = await resolvePromptForPreview(host, normalizedId);
    if (sequence !== promptPreviewSequence) {
        return true;
    }
    return presentPromptContentPreview(host, { promptId: normalizedId, prompt }, resolvePromptBaseline(prompt), options);
};

const openNewPromptContentPreview = (host: PromptPreviewHost): boolean => {
    promptPreviewSequence += 1;
    const baseline = Object.freeze({
        title: i18n.t('prompts.unnamedPrompt'),
        content: '',
        promptColor: null
    });
    return presentPromptContentPreview(host, { promptId: null, prompt: null }, baseline, { edit: true });
};

export { openNewPromptContentPreview, openPromptContentPreview };
export type { OpenPromptPreviewOptions, PromptPreviewHost };
