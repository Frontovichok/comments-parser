## Инструмент для поиска коментариев в исходных текстах
Выполняет поиск комментариев в директории с исходными текстами, используя регулярные выражения.
Поиск выполняется по расширениям файлов.

## Поддерживает следующие языки:
- Go
- C
- C++
- C#
- JavaScript
- TypeScript
- Python
- Perl
- Java
- Rust

## Запуск:
```bash
python comments-parser.py <src_dir> <output.json>
```
## Вывод (output.json):

```json
{
  "directory": "src_dir_pathr",
  "analyzeTime": "yyyy-mm-dd hh:mm:ss",
  "files": {
    "src_dir_path/example.js": [
      {
        "comment": "comment 1",
        "line": 1
      },
      {
        "comment": "comment 2",
        "line": 16
      }
    ],
    "src_dir_path/test.py": [
      {
        "comment": "comment 1",
        "line": 10
      },
      {
        "comment": "comment 2",
        "line": 160
      }
    ]
  }
}
```
