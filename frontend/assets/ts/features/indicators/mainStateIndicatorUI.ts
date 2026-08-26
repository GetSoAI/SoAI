/* SoAI - Indicators feature main state indicator UI [frontend/assets/ts/features/indicators/mainStateIndicatorUI.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { requireDocument } from '@core/environment/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { MAIN_STATE_DEFINITIONS, type StatusDefinition } from '@core/state/constants.ts';
import { isString } from '@core/typeGuards.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';

const DEFAULT_STATE = 'UNKNOWN';
const DEFAULT_VARIANT = 'sidebar';

interface VariantDefinition {
    tag: string;
    className: string;
    labelClass: string;
    iconWrapperClass: string;
    iconContainerClass: string;
    indicatorClass: string;
    role: string;
    ariaLive: string;
    id: string;
}

interface IndicatorVariants {
    sidebar: Readonly<VariantDefinition>;
    dashboard: Readonly<VariantDefinition>;
    [key: string]: Readonly<VariantDefinition>;
}

const INDICATOR_VARIANTS: Readonly<IndicatorVariants> = Object.freeze({
    sidebar: Object.freeze({
        tag: 'button',
        className: 'sidebar-link main-state-indicator',
        labelClass: 'sidebar-label',
        iconWrapperClass: 'ui-icon-button sidebar-icon-button',
        iconContainerClass: 'sidebar-icon',
        indicatorClass: '',
        role: 'status',
        ariaLive: 'polite',
        id: 'main-state-indicator'
    }),
    dashboard: Object.freeze({
        tag: 'div',
        className: 'dashboard-main-state',
        labelClass: 'status-label',
        iconWrapperClass: 'status-main-indicator',
        iconContainerClass: '',
        indicatorClass: 'status-indicator',
        role: 'status',
        ariaLive: 'polite',
        id: ''
    })
});

interface ResolvedVariant {
    key: string;
    definition: Readonly<VariantDefinition>;
}

interface MainStateInfo {
    state: string;
    color: string;
    description: string;
}

interface CreateOptions {
    variant?: string | undefined;
}

const resolveVariant = (variant: string | null | undefined): ResolvedVariant => {
    const key = variant ?? DEFAULT_VARIANT;
    const definition = INDICATOR_VARIANTS[key];
    if (!definition) {
        throw new Error('Unsupported main state indicator variant');
    }
    return { key, definition };
};

const normalizeMainState = (value: string | null): string => {
    if (isString(value)) {
        const normalized = value.trim().toUpperCase();
        return normalized || DEFAULT_STATE;
    }
    return DEFAULT_STATE;
};

const resolveDefinition = (state: string | null): { normalized: string; definition: StatusDefinition } => {
    const normalized = normalizeMainState(state);
    const definitions = MAIN_STATE_DEFINITIONS;
    const fallback = definitions[DEFAULT_STATE];
    if (!fallback) {
        throw new Error(`Main state definition "${DEFAULT_STATE}" is missing`);
    }
    const definition = definitions[normalized] ?? fallback;
    return { normalized, definition };
};

const resolveDefinitionDescription = (state: string): string => {
    switch (state) {
        case 'STARTING':
            return i18n.t('statusCatalog.main.starting');
        case 'READY':
            return i18n.t('statusCatalog.main.ready');
        case 'ACTIVE':
            return i18n.t('statusCatalog.main.active');
        case 'ERROR':
            return i18n.t('statusCatalog.main.error');
        case 'RECONNECTING':
            return i18n.t('statusCatalog.main.reconnecting');
        case 'STOPPING':
            return i18n.t('statusCatalog.main.stopping');
        case 'UNKNOWN':
            return i18n.t('statusCatalog.main.offline');
    }
    throw new Error(`Unsupported main state "${state}"`);
};

const getMainStateInfo = (state: string | null): MainStateInfo => {
    const { normalized, definition } = resolveDefinition(state);
    return { state: normalized, color: definition.color, description: resolveDefinitionDescription(normalized) };
};

const resolveLabelClass = (element: HTMLElement | null): string => element?.dataset?.['mainStateLabelClass'] || INDICATOR_VARIANTS[DEFAULT_VARIANT].labelClass;

const optionalChildHTMLElement = (parent: Element, selector: string): HTMLElement | null => {
    const element = dom.resolve(selector, parent);
    if (element === null) return null;
    if (element instanceof HTMLElement) return element;
    throw new Error(`Main state indicator expected HTMLElement for selector: ${selector}`);
};

const ensureLabel = (element: HTMLElement): HTMLElement => {
    const labelClass = resolveLabelClass(element);
    let label = optionalChildHTMLElement(element, `.${labelClass}`);
    if (!label) {
        const doc = element.ownerDocument ?? requireDocument();
        label = doc.createElement('span');
        label.className = labelClass;
        element.appendChild(label);
    } else {
        label.className = labelClass;
    }
    return label;
};

const resolveIndicatorClassName = (element: HTMLElement | null): string => {
    const { definition } = resolveVariant(element?.dataset?.['mainStateVariant']);
    const classes = ['status-indicator'];
    if (definition.indicatorClass) {
        classes.push(definition.indicatorClass);
    }
    return classes.join(' ');
};

const updateColor = (element: HTMLElement, color: string): void => {
    const variant = element?.dataset?.['mainStateVariant'];
    if (variant === 'dashboard') {
        element.dataset['color'] = color;
    } else {
        const indicator = optionalChildHTMLElement(element, '.status-indicator');
        if (!indicator) {
            return;
        }
        indicator.className = resolveIndicatorClassName(element);
        indicator.classList.add(color);
    }
};

const updateLabel = (element: HTMLElement, description: string): void => {
    const variant = element?.dataset?.['mainStateVariant'];
    if (variant === 'dashboard') {
        const textElement = optionalChildHTMLElement(element, '.status-main-text');
        if (textElement) {
            textElement.textContent = description;
        }
    } else {
        const label = ensureLabel(element);
        label.textContent = description;
    }
};

const applyMetadata = (element: HTMLElement, description: string, normalized: string): void => {
    element.dataset['state'] = normalized;
    element.setAttribute('aria-label', description);
    setTooltipText(element, description);
};

const createIcon = (doc: Document, definition: Readonly<VariantDefinition>, variant: string): HTMLElement => {
    const wrapper = doc.createElement('span');
    wrapper.className = definition.iconWrapperClass;
    wrapper.setAttribute('aria-hidden', 'true');

    if (variant === 'dashboard') {
        const textSpan = doc.createElement('span');
        textSpan.className = 'status-main-text';
        wrapper.appendChild(textSpan);
    } else {
        const indicator = doc.createElement('span');
        const indicatorClassNames = ['status-indicator'];
        if (definition.indicatorClass) {
            indicatorClassNames.push(definition.indicatorClass);
        }
        indicator.className = indicatorClassNames.join(' ');
        if (definition.iconContainerClass) {
            const container = doc.createElement('span');
            container.className = definition.iconContainerClass;
            container.appendChild(indicator);
            wrapper.appendChild(container);
        } else {
            wrapper.appendChild(indicator);
        }
    }
    return wrapper;
};

const renderTemplate = (doc: Document, variant: string | undefined): HTMLElement => {
    const { key, definition } = resolveVariant(variant);
    const root = definition.tag === 'button' ? doc.createElement('button') : doc.createElement(definition.tag);
    root.className = definition.className;
    root.dataset['mainStateVariant'] = key;
    root.dataset['mainStateLabelClass'] = definition.labelClass;
    if (definition.id) {
        root.id = definition.id;
    }
    if (root instanceof HTMLButtonElement) {
        root.type = 'button';
    }
    if (definition.role) {
        root.setAttribute('role', definition.role);
    }
    if (definition.ariaLive) {
        root.setAttribute('aria-live', definition.ariaLive);
    }
    const icon = createIcon(doc, definition, key);
    const label = doc.createElement('span');
    label.className = definition.labelClass;
    root.appendChild(icon);
    root.appendChild(label);
    return root;
};

const updateMainStateIndicatorUI = (element: HTMLElement | null, state: string | null): void => {
    if (!element) return;
    const info = getMainStateInfo(state);
    const description = info.description;
    updateColor(element, info.color);
    updateLabel(element, description);
    applyMetadata(element, description, info.state);
};

const createMainStateIndicatorUI = (state: string | null = DEFAULT_STATE, options: CreateOptions = {}): HTMLElement => {
    const element = renderTemplate(requireDocument(), options.variant);
    updateMainStateIndicatorUI(element, state);
    return element;
};

export { createMainStateIndicatorUI, updateMainStateIndicatorUI, normalizeMainState, getMainStateInfo };
