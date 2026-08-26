/* SoAI - Chat page agent plan modal [frontend/assets/ts/pages/chat/controllers/chatpageagent/agentPlanModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import type { AgentPlanStep } from '@core/chat/agentTypes.ts';
import { dom } from '@core/dom/dom.ts';
import { rebindButton } from '@core/dom/rebindButton.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { downloadFile, sanitizeDownloadFilename } from '@core/primitives/download.ts';
import { AGENT_PLAN_MODAL_ID } from '@features/chat/public.ts';
import { copyCodeBlock, type CopyCodeBlockHost } from '@pages/chat/controllers/page/actions/copyCodeBlock.ts';
import type { ChatPageAgentHost } from '@pages/chat/controllers/chatpageagent/contracts.ts';

type AgentPlanModalArguments = {
    host: ChatPageAgentHost;
    markdown: string;
    title: string | null;
    todo: AgentPlanStep[];
    explanation: string | null;
    onModalOpen: () => void;
    onModalClose: () => void;
};

const FENCED_CODE_BLOCK_PATTERN = /```([^\n`]*)\s*\n([\s\S]*?)```/g;
const PLAN_DOWNLOAD_FALLBACK_FILENAME = 'agent-plan.md';

const createCopyCodeBlockHost = (host: ChatPageAgentHost): CopyCodeBlockHost => {
    return {
        feedback: host.workflow.feedback,
        hasClipboardSupport: () => host.interaction.hasClipboardSupport(),
        copyToClipboard: (text, options) => host.interaction.copyToClipboard(text, options)
    };
};

const extractFencedCodeBlocks = (markdown: string): string[] => {
    const normalizedMarkdown = String(markdown ?? '').replace(/\r\n?/g, '\n');
    const codeBlocks: string[] = [];
    let match: RegExpExecArray | null;
    while ((match = FENCED_CODE_BLOCK_PATTERN.exec(normalizedMarkdown)) !== null) {
        const fullMatch = match[0];
        if (fullMatch) {
            codeBlocks.push(fullMatch);
        }
    }
    return codeBlocks;
};

const bindPlanCodeBlockCopyButtons = (host: ChatPageAgentHost, contentRoot: Element, markdown: string): void => {
    const copyHost = createCopyCodeBlockHost(host);
    const codeBlocks = extractFencedCodeBlocks(markdown);
    const buttons = dom.resolveAll('.message-code-block .code-copy-btn', contentRoot);
    const buildCodeBlockCopyHandler = (button: HTMLButtonElement): (() => void) => {
        return (): void => {
            void copyCodeBlock(copyHost, button, { preferMarkdown: true }).catch((error): void => {
                const narrowed = ensureError(error);
                host.workflow.logWarning('Failed to copy agent plan code block markdown to clipboard', narrowed);
            });
        };
    };
    for (let index = 0; index < buttons.length; index += 1) {
        const button = buttons[index];
        if (!(button instanceof HTMLButtonElement)) {
            continue;
        }
        const rebound = rebindButton(button, 'Agent plan modal failed to rebind code-block copy button');
        const fencedMarkdown = codeBlocks[index] ?? null;
        if (fencedMarkdown !== null) {
            rebound.setAttribute('data-code-markdown', encodeURIComponent(fencedMarkdown));
        }
        rebound.addEventListener('click', buildCodeBlockCopyHandler(rebound));
    }
};

const buildPlanDownloadFilename = (title: string | null): string => {
    const filename = title && title.trim() ? `${title.trim()}.md` : PLAN_DOWNLOAD_FALLBACK_FILENAME;
    return sanitizeDownloadFilename(filename, PLAN_DOWNLOAD_FALLBACK_FILENAME);
};

const normalizePlanLine = (value: string): string => value.replace(/\s+/g, ' ').trim();

const resolveTodoStatusLabel = (status: AgentPlanStep['status']): string => {
    if (status === 'completed') {
        return i18n.t('chat.toolActivity.status.completed');
    }
    if (status === 'in_progress') {
        return i18n.t('chat.toolActivity.status.running');
    }
    return i18n.t('chat.toolActivity.status.pending');
};

const renderTodoPlanMarkdown = (inputArguments: { title: string | null; explanation: string | null; todo: AgentPlanStep[] }): string => {
    const title = normalizePlanLine(inputArguments.title ?? '') || i18n.t('chat.agent.plan.modalTitle');
    const lines: string[] = [`# ${title}`];
    const explanation = normalizePlanLine(inputArguments.explanation ?? '');
    if (explanation) {
        lines.push('', explanation);
    }
    if (inputArguments.todo.length > 0) {
        lines.push('');
    }
    for (const item of inputArguments.todo) {
        const step = normalizePlanLine(item.step);
        if (!step) {
            continue;
        }
        const checkbox = item.status === 'completed' ? 'x' : ' ';
        lines.push(`- [${checkbox}] ${step} (${resolveTodoStatusLabel(item.status)})`);
    }
    return lines.join('\n').trim();
};

const resolvePlanMarkdown = (inputArguments: AgentPlanModalArguments): string => {
    const markdown = inputArguments.markdown.trim();
    if (markdown) {
        return inputArguments.markdown;
    }
    return renderTodoPlanMarkdown({
        title: inputArguments.title,
        explanation: inputArguments.explanation,
        todo: inputArguments.todo
    });
};

const openAgentPlanModal = (inputArguments: AgentPlanModalArguments): void => {
    const modalId = AGENT_PLAN_MODAL_ID;
    const presenter = requireModalPresenter();
    presenter.open(modalId);
    const modal = presenter.requireElement(modalId);
    const handlePlanModalClose = (): void => inputArguments.onModalClose();
    modal.addEventListener('core.modal.close', handlePlanModalClose, { once: true });

    const titleId = modalUiId(modalId, 'title');
    const contentId = modalUiId(modalId, 'content');
    const copyButtonId = modalUiId(modalId, 'copy');
    const downloadButtonId = modalUiId(modalId, 'download');
    const titleElement = dom.resolve(`#${titleId}`, modal);
    const content = dom.resolve(`#${contentId}`, modal);
    if (!content) {
        throw new Error('Agent plan modal content element is missing');
    }

    const markdown = resolvePlanMarkdown(inputArguments);
    const title = inputArguments.title;
    if (titleElement instanceof HTMLElement) {
        titleElement.textContent = title && title.trim() ? title.trim() : i18n.t('chat.agent.plan.modalTitle');
    }

    const messageHost = inputArguments.host.rendering.messages;
    const rendered = messageHost.renderMarkdownContent(markdown);
    const renderedHtml = toTrustedUiHtml(rendered);
    dom.setHTML(content, renderedHtml, { escape: false });
    bindPlanCodeBlockCopyButtons(inputArguments.host, content, markdown);

    const copyButton = dom.resolve(`#${copyButtonId}`, modal);
    if (!(copyButton instanceof HTMLButtonElement)) {
        throw new Error('Agent plan modal copy button is missing');
    }
    const rebound = rebindButton(copyButton, 'Agent plan modal failed to rebind copy button');
    rebound.disabled = !markdown.trim();
    const handleCopyPlanClick = (): void => {
        const payload = markdown;
        if (!payload.trim()) {
            return;
        }
        void inputArguments.host.interaction.copyToClipboard(payload).catch((error): void => {
            const narrowed = ensureError(error);
            inputArguments.host.workflow.logWarning('Failed to copy agent plan markdown to clipboard', narrowed);
        });
    };
    rebound.addEventListener('click', handleCopyPlanClick);

    const downloadButton = dom.resolve(`#${downloadButtonId}`, modal);
    if (!(downloadButton instanceof HTMLButtonElement)) {
        throw new Error('Agent plan modal download button is missing');
    }
    const reboundDownload = rebindButton(downloadButton, 'Agent plan modal failed to rebind download button');
    reboundDownload.disabled = !markdown.trim();
    const handleDownloadPlanClick = (): void => {
        const payload = markdown;
        if (!payload.trim()) {
            return;
        }
        downloadFile(payload, buildPlanDownloadFilename(title), 'text/markdown;charset=utf-8');
        inputArguments.host.workflow.feedback.show(i18n.t('common.notifications.downloadStarted'), 'download');
    };
    reboundDownload.addEventListener('click', handleDownloadPlanClick);
    inputArguments.onModalOpen();
};

export { openAgentPlanModal };
export type { AgentPlanModalArguments };
