import os
import re
import json
import argparse
from typing import List, Dict, Any
from datetime import datetime
from pathlib import Path

# Единое место для определения расширений файлов
FILE_EXTENSIONS = {
    "go": {".go"},
    "c": {".c", ".h"},
    "cpp": {".cpp", ".hpp", ".cc", ".hxx", ".cxx"},
    "javascript": {".js"},
    "typescript": {".ts", ".tsx"},
    "python": {".py"},
    "perl": {".pl", ".pm"},
    "java": {".java"},
    "rust": {".rs"},
    "csharp": {".cs"},
}

# Компилируем регулярные выражения для производительности
POD_PATTERN = re.compile(r"^=(\w+)(.*?)^=cut", re.MULTILINE | re.DOTALL)


class CommentParser:
    """Класс для парсинга комментариев с оптимизированной обработкой"""

    def __init__(self):
        self.all_extensions = {ext for exts in FILE_EXTENSIONS.values() for ext in exts}

    def find_source_files(self, directory: str) -> List[str]:
        """Рекурсивно находит все исходные файлы в директории"""
        source_files = []
        directory_path = Path(directory)

        for file_path in directory_path.rglob("*"):
            if file_path.is_file() and file_path.suffix in self.all_extensions:
                source_files.append(str(file_path))

        return source_files

    def detect_language(self, filepath: str) -> str:
        """Определяет язык программирования по расширению файла"""
        ext = Path(filepath).suffix
        for lang, exts in FILE_EXTENSIONS.items():
            if ext in exts:
                return lang
        return "unknown"

    def read_file_content(self, filepath: str) -> str:
        """Читает содержимое файла с обработкой различных кодировок"""
        encodings = ["utf-8", "latin-1", "cp1251", "iso-8859-1"]

        for encoding in encodings:
            try:
                with open(filepath, "r", encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue

        print(f"Не удалось прочитать файл {filepath}")
        return ""

    def parse_comments_in_file(self, filepath: str) -> List[Dict[str, Any]]:
        """Извлекает комментарии из файла"""
        content = self.read_file_content(filepath)
        if not content:
            return []

        language = self.detect_language(filepath)
        comments = self.parse_with_line_by_line(content, language)

        # Дополнительная обработка для специфичных языков
        if language == "python":
            comments.extend(self.parse_python_docstrings(content))
        elif language == "perl":
            comments.extend(self.parse_perl_pod(content))

        return comments

    def parse_with_line_by_line(
        self, content: str, language: str
    ) -> List[Dict[str, Any]]:
        """Оптимизированный построчный анализ для извлечения комментариев"""
        lines = content.split("\n")
        comments = []

        # Состояния парсера
        in_block_comment = False
        block_comment_lines = []
        block_start_line = 0

        for line_num, line in enumerate(lines, 1):
            line = line.rstrip("\r")

            if in_block_comment:
                # Ищем конец блочного комментария
                end_idx = line.find("*/")
                if end_idx != -1:
                    # Конец блочного комментария
                    block_comment_lines.append(line[:end_idx])
                    comment_text = "\n".join(block_comment_lines).strip()
                    if comment_text:
                        comments.append(
                            {"comment": comment_text, "line": block_start_line}
                        )
                    in_block_comment = False
                    # Проверяем, есть ли код после комментария
                    remaining = line[end_idx + 2 :].lstrip()
                    if remaining and remaining.startswith("//"):
                        # Однострочный комментарий после блочного
                        comments.append(
                            {"comment": remaining[2:].strip(), "line": line_num}
                        )
                else:
                    # Продолжаем блочный комментарий
                    block_comment_lines.append(line)
                continue

            # Поиск комментариев в строке
            comment_data = self.find_comments_in_line(line, language)
            if comment_data:
                comment_type, comment_text, end_idx = comment_data

                if comment_type == "line":
                    # Однострочный комментарий
                    comments.append({"comment": comment_text.strip(), "line": line_num})
                elif comment_type == "block":
                    # Начало блочного комментария
                    in_block_comment = True
                    block_comment_lines = [comment_text]
                    block_start_line = line_num

                    # Проверяем, заканчивается ли блочный комментарий в этой же строке
                    remaining = line[end_idx + 2 :]
                    end_idx_inner = remaining.find("*/")
                    if end_idx_inner != -1:
                        # Блочный комментарий заканчивается в этой строке
                        block_comment_lines[0] = remaining[:end_idx_inner]
                        comment_text = "\n".join(block_comment_lines).strip()
                        if comment_text:
                            comments.append(
                                {"comment": comment_text, "line": block_start_line}
                            )
                        in_block_comment = False

        return comments

    def find_comments_in_line(self, line: str, language: str) -> tuple:
        """Находит комментарии в одной строке кода"""
        i = 0
        in_string = False
        string_char = None
        escape_next = False

        while i < len(line):
            char = line[i]

            if escape_next:
                escape_next = False
                i += 1
                continue

            if char == "\\":
                escape_next = True
                i += 1
                continue

            if in_string:
                if char == string_char:
                    in_string = False
                    string_char = None
                i += 1
                continue

            if char in ['"', "'", "`"]:
                in_string = True
                string_char = char
                i += 1
                continue

            # Проверяем начало комментариев
            if i + 1 < len(line):
                if line[i : i + 2] == "//":
                    # Однострочный комментарий
                    return ("line", line[i + 2 :], i)
                elif line[i : i + 2] == "/*":
                    # Блочный комментарий
                    return ("block", line[i + 2 :], i)

            i += 1

        return None

    def parse_python_docstrings(self, content: str) -> List[Dict[str, Any]]:
        """Извлекает docstrings из Python кода"""
        docstrings = []
        lines = content.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i]
            quote_match = self.find_docstring_quotes(line)

            if quote_match:
                start_idx, quote_type = quote_match
                start_line = i + 1
                docstring_content, end_line = self.extract_docstring_content(
                    lines, i, start_idx, quote_type
                )

                if docstring_content:
                    docstrings.append(
                        {"comment": docstring_content.strip(), "line": start_line}
                    )
                    i = end_line
            i += 1

        return docstrings

    def find_docstring_quotes(self, line: str) -> tuple:
        """Находит начало docstring в строке"""
        triple_double = line.find('"""')
        triple_single = line.find("'''")

        if triple_double != -1 and (
            triple_single == -1 or triple_double < triple_single
        ):
            return (triple_double, '"""')
        elif triple_single != -1:
            return (triple_single, "'''")
        return None

    def extract_docstring_content(
        self, lines: List[str], start_idx: int, quote_pos: int, quote_type: str
    ) -> tuple:
        """Извлекает содержимое docstring"""
        content_lines = []
        current_line = lines[start_idx][quote_pos + 3 :]

        # Проверяем, закрывается ли docstring в той же строке
        end_pos = self.find_unescaped_quote(current_line, quote_type)
        if end_pos != -1:
            content_lines.append(current_line[:end_pos])
            return "\n".join(content_lines), start_idx

        content_lines.append(current_line)

        # Ищем закрывающие кавычки в следующих строках
        for i in range(start_idx + 1, len(lines)):
            current_line = lines[i]
            end_pos = self.find_unescaped_quote(current_line, quote_type)
            if end_pos != -1:
                content_lines.append(current_line[:end_pos])
                return "\n".join(content_lines), i
            content_lines.append(current_line)

        return "\n".join(content_lines), len(lines) - 1

    def find_unescaped_quote(self, line: str, quote_type: str) -> int:
        """Ищет незаэкранированные кавычки в строке"""
        pos = 0
        while pos < len(line):
            found_pos = line.find(quote_type, pos)
            if found_pos == -1:
                return -1

            # Проверяем экранирование
            if found_pos == 0 or line[found_pos - 1] != "\\":
                return found_pos

            pos = found_pos + 1
        return -1

    def parse_perl_pod(self, content: str) -> List[Dict[str, Any]]:
        """Извлекает POD документацию в Perl"""
        pod_comments = []

        for match in POD_PATTERN.finditer(content):
            pod_command = match.group(1).strip()
            pod_content = match.group(2).strip()
            line_number = content[: match.start()].count("\n") + 1

            pod_comments.append(
                {"comment": f"={pod_command}: {pod_content}", "line": line_number}
            )

        return pod_comments


