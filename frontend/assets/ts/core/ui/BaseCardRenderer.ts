/* SoAI - Shared UI base card renderer [frontend/assets/ts/core/ui/BaseCardRenderer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { toTrustedTableBodyHtml, type TrustedHtml } from '@core/security/public.ts';
import { getDomDocument } from '@core/dom/domEnvironment.ts';
import { createHtmlTableRow } from '@core/dom/html.ts';
import { isArray, isString } from '@core/typeGuards.ts';
import { createCardFactory } from '@core/ui/collectionLayoutPrimitives.ts';
import type { ButtonConfig, CollectionCardFactoryContract, CollectionLayoutBuilderContract, IconOptions } from '@core/uiprimitives/types.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';

interface CardRendererHost {
    dom: {
        createFragment(markup: TrustedHtml): DocumentFragment;
    };
    sanitizeClassName(className: string, type: string): string;
}

interface RoundButtonConfig {
    className?: string;
    action?: string;
    iconName?: IconName;
    iconOptions?: IconOptions;
    label?: string;
}

interface BaseCardRendererOptions {
    host?: CardRendererHost | undefined;
}

class BaseCardRenderer<TItem = JsonValue | null | undefined, TData = JsonObject | null> {
    protected host: CardRendererHost;
    protected cards: CollectionCardFactoryContract;
    protected builder: CollectionLayoutBuilderContract;

    constructor(options: BaseCardRendererOptions = {}) {
        const { host } = options;
        if (!host) {
            throw new Error(`${this.constructor.name} requires a host instance`);
        }
        this.host = host;
        this.cards = createCardFactory(host);
        this.builder = this.cards.getBuilder();
    }

    materialize(markup: TrustedHtml): Element | null {
        const fragment = this.host.dom.createFragment(markup);
        return fragment.firstElementChild;
    }

    materializeTableRow(markup: string): HTMLTableRowElement {
        const documentRef = getDomDocument();
        const tableBodyMarkup = toTrustedTableBodyHtml(markup);
        return createHtmlTableRow({ documentRef, html: tableBodyMarkup });
    }

    buildClassList(classes: string[] | null | undefined): string {
        const source = isArray(classes) ? classes : [];
        return source
            .flatMap((cls) => (isString(cls) ? cls.trim().split(/\s+/) : []))
            .filter(Boolean)
            .map((cls) => this.host.sanitizeClassName(cls, 'value'))
            .join(' ');
    }

    buildStatusClasses(value: string | null | undefined): string[] {
        if (!value) return [];
        return String(value).split(/\s+/).filter(Boolean);
    }

    protected requireCardIcon(name: string, options?: IconOptions): string {
        const iconMarkup = this.cards.icon(name, options);
        if (!isString(iconMarkup) || !iconMarkup.trim()) {
            throw new Error(`${this.constructor.name} requires icon "${name}"`);
        }
        return iconMarkup;
    }

    createRoundButton(config: RoundButtonConfig | null | undefined): ButtonConfig {
        if (!config) {
            throw new TypeError('Round button config must be a record');
        }
        const className = isString(config.className) ? config.className : '';
        const action = isString(config.action) ? config.action : '';
        const iconName = isString(config.iconName) ? config.iconName : '';
        const safeIconOptions = config.iconOptions ?? {};
        const translatedLabel = isString(config.label) ? config.label : '';

        if (!iconName) {
            throw new Error('Round button config requires iconName');
        }
        this.requireCardIcon(iconName, safeIconOptions);

        const button: ButtonConfig = {
            tag: 'button',
            type: 'button',
            icon: {
                name: iconName,
                options: safeIconOptions
            }
        };
        if (className) {
            button.className = className;
        }
        if (action) {
            button.dataset = { action };
        }
        if (translatedLabel) {
            button.aria = { label: translatedLabel };
            button.dataset = { ...(button.dataset ?? {}), tooltip: translatedLabel };
        }
        return button;
    }

    render(_item: TItem): Element | string | TrustedHtml | null {
        throw new Error(`${this.constructor.name} must implement render()`);
    }

    prepareCardData(_item: TItem): TData | null {
        throw new Error(`${this.constructor.name} must implement prepareCardData()`);
    }

    buildContent(_item: TItem, _data: TData | null): string | TrustedHtml | null {
        throw new Error(`${this.constructor.name} must implement buildContent()`);
    }

    buildActionButtons(_item?: TItem): string | string[] | ButtonConfig[] | null {
        throw new Error(`${this.constructor.name} must implement buildActionButtons()`);
    }
}

export { BaseCardRenderer };
export type { CardRendererHost, RoundButtonConfig, BaseCardRendererOptions };
