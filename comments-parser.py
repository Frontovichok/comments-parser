import os
import re
import json
import argparse
from typing import List, Dict, Any, Tuple
from datetime import datetime

# Единое место для определения расширений файлов
FILE_EXTENSIONS = {
    'go': ['.go'],
    'c': ['.c', '.h'],
    'cpp': ['.cpp', '.hpp', '.cc', '.hxx', '.cxx'],
    'javascript': ['.js'],
    'typescript': ['.ts', '.tsx'],
    'python': ['.py'],
    'perl': ['.pl', '.pm'],
    'java': ['.java'],
    'rust': ['.rs'],
    'csharp': ['.cs']
}

def find_source_files(directory: str) -> List[str]:
    """Рекурсивно находит все исходные файлы в директории"""
    source_files = []
    
    # Получаем все расширения из словаря FILE_EXTENSIONS
    all_extensions = [ext for exts in FILE_EXTENSIONS.values() for ext in exts]
    
    for root, _, files in os.walk(directory):
        for file in files:
            if any(file.endswith(ext) for ext in all_extensions):
                source_files.append(os.path.join(root, file))
    
    return source_files

def detect_language(filepath: str) -> str:
    """Определяет язык программирования по расширению файла"""
    _, ext = os.path.splitext(filepath)
    for lang, exts in FILE_EXTENSIONS.items():
        if ext in exts:
            return lang
    return 'unknown'

def parse_comments_in_file(filepath: str) -> List[Dict[str, Any]]:
    """Извлекает комментарии из файла, используя построчный анализ"""
    try:
        # Пытаемся открыть файл в UTF-8 кодировке
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        # Если не получается, пробуем latin-1 кодировку
        try:
            with open(filepath, 'r', encoding='latin-1') as f:
                content = f.read()
        except Exception as e:
            print(f"Не удалось прочитать файл {filepath}: {e}")
            return []

    # Определяем язык файла
    language = detect_language(filepath)
    
    # Для всех языков используем построчный анализ
    return parse_with_line_by_line(content, language)

def parse_with_line_by_line(content: str, language: str) -> List[Dict[str, Any]]:
    """Построчный анализ файла для извлечения комментариев"""
    lines = content.split('\n')
    comments = []
    in_block_comment = False
    block_comment_start_line = 0
    block_comment_text = []
    in_string = False
    string_char = None
    escape_next = False
    
    for line_num, line in enumerate(lines, 1):
        i = 0
        line_length = len(line)
        current_line_comment = None
        
        while i < line_length:
            if escape_next:
                escape_next = False
                i += 1
                continue
                
            char = line[i]
            
            # Обработка экранирования
            if char == '\\':
                escape_next = True
                i += 1
                continue
                
            # Обработка строковых литералов
            if in_string:
                if char == string_char:
                    in_string = False
                    string_char = None
                i += 1
                continue
                
            if char in ['"', "'", '`']:
                in_string = True
                string_char = char
                i += 1
                continue
                
            # Если мы внутри блочного комментария
            if in_block_comment:
                # Проверяем, не заканчивается ли комментарий на этой строке
                if i + 1 < line_length and char == '*' and line[i + 1] == '/':
                    in_block_comment = False
                    # Сохраняем комментарий
                    comment_text = '\n'.join(block_comment_text).strip()
                    if comment_text:
                        comments.append({
                            'comment': comment_text,
                            'line': block_comment_start_line
                        })
                    block_comment_text = []
                    i += 2  # Пропускаем '*/'
                else:
                    # Добавляем символ к комментарию
                    if not block_comment_text:
                        block_comment_text = [char]
                    else:
                        block_comment_text[-1] += char
                    i += 1
                continue
                
            # Проверяем начало блочного комментария
            if i + 1 < line_length and char == '/' and line[i + 1] == '*':
                in_block_comment = True
                block_comment_start_line = line_num
                block_comment_text = []
                i += 2  # Пропускаем '/*'
                continue
                
            # Проверяем начало однострочного комментария
            if i + 1 < line_length and char == '/' and line[i + 1] == '/':
                # Найден однострочный комментарий
                comment_text = line[i + 2:].strip()
                comments.append({
                    'comment': comment_text,
                    'line': line_num
                })
                break  # Переходим к следующей строке
                
            i += 1
            
        # Если мы все еще внутри блочного комментария в конце строки, добавляем перевод строки
        if in_block_comment and block_comment_text:
            block_comment_text[-1] += '\n'
    
    # Обработка Python docstrings
    if language == 'python':
        comments.extend(parse_python_docstrings(content))
    
    # Специальная обработка для Perl POD
    if language == 'perl':
        comments.extend(parse_perl_pod(content))
    
    return comments