def print_progress_bar(
    current: int, total: int, comments_count: int, bar_length: int = 50
):
    """Печатает прогресс-бар в консоль"""
    percent = min(100.0, float(current) * 100 / total)
    filled_length = int(bar_length * current // total)
    bar = "█" * filled_length + "░" * (bar_length - filled_length)

    print(
        f"\r{bar} {percent:.1f}% | Файлов: {current}/{total} | Комментариев: {comments_count}",
        end="",
        flush=True,
    )


def main():
    """Основная функция скрипта"""
    parser = argparse.ArgumentParser(
        description="Парсер комментариев в коде различных языков программирования"
    )
    parser.add_argument("input_dir", help="Путь к директории с исходными кодами")
    parser.add_argument("output_file", help="Путь к выходному JSON файлу")
    args = parser.parse_args()

    input_dir = Path(args.input_dir).resolve()

    if not input_dir.is_dir():
        print(f"Ошибка: Директория {input_dir} не существует")
        return

    # Инициализация парсера
    parser = CommentParser()

    print("Поиск исходных файлов...")
    source_files = parser.find_source_files(str(input_dir))
    total_files = len(source_files)

    if not source_files:
        print("Файлы для обработки не найдены")
        return

    print(f"Найдено файлов: {total_files}")
    print("Обработка файлов...")

    files_comments = {}
    total_comments = 0

    for i, source_file in enumerate(source_files, 1):
        comments = parser.parse_comments_in_file(source_file)
        files_comments[source_file] = comments
        total_comments += len(comments)

        print_progress_bar(i, total_files, total_comments)

    print()  # Новая строка после прогресс-бара

    # Формирование результата
    result = {
        "directory": str(input_dir),
        "analyzeTime": datetime.now().isoformat(),
        "statistics": {
            "totalFiles": total_files,
            "processedFiles": len(files_comments),
            "totalComments": total_comments,
        },
        "files": files_comments,
    }

    # Сохранение результатов
    try:
        with open(args.output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"✓ Результат сохранен в {args.output_file}")
    except Exception as e:
        print(f"✗ Ошибка при сохранении: {e}")
        return

    # Статистика
    print(f"\nОбработка завершена!")
    print(f"• Обработано файлов: {len(files_comments)}/{total_files}")
    print(f"• Найдено комментариев: {total_comments}")


if __name__ == "__main__":
    main()
