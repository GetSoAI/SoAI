/* SoAI - Models page support contracts [frontend/assets/ts/pages/models/contracts/ModelPageSupport.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { MODEL_STATUS_LOADING_VALUES, PLUGIN_STATUS_ERROR_VALUES, PLUGIN_STATUS_LOADING_VALUES, PLUGIN_STATUS_READY_VALUES } from '@core/models/modelStatus.ts';
import { isNullOrUndefined } from '@core/typeGuards.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import { MODELS_ACTION_DELETE, MODELS_ACTION_EDIT_MODEL, MODELS_ACTION_EDIT_PARAMETERS, MODELS_ACTION_EDIT_VIRTUAL, MODELS_ACTION_STOP_MODEL, MODELS_ACTION_TOGGLE_ENABLED } from '@pages/models/actions.ts';

interface ModelsActionHost {
    getItemCardId(model: ModelRecord): string;
    showEditVirtualModelForm(vmName: string): void | Promise<void>;
    showEditModelModal(model: ModelRecord): Promise<void>;
    deleteModel(identifier: string | number): Promise<void>;
    stopModel(model: ModelRecord): Promise<void>;
    toggleModelEnabled(model: ModelRecord, event?: Event): Promise<void>;
    navigateToModelDetail(model: ModelRecord, options?: { tab?: string; action?: string }): void;
}

const ACTIVE_MODEL_STATUSES: Readonly<string[]> = Object.freeze(['READY', 'PROCESSING']);

const PROVIDER_LOGO_PATHS: Readonly<Record<string, string>> = Object.freeze({
    ollama: 'img/logo/ollama-plugin-logo.png',
    vllm: 'img/logo/vllm-plugin-logo.png',
    llamacpp: 'img/logo/llamacpp-plugin-logo.png',
    external: 'img/logo/external-plugin-logo.png',
    ctranslate2: 'img/logo/ctranslate2-plugin-logo.png',
    embedding: 'img/logo/embedding-plugin-logo.png',
    melotts: 'img/logo/melotts-plugin-logo.png',
    whisper: 'img/logo/whisper-plugin-logo.png'
});
const BUILTIN_LOGO_FILES: Readonly<Record<string, string>> = Object.freeze({
    ollama: 'ollama-plugin-logo.png',
    vllm: 'vllm-plugin-logo.png',
    llamacpp: 'llamacpp-plugin-logo.png',
    external: 'external-plugin-logo.png',
    ctranslate2: 'ctranslate2-plugin-logo.png',
    embedding: 'embedding-plugin-logo.png',
    melotts: 'melotts-plugin-logo.png',
    whisper: 'whisper-plugin-logo.png'
});

const THIRD_PARTY_MODEL_LOGOS: Readonly<Record<string, string>> = Object.freeze({
    default: 'img/logo/third-party-model-logo.png',
    external: 'img/logo/third-party-model-external-logo.png'
});
const VIRTUAL_MODEL_LOGO = 'img/logo/virtual-model-logo.png';

type ModelActionHandler = (host: ModelsActionHost, model: ModelRecord, event?: Event) => void | Promise<void>;

const MODEL_ACTION_HANDLERS = Object.freeze({
    [MODELS_ACTION_DELETE](host: ModelsActionHost, model: ModelRecord, _event?: Event): Promise<void> | undefined {
        const identifier = model?.universalId ?? host.getItemCardId(model);
        return isNullOrUndefined(identifier) ? undefined : host.deleteModel(String(identifier));
    },
    [MODELS_ACTION_EDIT_MODEL]: (host: ModelsActionHost, model: ModelRecord, _event?: Event) => host.showEditModelModal(model),
    [MODELS_ACTION_EDIT_PARAMETERS]: (host: ModelsActionHost, model: ModelRecord, _event?: Event) => host.navigateToModelDetail(model),
    [MODELS_ACTION_EDIT_VIRTUAL]: (host: ModelsActionHost, model: ModelRecord, _event?: Event) => host.showEditVirtualModelForm(model?.name || model?.id || ''),
    [MODELS_ACTION_STOP_MODEL]: (host: ModelsActionHost, model: ModelRecord, _event?: Event) => host.stopModel(model),
    [MODELS_ACTION_TOGGLE_ENABLED]: (host: ModelsActionHost, model: ModelRecord, event?: Event) => {
        return host.toggleModelEnabled(model, event);
    }
} satisfies Record<string, ModelActionHandler>);

export { ACTIVE_MODEL_STATUSES, BUILTIN_LOGO_FILES, MODEL_ACTION_HANDLERS, MODEL_STATUS_LOADING_VALUES, PLUGIN_STATUS_ERROR_VALUES, PLUGIN_STATUS_LOADING_VALUES, PLUGIN_STATUS_READY_VALUES, PROVIDER_LOGO_PATHS, THIRD_PARTY_MODEL_LOGOS, VIRTUAL_MODEL_LOGO };

export type { ModelsActionHost };
