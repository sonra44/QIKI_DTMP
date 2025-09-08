import logging
import re
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class ProtoParser:
    """
    Парсер для .proto файлов. Извлекает messages, enums, services.
    """

    def parse_proto_file(self, proto_file_path: Path) -> Dict[str, Any]:
        """Парсит .proto файл и извлекает структурную информацию."""
        logger.info(f"Парсинг .proto файла: {proto_file_path}")

        if not proto_file_path.exists():
            logger.error(f"Proto файл не найден: {proto_file_path}")
            return {
                "file_path": str(proto_file_path),
                "messages": [],
                "enums": [],
                "services": [],
                "package": "",
            }

        try:
            content = proto_file_path.read_text(encoding="utf-8")

            # Извлекаем основную информацию
            package = self._extract_package(content)
            messages = self._extract_messages(content)
            enums = self._extract_enums(content)
            services = self._extract_services(content)

            return {
                "file_path": str(proto_file_path),
                "package": package,
                "messages": messages,
                "enums": enums,
                "services": services,
            }

        except Exception as e:
            logger.error(f"Ошибка парсинга {proto_file_path}: {e}")
            return {
                "file_path": str(proto_file_path),
                "messages": [],
                "enums": [],
                "services": [],
                "package": "",
            }

    def _extract_package(self, content: str) -> str:
        """Извлекает имя пакета."""
        match = re.search(r"package\s+([^;]+);", content)
        return match.group(1).strip() if match else ""

    def _extract_messages(self, content: str) -> List[Dict[str, Any]]:
        """Извлекает информацию о message типах."""
        messages = []
        # Ищем message блоки
        pattern = r"message\s+(\w+)\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}"

        for match in re.finditer(pattern, content, re.MULTILINE | re.DOTALL):
            message_name = match.group(1)
            message_body = match.group(2)

            # Извлекаем поля
            fields = self._extract_message_fields(message_body)

            messages.append(
                {
                    "name": message_name,
                    "fields": fields,
                    "description": self._extract_comment_before(content, match.start()),
                }
            )

        return messages

    def _extract_message_fields(self, message_body: str) -> List[Dict[str, str]]:
        """Извлекает поля из тела message."""
        fields = []
        # Простая регулярка для полей: тип имя = номер;
        field_pattern = r"(\w+(?:\.\w+)*)\s+(\w+)\s*=\s*(\d+);"

        for match in re.finditer(field_pattern, message_body):
            field_type = match.group(1)
            field_name = match.group(2)
            field_number = match.group(3)

            fields.append(
                {"type": field_type, "name": field_name, "number": field_number}
            )

        return fields

    def _extract_enums(self, content: str) -> List[Dict[str, Any]]:
        """Извлекает информацию об enum типах."""
        enums = []
        # Ищем enum блоки
        pattern = r"enum\s+(\w+)\s*\{([^{}]+)\}"

        for match in re.finditer(pattern, content, re.MULTILINE | re.DOTALL):
            enum_name = match.group(1)
            enum_body = match.group(2)

            # Извлекаем значения enum
            values = self._extract_enum_values(enum_body)

            enums.append(
                {
                    "name": enum_name,
                    "values": values,
                    "description": self._extract_comment_before(content, match.start()),
                }
            )

        return enums

    def _extract_enum_values(self, enum_body: str) -> List[Dict[str, str]]:
        """Извлекает значения из тела enum."""
        values = []
        # Регулярка для enum значений: ИМЯ = число;
        value_pattern = r"(\w+)\s*=\s*(\d+);"

        for match in re.finditer(value_pattern, enum_body):
            value_name = match.group(1)
            value_number = match.group(2)

            values.append({"name": value_name, "number": value_number})

        return values

    def _extract_services(self, content: str) -> List[Dict[str, Any]]:
        """Извлекает информацию о service типах."""
        services = []
        # Ищем service блоки
        pattern = r"service\s+(\w+)\s*\{([^{}]+)\}"

        for match in re.finditer(pattern, content, re.MULTILINE | re.DOTALL):
            service_name = match.group(1)
            service_body = match.group(2)

            # Извлекаем RPC методы
            methods = self._extract_rpc_methods(service_body)

            services.append(
                {
                    "name": service_name,
                    "methods": methods,
                    "description": self._extract_comment_before(content, match.start()),
                }
            )

        return services

    def _extract_rpc_methods(self, service_body: str) -> List[Dict[str, str]]:
        """Извлекает RPC методы из тела service."""
        methods = []
        # Регулярка для RPC: rpc MethodName (Request) returns (Response);
        rpc_pattern = r"rpc\s+(\w+)\s*\(([^)]+)\)\s*returns\s*\(([^)]+)\);"

        for match in re.finditer(rpc_pattern, service_body):
            method_name = match.group(1)
            request_type = match.group(2).strip()
            response_type = match.group(3).strip()

            methods.append(
                {
                    "name": method_name,
                    "request": request_type,
                    "response": response_type,
                }
            )

        return methods

    def _extract_comment_before(self, content: str, position: int) -> str:
        """Извлекает комментарий перед указанной позицией."""
        # Ищем комментарии // или /* */ перед позицией
        lines = content[:position].split("\n")
        comments = []

        # Идем назад от позиции и собираем комментарии
        for line in reversed(lines[-5:]):  # Смотрим последние 5 строк
            line = line.strip()
            if line.startswith("//"):
                comments.insert(0, line[2:].strip())
            elif line.startswith("/*") or line.endswith("*/"):
                # Простая обработка блочных комментариев
                comment = line.replace("/*", "").replace("*/", "").strip()
                if comment:
                    comments.insert(0, comment)
            elif not line:
                continue  # Пустые строки игнорируем
            else:
                break  # Встретили не комментарий - останавливаемся

        return " ".join(comments)


