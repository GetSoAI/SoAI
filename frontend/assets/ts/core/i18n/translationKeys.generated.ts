/* SoAI - Frontend core Translation root declaration catalog [frontend/assets/ts/core/i18n/translationKeys.generated.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AboutTranslationKey } from '@core/i18n/translationkeys/about.generated.ts';
import type { AppTranslationKey } from '@core/i18n/translationkeys/app.generated.ts';
import type { AutomationTranslationKey } from '@core/i18n/translationkeys/automation.generated.ts';
import type { ChartsTranslationKey } from '@core/i18n/translationkeys/charts.generated.ts';
import type { ChatTranslationKey } from '@core/i18n/translationkeys/chat.generated.ts';
import type { CollectionsTranslationKey } from '@core/i18n/translationkeys/collections.generated.ts';
import type { CommonTranslationKey } from '@core/i18n/translationkeys/common.generated.ts';
import type { ContentPreviewTranslationKey } from '@core/i18n/translationkeys/contentPreview.generated.ts';
import type { DashboardTranslationKey } from '@core/i18n/translationkeys/dashboard.generated.ts';
import type { DetachedTranslationKey } from '@core/i18n/translationkeys/detached.generated.ts';
import type { DocumentsTranslationKey } from '@core/i18n/translationkeys/documents.generated.ts';
import type { FileExplorerTranslationKey } from '@core/i18n/translationkeys/fileExplorer.generated.ts';
import type { HardwareTranslationKey } from '@core/i18n/translationkeys/hardware.generated.ts';
import type { HeaderTranslationKey } from '@core/i18n/translationkeys/header.generated.ts';
import type { HelpTranslationKey } from '@core/i18n/translationkeys/help.generated.ts';
import type { LicensingTranslationKey } from '@core/i18n/translationkeys/licensing.generated.ts';
import type { LiveStatusOverlayTranslationKey } from '@core/i18n/translationkeys/liveStatusOverlay.generated.ts';
import type { LoginTranslationKey } from '@core/i18n/translationkeys/login.generated.ts';
import type { LogsTranslationKey } from '@core/i18n/translationkeys/logs.generated.ts';
import type { MetricsTranslationKey } from '@core/i18n/translationkeys/metrics.generated.ts';
import type { ModelDetailTranslationKey } from '@core/i18n/translationkeys/modelDetail.generated.ts';
import type { ModelsTranslationKey } from '@core/i18n/translationkeys/models.generated.ts';
import type { NavTranslationKey } from '@core/i18n/translationkeys/nav.generated.ts';
import type { NotificationsTranslationKey } from '@core/i18n/translationkeys/notifications.generated.ts';
import type { PageOutletTranslationKey } from '@core/i18n/translationkeys/pageOutlet.generated.ts';
import type { PagesTranslationKey } from '@core/i18n/translationkeys/pages.generated.ts';
import type { PluginsTranslationKey } from '@core/i18n/translationkeys/plugins.generated.ts';
import type { PowerTranslationKey } from '@core/i18n/translationkeys/power.generated.ts';
import type { PromptsTranslationKey } from '@core/i18n/translationkeys/prompts.generated.ts';
import type { RestartOverlayTranslationKey } from '@core/i18n/translationkeys/restartOverlay.generated.ts';
import type { RichTextTranslationKey } from '@core/i18n/translationkeys/richText.generated.ts';
import type { RouterTranslationKey } from '@core/i18n/translationkeys/router.generated.ts';
import type { SearchTranslationKey } from '@core/i18n/translationkeys/search.generated.ts';
import type { SettingsTranslationKey } from '@core/i18n/translationkeys/settings.generated.ts';
import type { StatusCatalogTranslationKey } from '@core/i18n/translationkeys/statusCatalog.generated.ts';
import type { SyntaxHighlighterTranslationKey } from '@core/i18n/translationkeys/syntaxHighlighter.generated.ts';
import type { TabsTranslationKey } from '@core/i18n/translationkeys/tabs.generated.ts';
import type { TaskManagerTranslationKey } from '@core/i18n/translationkeys/taskManager.generated.ts';
import type { TerminalTranslationKey } from '@core/i18n/translationkeys/terminal.generated.ts';
import type { UiTranslationKey } from '@core/i18n/translationkeys/ui.generated.ts';
import type { UpdatesTranslationKey } from '@core/i18n/translationkeys/updates.generated.ts';
import type { WizardTranslationKey } from '@core/i18n/translationkeys/wizard.generated.ts';

export type TranslationKey =
    | AboutTranslationKey
    | AppTranslationKey
    | AutomationTranslationKey
    | ChartsTranslationKey
    | ChatTranslationKey
    | CollectionsTranslationKey
    | CommonTranslationKey
    | ContentPreviewTranslationKey
    | DashboardTranslationKey
    | DetachedTranslationKey
    | DocumentsTranslationKey
    | FileExplorerTranslationKey
    | HardwareTranslationKey
    | HeaderTranslationKey
    | HelpTranslationKey
    | LicensingTranslationKey
    | LiveStatusOverlayTranslationKey
    | LoginTranslationKey
    | LogsTranslationKey
    | MetricsTranslationKey
    | ModelDetailTranslationKey
    | ModelsTranslationKey
    | NavTranslationKey
    | NotificationsTranslationKey
    | PageOutletTranslationKey
    | PagesTranslationKey
    | PluginsTranslationKey
    | PowerTranslationKey
    | PromptsTranslationKey
    | RestartOverlayTranslationKey
    | RichTextTranslationKey
    | RouterTranslationKey
    | SearchTranslationKey
    | SettingsTranslationKey
    | StatusCatalogTranslationKey
    | SyntaxHighlighterTranslationKey
    | TabsTranslationKey
    | TaskManagerTranslationKey
    | TerminalTranslationKey
    | UiTranslationKey
    | UpdatesTranslationKey
    | WizardTranslationKey;

export type PluralBaseKey =
    | 'chat.attachments.overflowHidden'
    | 'chat.attachments.soaiPathLinkAdded'
    | 'chat.attachModal.uploadProcessing'
    | 'chat.attachModal.uploadSummary'
    | 'chat.inlinePreviews.folderMore'
    | 'chat.inlinePreviews.folderSummary'
    | 'common.time.units.day.long'
    | 'common.time.units.hour.long'
    | 'common.time.units.minute.long'
    | 'metrics.modelTable.count'
    | 'metrics.plugin_health.count'
    | 'models.metrics.constituentModelsShortCount'
    | 'models.stats.externalProviders'
    | 'models.stats.loaded'
    | 'models.stats.local_models'
    | 'models.stats.requests'
    | 'models.stats.totalModels'
    | 'models.stats.virtualModels'
    | 'plugins.confirmations.stopAllMessage'
    | 'plugins.stats.activePlugins'
    | 'plugins.stats.concurrentPlugins'
    | 'plugins.stats.persistentPlugins'
    | 'plugins.stats.totalPlugins'
    | 'taskManager.confirmations.cancelOperationsMessage'
    | 'taskManager.confirmations.stopAllMessage'
    | 'taskManager.header.taskCounter'
    | 'taskManager.notifications.cancelOperationsFailed'
    | 'taskManager.notifications.cancelOperationsSuccess'
    | 'wizard.completion.summary.plugins.installed';

export type BaseTranslationKey = TranslationKey;
export type BasePluralBaseKey = PluralBaseKey;
