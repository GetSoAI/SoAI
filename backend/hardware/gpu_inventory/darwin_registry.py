"""SoAI - Bounded Darwin IORegistry physical path and PCI facts [backend/hardware/gpu_inventory/darwin_registry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from base64 import b64decode
from binascii import Error
from typing import TYPE_CHECKING

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import ParseError, fromstring

from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from core.types.json import JSONDict


__all__ = ("parse_darwin_registry",)


def parse_darwin_registry(raw: str) -> list[JSONDict]:
    try:
        if "<!ENTITY" in raw:
            raise ValidationError("Darwin GPU registry entity declarations are invalid.")
        document = fromstring(raw, forbid_entities=True, forbid_external=True)
        if document.tag != "plist" or len(document) != 1 or document[0].tag != "array":
            raise ValidationError("Darwin GPU registry archive framing is invalid.")
        rows: list[JSONDict] = []
        _registry_nodes(document[0], (), rows, [0])
    except (ParseError, DefusedXmlException, Error, ValueError) as exception:
        raise ValidationError(
            "Darwin GPU registry response is malformed.", details={"stdout": raw}
        ) from exception
    if len(
        {row["native_device_path"] for row in rows if isinstance(row["native_device_path"], str)}
    ) != len(rows):
        raise ValidationError("Darwin GPU registry physical paths are ambiguous.")
    return rows


def _registry_nodes(
    array: Element, parent: tuple[str, ...], rows: list[JSONDict], count: list[int]
) -> None:
    for node in array:
        count[0] += 1
        if count[0] > 16384 or len(parent) > 64 or node.tag != "dict" or len(node) % 2:
            raise ValidationError("Darwin GPU registry tree is invalid or exceeds bounded scope.")
        fields: dict[str, Element] = {}
        for offset in range(0, len(node), 2):
            key = node[offset]
            if key.tag != "key" or key.text is None or key.text in fields:
                raise ValidationError("Darwin GPU registry properties are invalid or duplicated.")
            fields[key.text] = node[offset + 1]
        name_element = fields.get("IORegistryEntryName")
        name = (
            name_element.text if name_element is not None and name_element.tag == "string" else None
        )
        if not name or name != name.strip() or "/" in name or name in (".", ".."):
            raise ValidationError("Darwin GPU registry has no actual path component.")
        path = parent + (name,)
        class_element = fields.get("class-code")
        native_class = fields.get("IOObjectClass")
        if (
            class_element is None
            and native_class is not None
            and native_class.text == "IOPCIDevice"
        ):
            raise ValidationError("Darwin PCI registry has no observed class authority.")
        if class_element is not None and _registry_number(class_element) >> 16 == 3:
            vendor_element, device_element = fields.get("vendor-id"), fields.get("device-id")
            if vendor_element is None or device_element is None:
                raise ValidationError("Darwin GPU registry physical device facts are incomplete.")
            if _registry_number(vendor_element) > 65535 or _registry_number(device_element) > 65535:
                raise ValidationError("Darwin GPU registry PCI vendor or device width is invalid.")
            model, driver = fields.get("model"), fields.get("IOObjectClass")
            rows.append(
                {
                    "native_device_path": f"darwin:ioreg:IOService:/{'/'.join(path)}",
                    "pci_vendor_id": f"{_registry_number(vendor_element):04x}",
                    "pci_device_id": f"{_registry_number(device_element):04x}",
                    "name": model.text if model is not None and model.tag == "string" else None,
                    "platform_driver": (
                        driver.text if driver is not None and driver.tag == "string" else None
                    ),
                }
            )
        children = fields.get("IORegistryEntryChildren")
        if children is not None:
            if children.tag != "array":
                raise ValidationError("Darwin GPU registry child relationship is invalid.")
            _registry_nodes(children, path, rows, count)


def _registry_number(element: Element) -> int:
    if element.tag == "data" and element.text:
        raw = b64decode("".join(element.text.split()), validate=True)
        if len(raw) not in (2, 3, 4):
            raise ValidationError("Darwin GPU registry native numeric width is invalid.")
        return int.from_bytes(raw, "little")
    if element.tag == "integer" and element.text and element.text.isdecimal():
        return int(element.text)
    raise ValidationError("Darwin GPU registry native numeric observation is invalid.")
