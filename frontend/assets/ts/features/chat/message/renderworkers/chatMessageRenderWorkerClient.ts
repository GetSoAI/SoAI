/* SoAI - Chat feature message render worker client [frontend/assets/ts/features/chat/message/renderworkers/chatMessageRenderWorkerClient.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { getLocalizationSnapshot } from '@core/localization/public.ts';
import { buildChatMessageWorkerTranslations } from '@features/chat/message/messageview/chatMessageTranslations.ts';
import { ChatMessageRenderWorkerPool } from '@features/chat/messagerenderworker/pool.ts';
import { buildIconKey, type IconKey, type RenderAssistantBodyFromMessageInput, type RenderInlineDetailsFromMessageInput, type WorkerResources } from '@features/chat/messagerenderworker/protocol.ts';
import { NEWS_HEADER_ICON_OPTIONS, NEWS_LINK_ICON_OPTIONS, NEWS_PLACEHOLDER_ICON_OPTIONS } from '@features/chat/message/messageview/assistantNewsIcons.ts';
import { PLAN_WIDGET_ACTION_ICON_OPTIONS, PLAN_WIDGET_HEADER_ICON_OPTIONS } from '@features/chat/message/messageview/assistantPlanWidgetIcons.ts';
import { WEATHER_FORECAST_ICON_OPTIONS, WEATHER_HEADER_ICON_OPTIONS, WEATHER_ICON_OPTIONS } from '@features/chat/message/messageview/weatherWidgetIcons.ts';

interface ChatMessageRenderWorkerClientDependencies {
    getIconHtml: (name: IconName, options?: IconOptions) => string;
}

class ChatMessageRenderWorkerClient {
    readonly #dependencies: ChatMessageRenderWorkerClientDependencies;
    readonly #renderWorkers: ChatMessageRenderWorkerPool;

    constructor(inputArguments: { dependencies: ChatMessageRenderWorkerClientDependencies }) {
        this.#dependencies = inputArguments.dependencies;
        const resources: WorkerResources = {
            translationsByKey: buildChatMessageWorkerTranslations(),
            iconsByKey: this.#buildWorkerIconsByKey(),
            localizationSnapshot: getLocalizationSnapshot()
        };
        this.#renderWorkers = new ChatMessageRenderWorkerPool(resources);
    }

    dispose(): void {
        this.#renderWorkers.dispose();
    }

    refreshResources(): void {
        const nextResources: WorkerResources = {
            translationsByKey: buildChatMessageWorkerTranslations(),
            iconsByKey: this.#buildWorkerIconsByKey(),
            localizationSnapshot: getLocalizationSnapshot()
        };
        this.#renderWorkers.updateResources(nextResources);
    }

    renderInlineDetailsFromMessage(inputArguments: RenderInlineDetailsFromMessageInput): Promise<{ html: string; context: RenderInlineDetailsFromMessageInput['context'] }> {
        return this.#renderWorkers.renderInlineDetailsFromMessage(inputArguments);
    }

    renderAssistantBodyFromMessage(inputArguments: RenderAssistantBodyFromMessageInput): Promise<{ html: string; context: RenderAssistantBodyFromMessageInput['context'] }> {
        return this.#renderWorkers.renderAssistantBodyFromMessage(inputArguments);
    }

    getWorkerCount(): number {
        return this.#renderWorkers.getWorkerCount();
    }

    #buildWorkerIconsByKey(): Record<IconKey, string> {
        const entries: Array<{ name: IconName; options?: IconOptions }> = [
            { name: 'copy', options: { size: 14, strokeWidth: 1.5 } },
            { name: 'external-link', options: { size: 14, strokeWidth: 1.5 } },
            { name: 'warning', options: { size: 14, strokeWidth: 1.5 } },
            { name: 'close', options: { size: 14, strokeWidth: 1.5 } },
            { name: 'close', options: { size: 16, strokeWidth: 1.7 } },
            { name: 'clock', options: { size: 16, strokeWidth: 1.7 } },
            { name: 'hardware', options: { size: 16, strokeWidth: 1.7 } },
            { name: 'thinking', options: { size: 16, strokeWidth: 1.7 } },
            { name: 'plugin', options: { size: 16, strokeWidth: 1.7 } },
            { name: 'agent-compact', options: { size: 16, strokeWidth: 1.7 } },
            { name: 'model-default', options: { size: 16, strokeWidth: 1.7 } },
            { name: 'chevron-right', options: { size: 10, strokeWidth: 4 } },
            { name: 'hourglass', options: { size: 8, strokeWidth: 1.5 } },
            { name: 'dot', options: { size: 10, strokeWidth: 1.5 } },
            { name: 'dot-leading', options: { size: 12, strokeWidth: 1.5 } },
            { name: 'model-default', options: { size: 16, strokeWidth: 1.5 } },
            { name: 'file-audio', options: { size: 16, strokeWidth: 1.5 } },
            { name: 'file-document', options: { size: 16, strokeWidth: 1.5 } },
            { name: 'file-generic', options: { size: 16, strokeWidth: 1.5 } },
            { name: 'file-image', options: { size: 16, strokeWidth: 1.5 } },
            { name: 'file-text', options: { size: 16, strokeWidth: 1.5 } },
            { name: 'file-video', options: { size: 16, strokeWidth: 1.5 } },
            { name: 'news', options: NEWS_HEADER_ICON_OPTIONS },
            { name: 'external-link', options: NEWS_LINK_ICON_OPTIONS },
            { name: 'file-image', options: NEWS_PLACEHOLDER_ICON_OPTIONS },
            { name: 'plan', options: PLAN_WIDGET_HEADER_ICON_OPTIONS },
            { name: 'plan', options: PLAN_WIDGET_ACTION_ICON_OPTIONS },
            { name: 'play', options: PLAN_WIDGET_ACTION_ICON_OPTIONS },
            { name: 'weather-cloud', options: WEATHER_HEADER_ICON_OPTIONS },
            { name: 'weather-cloud', options: WEATHER_ICON_OPTIONS },
            { name: 'weather-fog', options: WEATHER_ICON_OPTIONS },
            { name: 'weather-moon', options: WEATHER_ICON_OPTIONS },
            { name: 'weather-rain', options: WEATHER_ICON_OPTIONS },
            { name: 'weather-snow', options: WEATHER_ICON_OPTIONS },
            { name: 'weather-sun', options: WEATHER_ICON_OPTIONS },
            { name: 'weather-thunder', options: WEATHER_ICON_OPTIONS },
            { name: 'weather-cloud', options: WEATHER_FORECAST_ICON_OPTIONS },
            { name: 'weather-fog', options: WEATHER_FORECAST_ICON_OPTIONS },
            { name: 'weather-rain', options: WEATHER_FORECAST_ICON_OPTIONS },
            { name: 'weather-snow', options: WEATHER_FORECAST_ICON_OPTIONS },
            { name: 'weather-sun', options: WEATHER_FORECAST_ICON_OPTIONS },
            { name: 'weather-thunder', options: WEATHER_FORECAST_ICON_OPTIONS }
        ];
        const mapped: Record<IconKey, string> = {};
        for (const entry of entries) {
            const html = this.#dependencies.getIconHtml(entry.name, entry.options);
            const key = buildIconKey(entry.name, entry.options);
            mapped[key] = html;
        }
        return mapped;
    }
}

export { ChatMessageRenderWorkerClient };
export type { ChatMessageRenderWorkerClientDependencies };
