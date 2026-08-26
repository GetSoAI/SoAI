/* SoAI - MCP configuration help text resolver [frontend/assets/ts/features/settings/mcp/configitems/helpText.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { isArray, isBoolean, isNumber, isString } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

const KNOWN_HELP_TEXT_RESOLVERS: Readonly<Record<string, () => string>> = Object.freeze({
    'TOOLS.MCP.ENABLED': () => i18n.t('settings.mcp.configHelp.mcpEnabled'),
    'TOOLS.MCP.OAUTH.STATE_TOKEN_TTL_MS': () => i18n.t('settings.mcp.configHelp.oauthStateTokenTtlMs'),
    'TOOLS.MCP.OAUTH.REFRESH_SKEW_MS': () => i18n.t('settings.mcp.configHelp.oauthRefreshSkewMs'),
    'TOOLS.MCP.ELICITATION.WAIT_TIMEOUT_MS': () => i18n.t('settings.mcp.configHelp.elicitationWaitTimeoutMs'),
    'TOOLS.MCP.SUBAGENT.OBSERVE_TIMEOUT_MS': () => i18n.t('settings.mcp.configHelp.subagentObserveTimeoutMs'),
    'TOOLS.MCP.SECRET_PROMPT.HANDLE_STORE_MAX_TOTAL': () => i18n.t('settings.mcp.configHelp.secretPromptHandleStoreMaxTotal'),
    'TOOLS.MCP.SECRET_PROMPT.HANDLE_STORE_MAX_PER_USER': () => i18n.t('settings.mcp.configHelp.secretPromptHandleStoreMaxPerUser'),
    'TOOLS.MCP.SHELL.ENABLED': () => i18n.t('settings.mcp.configHelp.shellEnabled'),
    'TOOLS.MCP.SHELL.COMMAND_BLACKLIST': () => i18n.t('settings.mcp.configHelp.shellBlacklist'),
    'TOOLS.MCP.FILE_GUARD_READ_BEFORE_WRITE.ENABLED': () => i18n.t('settings.mcp.configHelp.fileGuardReadBeforeWriteEnabled'),
    'TOOLS.MCP.BROWSER.ENABLED': () => i18n.t('settings.mcp.configHelp.browserEnabled'),
    'TOOLS.MCP.BROWSER.HEADLESS': () => i18n.t('settings.mcp.configHelp.browserHeadless'),
    'TOOLS.MCP.BROWSER.AUTO_INSTALL': () => i18n.t('settings.mcp.configHelp.browserAutoInstall'),
    'TOOLS.MCP.BROWSER.AUTO_INSTALL_TIMEOUT_SEC': () => i18n.t('settings.mcp.configHelp.browserAutoInstallTimeoutSec'),
    'TOOLS.MCP.BROWSER.SESSION_SCOPE': () => i18n.t('settings.mcp.configHelp.browserSessionScope'),
    'TOOLS.MCP.BROWSER.DEFAULT_PROFILE': () => i18n.t('settings.mcp.configHelp.browserDefaultProfile'),
    'TOOLS.MCP.BROWSER.PROFILES': () => i18n.t('settings.mcp.configHelp.browserProfiles'),
    'TOOLS.MCP.BROWSER.CDP_CONNECT_TIMEOUT_MS': () => i18n.t('settings.mcp.configHelp.browserCdpConnectTimeoutMs'),
    'TOOLS.MCP.BROWSER.JS_EVAL_ENABLED': () => i18n.t('settings.mcp.configHelp.browserJsEvalEnabled'),
    'TOOLS.MCP.BROWSER.JS_EVAL_MAX_SCRIPT_CHARS': () => i18n.t('settings.mcp.configHelp.browserJsEvalMaxScriptChars'),
    'TOOLS.MCP.BROWSER.JS_EVAL_TIMEOUT_MS': () => i18n.t('settings.mcp.configHelp.browserJsEvalTimeoutMs'),
    'TOOLS.MCP.BROWSER.DEFAULT_NAV_TIMEOUT_SEC': () => i18n.t('settings.mcp.configHelp.browserDefaultNavTimeoutSec'),
    'TOOLS.MCP.BROWSER.DEFAULT_ACTION_TIMEOUT_SEC': () => i18n.t('settings.mcp.configHelp.browserDefaultActionTimeoutSec'),
    'TOOLS.MCP.BROWSER.TITLE_RETRY_ATTEMPTS': () => i18n.t('settings.mcp.configHelp.browserTitleRetryAttempts'),
    'TOOLS.MCP.BROWSER.TITLE_RETRY_DELAY_MS': () => i18n.t('settings.mcp.configHelp.browserTitleRetryDelayMs'),
    'TOOLS.MCP.BROWSER.MAX_WAIT_SEC': () => i18n.t('settings.mcp.configHelp.browserMaxWaitSec'),
    'TOOLS.MCP.BROWSER.RENDER_STABILIZE_MS': () => i18n.t('settings.mcp.configHelp.browserRenderStabilizeMs'),
    'TOOLS.MCP.BROWSER.MAX_CONCURRENT_PAGES': () => i18n.t('settings.mcp.configHelp.browserMaxConcurrentPages'),
    'TOOLS.MCP.BROWSER.BLOCK_IMAGES': () => i18n.t('settings.mcp.configHelp.browserBlockImages'),
    'TOOLS.MCP.BROWSER.BLOCK_FONTS': () => i18n.t('settings.mcp.configHelp.browserBlockFonts'),
    'TOOLS.MCP.BROWSER.BLOCK_MEDIA': () => i18n.t('settings.mcp.configHelp.browserBlockMedia'),
    'TOOLS.MCP.BROWSER.BLOCK_ADS': () => i18n.t('settings.mcp.configHelp.browserBlockAds'),
    'TOOLS.MCP.BROWSER.AD_BLOCK_LIST_URL': () => i18n.t('settings.mcp.configHelp.browserAdBlockListUrl'),
    'TOOLS.MCP.BROWSER.DNS_TIMEOUT_SEC': () => i18n.t('settings.mcp.configHelp.browserDnsTimeoutSec'),
    'TOOLS.MCP.BROWSER.SNAPSHOT_MAX_CHARS': () => i18n.t('settings.mcp.configHelp.browserSnapshotMaxChars'),
    'TOOLS.MCP.BROWSER.LOG_MAX_ENTRIES': () => i18n.t('settings.mcp.configHelp.browserLogMaxEntries'),
    'TOOLS.MCP.BROWSER.STORAGE_STATE_ENABLED': () => i18n.t('settings.mcp.configHelp.browserStorageStateEnabled'),
    'TOOLS.MCP.BROWSER.STORAGE_STATE_DIR': () => i18n.t('settings.mcp.configHelp.browserStorageStateDir'),
    'TOOLS.MCP.BROWSER.STORAGE_STATE_AUTOSAVE_ON_MUTATION': () => i18n.t('settings.mcp.configHelp.browserStorageStateAutosaveOnMutation'),
    'TOOLS.MCP.BROWSER.STORAGE_STATE_SAVE_THROTTLE_SEC': () => i18n.t('settings.mcp.configHelp.browserStorageStateSaveThrottleSec'),
    'TOOLS.MCP.BROWSER.STORAGE_STATE_SAVE_TIMEOUT_SEC': () => i18n.t('settings.mcp.configHelp.browserStorageStateSaveTimeoutSec'),
    'TOOLS.MCP.BROWSER.USER_DATA_DIR_BASE_DIR': () => i18n.t('settings.mcp.configHelp.browserUserDataDirBaseDir'),
    'TOOLS.MCP.BROWSER.USER_DATA_DIR_LOCK_TIMEOUT_SEC': () => i18n.t('settings.mcp.configHelp.browserUserDataDirLockTimeoutSec'),
    'TOOLS.MCP.BROWSER.PDF_MAX_INLINE_BYTES': () => i18n.t('settings.mcp.configHelp.browserPdfMaxInlineBytes'),
    'TOOLS.MCP.BROWSER.NETWORK_BODY_MAX_BYTES': () => i18n.t('settings.mcp.configHelp.browserNetworkBodyMaxBytes'),
    'TOOLS.MCP.WEB_FETCH.BLOCK_PRIVATE_NETWORK_EGRESS': () => i18n.t('settings.mcp.configHelp.webFetchBlockPrivateNetworkEgress'),
    'TOOLS.MCP.WEB_FETCH.DNS_TIMEOUT_SEC': () => i18n.t('settings.mcp.configHelp.webFetchDnsTimeoutSec'),
    'TOOLS.MCP.WEB_FETCH.DEFAULT_MAX_CHARS': () => i18n.t('settings.mcp.configHelp.webFetchDefaultMaxChars'),
    'TOOLS.MCP.WEB_FETCH.MAX_CHARS_LIMIT': () => i18n.t('settings.mcp.configHelp.webFetchMaxCharsLimit'),
    'TOOLS.MCP.HTTP_REQUEST.BLOCK_PRIVATE_NETWORK_EGRESS': () => i18n.t('settings.mcp.configHelp.httpRequestBlockPrivateNetworkEgress'),
    'TOOLS.MCP.HTTP_REQUEST.DNS_TIMEOUT_SEC': () => i18n.t('settings.mcp.configHelp.httpRequestDnsTimeoutSec'),
    'TOOLS.MCP.GENERATE_IMAGE.ENABLED': () => i18n.t('settings.mcp.configHelp.generateImageEnabled'),
    'TOOLS.MCP.GENERATE_IMAGE.ENGINE': () => i18n.t('settings.mcp.configHelp.generateImageEngine'),
    'TOOLS.MCP.GENERATE_IMAGE.DEFAULT_WIDTH': () => i18n.t('settings.mcp.configHelp.generateImageDefaultWidth'),
    'TOOLS.MCP.GENERATE_IMAGE.DEFAULT_HEIGHT': () => i18n.t('settings.mcp.configHelp.generateImageDefaultHeight'),
    'TOOLS.MCP.GENERATE_IMAGE.DEFAULT_STEPS': () => i18n.t('settings.mcp.configHelp.generateImageDefaultSteps'),
    'TOOLS.MCP.GENERATE_IMAGE.DEFAULT_CFG_SCALE': () => i18n.t('settings.mcp.configHelp.generateImageDefaultCfgScale'),
    'TOOLS.MCP.GENERATE_IMAGE.NEGATIVE_PROMPT': () => i18n.t('settings.mcp.configHelp.generateImageNegativePrompt'),
    'TOOLS.MCP.GENERATE_IMAGE.TIMEOUT_SEC': () => i18n.t('settings.mcp.configHelp.generateImageTimeoutSec'),
    'TOOLS.MCP.GENERATE_IMAGE.POLL_INTERVAL_SEC': () => i18n.t('settings.mcp.configHelp.generateImagePollIntervalSec'),
    'TOOLS.MCP.GENERATE_IMAGE.MAX_IMAGE_BYTES': () => i18n.t('settings.mcp.configHelp.generateImageMaxImageBytes'),
    'TOOLS.MCP.GENERATE_IMAGE.BLOCK_PRIVATE_NETWORK_EGRESS': () => i18n.t('settings.mcp.configHelp.generateImageBlockPrivateNetworkEgress'),
    'TOOLS.MCP.GENERATE_IMAGE.DNS_TIMEOUT_SEC': () => i18n.t('settings.mcp.configHelp.generateImageDnsTimeoutSec'),
    'TOOLS.MCP.GENERATE_IMAGE.AUTOMATIC1111.BASE_URL': () => i18n.t('settings.mcp.configHelp.automatic1111BaseUrl'),
    'TOOLS.MCP.GENERATE_IMAGE.AUTOMATIC1111.BASIC_AUTH': () => i18n.t('settings.mcp.configHelp.automatic1111BasicAuth'),
    'TOOLS.MCP.GENERATE_IMAGE.AUTOMATIC1111.SAMPLER_NAME': () => i18n.t('settings.mcp.configHelp.automatic1111SamplerName'),
    'TOOLS.MCP.GENERATE_IMAGE.AUTOMATIC1111.SCHEDULER': () => i18n.t('settings.mcp.configHelp.automatic1111Scheduler'),
    'TOOLS.MCP.GENERATE_IMAGE.AUTOMATIC1111.EXTRA_PARAMS_JSON': () => i18n.t('settings.mcp.configHelp.automatic1111ExtraParamsJson'),
    'TOOLS.MCP.GENERATE_IMAGE.COMFYUI.BASE_URL': () => i18n.t('settings.mcp.configHelp.comfyuiBaseUrl'),
    'TOOLS.MCP.GENERATE_IMAGE.COMFYUI.API_KEY': () => i18n.t('settings.mcp.configHelp.comfyuiApiKey'),
    'TOOLS.MCP.GENERATE_IMAGE.COMFYUI.MODEL': () => i18n.t('settings.mcp.configHelp.comfyuiModel'),
    'TOOLS.MCP.GENERATE_IMAGE.COMFYUI.WORKFLOW_JSON': () => i18n.t('settings.mcp.configHelp.comfyuiWorkflowJson'),
    'TOOLS.MCP.GENERATE_IMAGE.COMFYUI.WORKFLOW_NODES': () => i18n.t('settings.mcp.configHelp.comfyuiWorkflowNodes'),
    'TOOLS.MCP.GENERATE_IMAGE.COMFYUI.OUTPUT_NODE_IDS': () => i18n.t('settings.mcp.configHelp.comfyuiOutputNodeIds'),
    'TOOLS.MCP.GENERATE_IMAGE.AI_HORDE.BASE_URL': () => i18n.t('settings.mcp.configHelp.aiHordeBaseUrl'),
    'TOOLS.MCP.GENERATE_IMAGE.AI_HORDE.API_KEY': () => i18n.t('settings.mcp.configHelp.aiHordeApiKey'),
    'TOOLS.MCP.GENERATE_IMAGE.AI_HORDE.MODEL': () => i18n.t('settings.mcp.configHelp.aiHordeModel'),
    'TOOLS.MCP.GENERATE_IMAGE.AI_HORDE.MAX_GENERATION_WAIT_SEC': () => i18n.t('settings.mcp.configHelp.aiHordeMaxGenerationWaitSec'),
    'TOOLS.MCP.WEATHER.ENABLED': () => i18n.t('settings.mcp.configHelp.weatherEnabled'),
    'TOOLS.MCP.WEATHER.GEOCODING_BASE_URL': () => i18n.t('settings.mcp.configHelp.weatherGeocodingBaseUrl'),
    'TOOLS.MCP.WEATHER.FORECAST_BASE_URL': () => i18n.t('settings.mcp.configHelp.weatherForecastBaseUrl'),
    'TOOLS.MCP.WEATHER.TIMEOUT_SEC': () => i18n.t('settings.mcp.configHelp.weatherTimeoutSec'),
    'TOOLS.MCP.WEATHER.MAX_RESPONSE_BYTES': () => i18n.t('settings.mcp.configHelp.weatherMaxResponseBytes'),
    'TOOLS.MCP.WEATHER.BLOCK_PRIVATE_NETWORK_EGRESS': () => i18n.t('settings.mcp.configHelp.weatherBlockPrivateNetworkEgress'),
    'TOOLS.MCP.WEATHER.DNS_TIMEOUT_SEC': () => i18n.t('settings.mcp.configHelp.weatherDnsTimeoutSec'),
    'TOOLS.MCP.READ_IMAGE.MAX_SOURCE_BYTES': () => i18n.t('settings.mcp.configHelp.readImageMaxSourceBytes'),
    'TOOLS.MCP.READ_IMAGE.MAX_ENCODED_CHARS': () => i18n.t('settings.mcp.configHelp.readImageMaxEncodedChars'),
    'TOOLS.MCP.READ_IMAGE.MAX_PIXELS': () => i18n.t('settings.mcp.configHelp.readImageMaxPixels'),
    'TOOLS.MCP.READ_IMAGE.JPEG_QUALITY': () => i18n.t('settings.mcp.configHelp.readImageJpegQuality'),
    'TOOLS.MCP.READ_VIDEO.WHISPER_MODEL': () => i18n.t('settings.mcp.configHelp.readVideoWhisperModel'),
    'TOOLS.MCP.HOST_MODE.ENABLED': () => i18n.t('settings.mcp.configHelp.hostModeEnabled'),
    'TOOLS.MCP.HOST_MODE.AUTO_CONNECT_ON_STARTUP': () => i18n.t('settings.mcp.configHelp.hostModeAutoConnectOnStartup'),
    'TOOLS.MCP.HOST_MODE.RECONNECT_DELAY_SEC': () => i18n.t('settings.mcp.configHelp.hostModeReconnectDelaySec'),
    'TOOLS.MCP.HOST_MODE.MAX_RECONNECT_ATTEMPTS': () => i18n.t('settings.mcp.configHelp.hostModeMaxReconnectAttempts'),
    'TOOLS.MCP.HOST_MODE.ROOTS': () => i18n.t('settings.mcp.configHelp.hostModeRoots'),
    'TOOLS.MCP.HOST_MODE.ROOTS_LIST_CHANGED': () => i18n.t('settings.mcp.configHelp.hostModeRootsListChanged'),
    'TOOLS.MCP.HOST_MODE.SAMPLING.ENABLED': () => i18n.t('settings.mcp.configHelp.hostModeSamplingEnabled'),
    'TOOLS.MCP.HOST_MODE.SAMPLING.DEFAULT_MODEL': () => i18n.t('settings.mcp.configHelp.hostModeSamplingDefaultModel'),
    'TOOLS.MCP.HOST_MODE.SAMPLING.INFERENCE_TIMEOUT_SEC': () => i18n.t('settings.mcp.configHelp.hostModeSamplingInferenceTimeoutSec'),
    'TOOLS.MCP.HOST_MODE.ELICITATION.ENABLED': () => i18n.t('settings.mcp.configHelp.hostModeElicitationEnabled'),
    'TOOLS.MCP.SERVER_MODE.ENABLED': () => i18n.t('settings.mcp.configHelp.serverModeEnabled'),
    'TOOLS.MCP.SERVER_MODE.EXPOSED_TOOLS': () => i18n.t('settings.mcp.configHelp.serverModeExposedTools'),
    'TOOLS.MCP.SERVER_MODE.EXPOSED_RESOURCES': () => i18n.t('settings.mcp.configHelp.serverModeExposedResources'),
    'TOOLS.MCP.SERVER_MODE.EXPOSED_PROMPTS': () => i18n.t('settings.mcp.configHelp.serverModeExposedPrompts'),
    'TOOLS.MCP.SERVER_MODE.ALLOWED_ORIGINS': () => i18n.t('settings.mcp.configHelp.serverModeAllowedOrigins'),
    'TOOLS.MCP.SERVER_MODE.LIST_CHANGED_NOTIFICATIONS': () => i18n.t('settings.mcp.configHelp.serverModeListChangedNotifications'),
    'TOOLS.MCP.SERVER_MODE.SSE_REPLAY_BUFFER_SIZE': () => i18n.t('settings.mcp.configHelp.serverModeSseReplayBufferSize'),
    'TOOLS.MCP.TASKS.ENABLED': () => i18n.t('settings.mcp.configHelp.tasksEnabled'),
    'TOOLS.MCP.TASKS.DEFAULT_TTL_SEC': () => i18n.t('settings.mcp.configHelp.tasksDefaultTtlSec'),
    'TOOLS.MCP.TASKS.MAX_CONCURRENT_PER_CLIENT': () => i18n.t('settings.mcp.configHelp.tasksMaxConcurrentPerClient'),
    'TOOLS.MCP.TASKS.PROXY_TIMEOUT_SEC': () => i18n.t('settings.mcp.configHelp.tasksProxyTimeoutSec'),
    'TOOLS.MCP.TASKS.TOOL_TIMEOUT_SEC': () => i18n.t('settings.mcp.configHelp.tasksToolTimeoutSec'),
    'TOOLS.MCP.CLIENT_NOTIFICATION_QUEUE_SIZE': () => i18n.t('settings.mcp.configHelp.clientNotificationQueueSize'),
    'TOOLS.MCP.SESSION_TTL_SEC': () => i18n.t('settings.mcp.configHelp.sessionTtlSec'),
    'TOOLS.MCP.SESSION_SWEEP_INTERVAL_SEC': () => i18n.t('settings.mcp.configHelp.sessionSweepIntervalSec'),
    'TOOLS.MCP.READ_VIDEO.DEFAULT_FRAMES_PER_SECOND': () => i18n.t('settings.mcp.configHelp.readVideoDefaultFramesPerSecond'),
    'TOOLS.MCP.READ_VIDEO.MAX_FRAMES_PER_SECOND': () => i18n.t('settings.mcp.configHelp.readVideoMaxFramesPerSecond'),
    'TOOLS.MCP.READ_VIDEO.FRAME_PAGE_SIZE': () => i18n.t('settings.mcp.configHelp.readVideoFramePageSize'),
    'TOOLS.MCP.READ_VIDEO.MAX_FRAME_PIXELS': () => i18n.t('settings.mcp.configHelp.readVideoMaxFramePixels'),
    'TOOLS.MCP.READ_VIDEO.JPEG_QUALITY': () => i18n.t('settings.mcp.configHelp.readVideoJpegQuality'),
    'TOOLS.MCP.READ_VIDEO.INCLUDE_AUDIO_DEFAULT': () => i18n.t('settings.mcp.configHelp.readVideoIncludeAudioDefault'),
    'TOOLS.MCP.READ_VIDEO.AUDIO_CHUNK_SECONDS': () => i18n.t('settings.mcp.configHelp.readVideoAudioChunkSeconds'),
    'TOOLS.MCP.READ_VIDEO.JOB_RETENTION_HOURS': () => i18n.t('settings.mcp.configHelp.readVideoJobRetentionHours'),
    'TOOLS.MCP.READ_VIDEO.MAX_ACTIVE_JOBS': () => i18n.t('settings.mcp.configHelp.readVideoMaxActiveJobs'),
    'TOOLS.MCP.READ_VIDEO.TEMP_RESERVATION_SAFETY_MULTIPLIER': () => i18n.t('settings.mcp.configHelp.readVideoTempReservationSafetyMultiplier'),
    'TOOLS.MCP.READ_VIDEO.VIDEO_PREVIEW_SECONDS': () => i18n.t('settings.mcp.configHelp.readVideoPreviewSeconds'),
    'TOOLS.MCP.READ_VIDEO.VIDEO_PREVIEW_MAX_PIXELS': () => i18n.t('settings.mcp.configHelp.readVideoPreviewMaxPixels'),
    'TOOLS.MCP.READ_VIDEO.VIDEO_PREVIEW_CRF': () => i18n.t('settings.mcp.configHelp.readVideoPreviewCrf'),
    'TOOLS.MCP.READ_VIDEO.VIDEO_PREVIEW_MAX_BYTES': () => i18n.t('settings.mcp.configHelp.readVideoPreviewMaxBytes'),
    'TOOLS.MCP.READ_VIDEO.PROBE_TIMEOUT_SEC': () => i18n.t('settings.mcp.configHelp.readVideoProbeTimeoutSec'),
    'TOOLS.MCP.READ_VIDEO.FRAME_EXTRACTION_TIMEOUT_SEC': () => i18n.t('settings.mcp.configHelp.readVideoFrameExtractionTimeoutSec'),
    'TOOLS.MCP.READ_VIDEO.AUDIO_EXTRACTION_TIMEOUT_SEC': () => i18n.t('settings.mcp.configHelp.readVideoAudioExtractionTimeoutSec'),
    'TOOLS.MCP.READ_VIDEO.PREVIEW_EXTRACTION_TIMEOUT_SEC': () => i18n.t('settings.mcp.configHelp.readVideoPreviewExtractionTimeoutSec'),
    'TOOLS.MCP.READ_VIDEO.LIVE_PROGRESS_MIN_INTERVAL_MS': () => i18n.t('settings.mcp.configHelp.readVideoLiveProgressMinIntervalMs')
});

const resolveKnownMcpConfigHelpText = (path: string): string | null => {
    return KNOWN_HELP_TEXT_RESOLVERS[path.toUpperCase()]?.() ?? null;
};

const resolveFallbackHelpText = (key: string, value: JsonValue): string => {
    const normalizedKey = key.toUpperCase();
    if (normalizedKey === 'ENABLED') return i18n.t('settings.mcp.configHelp.fallbackEnabled');
    if (normalizedKey.endsWith('BASE_URL')) return i18n.t('settings.mcp.configHelp.fallbackBaseUrl');
    if (normalizedKey.endsWith('API_KEY')) return i18n.t('settings.mcp.configHelp.fallbackApiKey');
    if (normalizedKey.endsWith('TIMEOUT_SEC') || normalizedKey.endsWith('TIMEOUT_MS')) return i18n.t('settings.mcp.configHelp.fallbackTimeout');
    if (normalizedKey.includes('MAX_') || normalizedKey.includes('_MAX_')) return i18n.t('settings.mcp.configHelp.fallbackMaximum');
    if (normalizedKey.includes('INTERVAL') || normalizedKey.includes('DELAY')) return i18n.t('settings.mcp.configHelp.fallbackInterval');
    if (isArray(value)) return i18n.t('settings.mcp.configHelp.fallbackJsonList');
    if (isBoolean(value)) return i18n.t('settings.mcp.configHelp.fallbackBoolean');
    if (isNumber(value)) return i18n.t('settings.mcp.configHelp.fallbackNumber');
    if (isString(value)) return i18n.t('settings.mcp.configHelp.fallbackText');
    return i18n.t('settings.mcp.configHelp.fallbackJson');
};

const resolveMcpConfigHelpText = (path: string, key: string, value: JsonValue): string => {
    return resolveKnownMcpConfigHelpText(path) ?? resolveFallbackHelpText(key, value);
};

export { resolveMcpConfigHelpText };
