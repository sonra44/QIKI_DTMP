import argparse
import sys
import os
import logging
from .core.generator import (
    create_design_document,
    create_proto_contract,
    compile_protos,
    build_readme,
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Определяем корневую директорию проекта
_CURRENT_DIR = os.path.dirname(__file__)
_TOOL_ROOT = os.path.abspath(os.path.join(_CURRENT_DIR, ".."))
_PROJECT_ROOT = os.path.abspath(os.path.join(_TOOL_ROOT, ".."))
DOCS_DIR = os.path.join(_PROJECT_ROOT, "docs", "design")


def main():
    """Главная функция для обработки аргументов командной строки."""
    parser = argparse.ArgumentParser(
        prog="qiki-docgen",
        description="Инструмент для автоматизации создания и управления документацией проекта QIKI_DTMP.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Выполнить в режиме симуляции без фактических изменений файлов.",
    )
    parser.add_argument(
        "--template",
        type=str,
        default="default",
        help="Имя шаблона для использования (например, 'default', 'minimal').",
    )

    subparsers = parser.add_subparsers(
        dest="command", help="Доступные команды", required=True
    )

    # --- Команда 'new' ---
    parser_new = subparsers.add_parser(
        "new", help="Создать новый компонент (design.md + .proto)."
    )
    parser_new.add_argument(
        "name", type=str, help="Имя компонента (например, 'Q-Sim-Service')."
    )
    parser_new.add_argument(
        "--force", action="store_true", help="Перезаписать файлы, если они существуют."
    )

    # --- Команда 'compile-protos' ---
    parser_compile = subparsers.add_parser(
        "compile-protos", help="Скомпилировать все .proto контракты."
    )

    # --- Команда 'build-readme' ---
    parser_readme = subparsers.add_parser(
        "build-readme", help="Собрать главный README.md из документов."
    )

    args = parser.parse_args()

    if args.dry_run:
        logger.info("Запущен режим Dry Run. Файлы не будут изменены.")

    try:
        if args.command == "new":
            logger.info(f"Создание нового компонента: {args.name}")
            component_dir = os.path.join(DOCS_DIR, args.name)

            if not args.dry_run:
                os.makedirs(component_dir, exist_ok=True)
                logger.info(f"Директория компонента создана: {component_dir}")
            else:
                logger.info(
                    f"Dry Run: Директория компонента будет создана: {component_dir}"
                )

            target_file_md = os.path.join(component_dir, f"{args.name}_design.md")
            create_design_document(
                args.name, target_file_md, args.force, args.dry_run, args.template
            )
            create_proto_contract(args.name, args.force, args.dry_run, args.template)
            compile_protos(args.dry_run)

        elif args.command == "compile-protos":
            logger.info("Компиляция всех .proto контрактов.")
            compile_protos(args.dry_run)

        elif args.command == "build-readme":
            logger.info("Сборка главного README.md.")
            build_readme(args.dry_run)

        else:
            parser.print_help(sys.stderr)
            sys.exit(1)
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