def parse_python_docstrings(content: str) -> List[Dict[str, Any]]:
    """Извлекает docstrings из Python кода с учетом экранирования"""
    docstrings = []
    lines = content.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        # Ищем начало docstring
        start_index = line.find('"""')
        if start_index == -1:
            start_index = line.find("'''")
        if start_index == -1:
            i += 1
            continue

        # Найден возможный начало docstring
        quote_type = line[start_index:start_index+3]
        # Проверяем, не является ли это закрывающим docstring (если перед этим уже был открыт)
        # Но мы ищем именно начало, так что предполагаем, что это открывающий

        # Извлекаем содержимое с текущей строки
        docstring_lines = []
        current_line = line[start_index+3:]  # Часть после открывающих кавычек
        start_line_number = i + 1

        # Флаг, что мы нашли конец docstring
        found_end = False

        # Проверяем, закрывается ли docstring в этой же строке
        end_index = find_unescaped_quote(current_line, quote_type)
        if end_index != -1:
            # Docstring заканчивается в этой же строке
            docstring_lines.append(current_line[:end_index])
            found_end = True
        else:
            docstring_lines.append(current_line)
            # Продолжаем искать в следующих строках
            i += 1
            while i < len(lines):
                current_line = lines[i]
                end_index = find_unescaped_quote(current_line, quote_type)
                if end_index != -1:
                    # Нашли конец docstring
                    docstring_lines.append(current_line[:end_index])
                    found_end = True
                    break
                else:
                    docstring_lines.append(current_line)
                i += 1

        if found_end:
            comment_text = '\n'.join(docstring_lines).strip()
            if comment_text:
                docstrings.append({
                    'comment': comment_text,
                    'line': start_line_number
                })
        # Продолжаем со следующей строки после конца docstring
        i += 1

    return docstrings

def find_unescaped_quote(line: str, quote_type: str) -> int:
    """
    Ищет незаэкранированные кавычки в строке.
    Возвращает индекс начала кавычек или -1, если не найдено.
    """
    i = 0
    while i < len(line):
        # Если находим кавычки
        if line[i:i+3] == quote_type:
            # Проверяем, не экранированы ли они
            if i > 0 and line[i-1] == '\\':
                # Кавычки экранированы, пропускаем
                i += 3
                continue
            return i
        i += 1
    return -1

def parse_perl_pod(content: str) -> List[Dict[str, Any]]:
    """Специальная функция для извлечения POD документации в Perl"""
    pod_comments = []
    # Паттерн для поиска POD документации
    pod_pattern = r'^=(\w+)(.*?)^=cut'
    
    for match in re.finditer(pod_pattern, content, re.MULTILINE | re.DOTALL):
        pod_command = match.group(1).strip()
        pod_content = match.group(2).strip()
        line_number = content[:match.start()].count('\n') + 1
        
        pod_comments.append({
            'comment': f"=pod {pod_command}: {pod_content}",
            'line': line_number
        })
    
    return pod_comments

def main():
    """Основная функция скрипта"""
    # Настройка парсера аргументов командной строки
    parser = argparse.ArgumentParser(description='Парсер комментариев в коде различных языков программирования')
    parser.add_argument('input_dir', help='Путь к директории с исходными кодами')
    parser.add_argument('output_file', help='Путь к выходному JSON файлу')
    args = parser.parse_args()

    # Получаем абсолютный путь к директории
    abs_input_dir = os.path.abspath(args.input_dir)
    
    # Проверяем существование директории
    if not os.path.isdir(abs_input_dir):
        print(f"Ошибка: Директория {abs_input_dir} не существует")
        return
    
    # Поиск и парсинг файлов
    source_files = find_source_files(abs_input_dir)
    files_comments = {}
    
    # Обрабатываем каждый файл
    for source_file in source_files:
        comments = parse_comments_in_file(source_file)
        # Используем абсолютный путь к файлу как ключ
        files_comments[source_file] = comments
        print(f"Обработан {source_file}, найдено {len(comments)} комментариев")

    # Формируем результат с требуемой структурой
    result = {
        "directory": abs_input_dir,
        "analyzeTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "files": files_comments
    }

    # Сохранение в JSON
    try:
        with open(args.output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"Результат сохранен в {args.output_file}")
    except Exception as e:
        print(f"Ошибка при сохранении файла {args.output_file}: {e}")
        return

    # Выводим статистику
    total_comments = sum(len(comments) for comments in files_comments.values())
    print(f"Всего найдено {total_comments} комментариев в {len(source_files)} файлах")

if __name__ == '__main__':
    main()