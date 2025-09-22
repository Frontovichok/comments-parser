## Инструмент для поиска коментариев в исходных текстах
Выполняет поиск комментариев по расширениям файлов используя регулярные выражения

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
    "src_dir_pathr/example.js": [
      {
        "comment": "comment 1",
        "line": 1
      },
      {
        "comment": "comment 2",
        "line": 16
      }
    ],
    "src_dir_pathr/test.py": [
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