class DesignDocParser:
    """
    Парсер для design.md документов. Поддерживает YAML frontmatter и структурированные секции.
    """

    def parse_design_doc(self, design_doc_path: Path) -> Dict[str, Any]:
        """Парсит design.md документ и извлекает структурированную информацию."""
        logger.info(f"Парсинг design.md документа: {design_doc_path}")

        if not design_doc_path.exists():
            logger.error(f"Design документ не найден: {design_doc_path}")
            return self._empty_result(design_doc_path)

        try:
            content = design_doc_path.read_text(encoding="utf-8")

            # Извлекаем frontmatter и основной контент
            frontmatter, main_content = self._split_frontmatter(content)

            # Парсим YAML frontmatter если есть
            metadata = self._parse_frontmatter(frontmatter) if frontmatter else {}

            # Извлекаем структурированные секции
            sections = self._extract_sections(main_content)

            # Определяем component_name
            component_name = self._determine_component_name(
                metadata, sections, design_doc_path
            )

            return {
                "file_path": str(design_doc_path),
                "component_name": component_name,
                "metadata": metadata,
                "sections": sections,
                "overview": sections.get("1. Overview", sections.get("1. Обзор", "")),
                "has_frontmatter": bool(frontmatter),
            }

        except Exception as e:
            logger.error(f"Ошибка парсинга design документа {design_doc_path}: {e}")
            return self._empty_result(design_doc_path)

    def _empty_result(self, design_doc_path: Path) -> Dict[str, Any]:
        """Возвращает пустой результат при ошибке."""
        return {
            "file_path": str(design_doc_path),
            "component_name": "",
            "metadata": {},
            "sections": {},
            "overview": "",
            "has_frontmatter": False,
        }

    def _split_frontmatter(self, content: str) -> tuple[str, str]:
        """Разделяет YAML frontmatter и основной контент."""
        if not content.startswith("---"):
            return "", content

        # Ищем закрывающий ---
        lines = content.split("\n")
        end_index = -1

        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                end_index = i
                break

        if end_index == -1:
            return "", content  # Нет закрывающего ---, считаем что frontmatter нет

        frontmatter = "\n".join(lines[1:end_index])
        main_content = "\n".join(lines[end_index + 1 :])

        return frontmatter, main_content

    def _parse_frontmatter(self, frontmatter: str) -> Dict[str, Any]:
        """Парсит YAML frontmatter."""
        try:
            # Простой YAML парсинг без внешних библиотек
            metadata = {}
            for line in frontmatter.split("\n"):
                line = line.strip()
                if ":" in line and not line.startswith("#"):
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip()

                    # Убираем кавычки если есть
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]

                    metadata[key] = value

            return metadata
        except Exception as e:
            logger.warning(f"Ошибка парсинга YAML frontmatter: {e}")
            return {}

    def _extract_sections(self, content: str) -> Dict[str, str]:
        """Извлекает секции документа по заголовкам."""
        sections = {}
        current_section = None
        current_content = []

        for line in content.split("\n"):
            # Ищем заголовки уровня 2 (## ...)
            if re.match(r"^##\s+(.+)$", line):
                # Сохраняем предыдущую секцию
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()

                # Начинаем новую секцию
                current_section = re.match(r"^##\s+(.+)$", line).group(1)
                current_content = []
            elif current_section:
                current_content.append(line)

        # Сохраняем последнюю секцию
        if current_section:
            sections[current_section] = "\n".join(current_content).strip()

        return sections

    def _determine_component_name(
        self, metadata: Dict[str, Any], sections: Dict[str, str], file_path: Path
    ) -> str:
        """Определяет имя компонента из различных источников."""
        # 1. Из frontmatter
        if "component_name" in metadata:
            return metadata["component_name"]

        # 2. Из заголовка документа
        title_patterns = [r"^#\s+(?:Design:\s*)?(.+)$", r"^#\s+(?:Дизайн:\s*)?(.+)$"]

        for section_content in sections.values():
            lines = section_content.split("\n")
            if lines:
                first_line = lines[0].strip()
                for pattern in title_patterns:
                    match = re.match(pattern, first_line)
                    if match:
                        return match.group(1).strip()

        # 3. Из имени файла
        return file_path.stem.replace("_design", "").replace("-", "_")
