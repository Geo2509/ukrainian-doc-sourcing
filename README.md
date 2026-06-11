# Ukrainian Document Sourcing

Проект для поиска, скачивания, первичной проверки и отбора украинских документных PDF. Он собирает кандидаты из поисковой выдачи, скачивает PDF-файлы, прогоняет их через QA-фильтр и копирует подходящие документы в отдельную папку.

## Что внутри

- `scripts/search_ddg.py` - ищет ссылки на украинские документы через DuckDuckGo/DDGS и сохраняет кандидатов в `data/candidate_links.csv`.
- `scripts/download_pdfs.py` - скачивает найденные PDF в `downloads/`.
- `scripts/qa_check.py` - проверяет скачанные PDF через `pdftotext`, при необходимости запускает OCR и отбраковывает плохое распознавание.
- `scripts/export_approved.py` - копирует авто-одобренные PDF из `downloads/` в `approved_pdfs/`.
- `scripts/final_validate_documents.py` - повторно валидирует финальный список и пишет `output/final_validation_report.txt`.
- `data/candidate_links.csv` - найденные ссылки-кандидаты.
- `downloads/` - все скачанные PDF.
- `output/qa_results.csv` - полный QA-отчет по скачанным файлам.
- `output/approved_candidates.csv` - файлы, прошедшие базовый QA-фильтр.
- `output/final_validation_results.csv` - финальная машинная проверка одобренных кандидатов.
- `output/final_validation_report.txt` - человекочитаемый отчет с первыми строками текста и оценкой OCR.
- `approved_pdfs/` - финальная подборка одобренных PDF.

## Категории документов

Скрипт поиска собирает документы по таким категориям:

- `contract` - договоры, акты, дополнительные соглашения.
- `financial_environmental_report` - финансовые отчеты, экологические отчеты, документы ОВД.
- `receipt` - квитанции, чеки, платежные документы.
- `certificate_of_analysis` - сертификаты анализа, качества, соответствия, протоколы испытаний.
- `hospital_claim` - документы по медицинским услугам и страховым/компенсационным кейсам.
- `patient_form` - анкеты пациента, согласия, медицинские формы.
- `medical_doctor_note` - медицинские заключения, выписки, справки врача.
- `logistics_financial` - накладные, счета, акты выполненных работ.
- `handwritten` - заявления, объяснения, расписки, рапорты и другие документы с рукописным контекстом.
- `editable_docs` - DOCX-кандидаты; текущий загрузчик сохраняет файлы как PDF, поэтому эту категорию стоит обрабатывать отдельно при необходимости.

## Текущее состояние данных

На момент подготовки README в проекте уже есть:

- 488 ссылок-кандидатов в `data/candidate_links.csv`.
- 673 скачанных PDF в `downloads/`.
- 673 проверенных файла в `output/qa_results.csv`.
- 59 авто-одобренных кандидатов в `output/approved_candidates.csv`.
- 76 PDF в `approved_pdfs/`; это больше, чем авто-одобренных строк, поэтому часть финальной подборки, вероятно, добавлялась или переименовывалась вручную.

Распределение файлов в `approved_pdfs/`:

| Категория | Количество |
| --- | ---: |
| `financial_environmental_report` | 23 |
| `logistics_financial` | 12 |
| `certificate_of_analysis` | 11 |
| `handwritten` | 10 |
| `contract` | 8 |
| `receipt` | 6 |
| `patient_form` | 3 |
| `medical_doctor_note` | 3 |

## Установка

Нужен Python 3.10+ и системные OCR/PDF-утилиты: `pdftotext`/`pdfinfo` из Poppler, `ocrmypdf`, Tesseract с языком `ukr`.

```bash
python -m venv venv
source venv/bin/activate
pip install pandas ddgs requests PyMuPDF ocrmypdf
```

В репозитории уже есть локальный `venv/`, но для воспроизводимости лучше пересоздать окружение или поставить зависимости явно.

## Запуск пайплайна

1. Найти ссылки-кандидаты:

```bash
python scripts/search_ddg.py
```

Результат: `data/candidate_links.csv`.

2. Скачать PDF:

```bash
python scripts/download_pdfs.py
```

Результат: файлы в `downloads/`.

3. Проверить качество документов:

```bash
python scripts/qa_check.py
```

Результаты:

- `output/qa_results.csv` - полный отчет.
- `output/approved_candidates.csv` - только документы, прошедшие базовую проверку.

4. Скопировать одобренные документы:

```bash
python scripts/export_approved.py
```

Результат: PDF в `approved_pdfs/`.

5. Сделать финальную проверку OCR/текста:

```bash
python3 scripts/final_validate_documents.py
```

Результаты:

- `output/final_validation_results.csv` - финальные поля по каждому кандидату.
- `output/final_validation_report.txt` - отчет: имя файла, источник, слова/символы, нужен ли OCR, первые 10 строк текста, качество OCR.

6. Проверить дубликаты после экспорта:

```bash
python scripts/cleanup_duplicate_pdfs.py --report output/duplicate_check_after_export.csv
```

Если в выводе есть дубликаты, удалить точные копии:

```bash
python scripts/cleanup_duplicate_pdfs.py --delete --report output/duplicate_cleanup_after_export.csv
```

Этот шаг стоит запускать каждый раз после `export_approved.py`, после ручного копирования файлов в `prepared_pdfs/` или после создания новых подборок.

## QA-критерии

`scripts/qa_check.py` и `scripts/final_validate_documents.py` считают документ прошедшим проверку, если:

- в PDF не больше 3 страниц;
- `pdftotext file.pdf -` дает не меньше 300 слов, либо OCR дает не меньше 300 слов;
- качество извлеченного/OCR-текста равно `good` или `medium`;
- нет признаков мусорного OCR: вертикальных столбцов букв, большого числа отдельных букв на отдельных строках, текста без нормальных украинских слов.

Для каждого PDF сохраняются:

- `local_path`;
- `source_url`;
- `category`;
- `format` (`handwritten`, `digital`, `printed`);
- `extracted_word_count`;
- `ocr_word_count`;
- `ocr_character_count`;
- `ocr_quality` (`good`, `medium`, `bad`);
- `accepted`;
- `rejection_reason`.

Если `extracted_word_count < 300`, запускается:

```bash
ocrmypdf --deskew --clean --rotate-pages -l ukr input.pdf output_ocr.pdf
```

После OCR текст снова извлекается через `pdftotext`, считаются слова/символы и сохраняется preview первых строк.

Приоритет отбора:

1. Оригинальный PDF с качественным текстовым слоем.
2. PDF, который после OCR дает качественный украинский текст.
3. Сканированный PDF только если OCR проходит проверку качества.

Полностью рукописные страницы больше не являются целевым типом. Для документов с рукописным заполнением лучше искать печатные формы: медицинские формы, анкеты, согласия пациента, формы с подписями и датами, где максимум текста напечатан, а рукописи минимум.

Проверка OCR не заменяет ручную проверку приватных данных. Перед использованием финальной подборки нужно отдельно смотреть источники, читаемость и возможные PII.

## Важные замечания

- Скрипты используют относительные пути, поэтому запускать их нужно из корня проекта.
- `search_ddg.py` зависит от доступности поисковой выдачи и может возвращать разные результаты в разные дни.
- `download_pdfs.py` проверяет `Content-Type` и расширение URL, но не валидирует содержимое PDF глубоко.
- В именах файлов могут быть префиксы `!`, `!!` и похожие отметки. Похоже, они использовались для ручной сортировки или приоритизации.
- Перед использованием финальной подборки в датасетах стоит сделать ручную проверку источника, читаемости и приватных данных.

## Синтетическое рукописное заполнение

Для AI-training/OCR/layout-задач можно делать синтетические версии документов: печатная форма остается фоном, а выбранные поля заполняются вымышленным рукописным текстом на украинском языке.

### Критерии выбора исходного PDF

Лучше выбирать документы из `output/approved_candidates.csv`, где:

- `pages` равно `1`;
- `final_word_count` не меньше `300`;
- `ocr_quality` равно `good` или `medium`;
- документ содержит пустые поля, строки, таблицы или зоны для подписи;
- документ не содержит реальных приватных данных, либо они заранее удалены/заменены.

Быстро посмотреть подходящие кандидаты:

```bash
python3 -c "import pandas as pd; df=pd.read_csv('output/approved_candidates.csv'); print(df[(df['pages']==1) & (df['final_word_count']>=300)][['local_path','pages','final_word_count','ocr_quality','format']].sort_values('final_word_count').to_string(index=False))"
```

### Что нужно передать для генерации sample

Минимальный формат задания:

```text
PDF: 340_logistics_financial.pdf

Поля/текст:
1. ПІБ: Іваненко Олексій Петрович
2. Дата: 14.05.2026
3. Адреса: м. Львів, вул. Сонячна, 12
4. Примітка: Документ перевірено, дані внесено вручну
5. Підпис: Іваненко
```

Можно передать и свободный текст. Тогда места для вставки выбираются по пустым областям, строкам, таблицам и зонам подписи.

### Как имитируется письмо ручкой

Для рукописного слоя используются такие эффекты:

- синий или темно-синий цвет чернил;
- небольшая прозрачность, чтобы текст не выглядел как печатный слой;
- легкий наклон текста;
- случайные смещения по baseline;
- разный размер букв и интервалы;
- небольшая неровность поворота отдельных строк;
- разные рукописные стили для разных полей;
- при необходимости растрирование рукописного слоя перед вставкой в PDF.

### Результат

Синтетические документы лучше сохранять отдельно, например:

```text
generated_pdfs/
```

Рекомендуемый формат имени:

```text
generated_pdfs/340_logistics_financial_handfilled_sample_001.pdf
```

### Ограничения

- Использовать только вымышленные данные.
- Не использовать реальные подписи, реальные паспортные/налоговые/банковские данные и реальные медицинские сведения.
- Не выдавать synthetic samples за настоящие документы.
- Для production-разметки сохранять связь с исходным файлом: имя исходного PDF, список заполненных полей, использованный стиль рукописного текста.

## Очистка дубликатов PDF

В проекте часто появляются одинаковые PDF под разными именами: поисковик может найти один и тот же документ по разным запросам, а затем файлы копируются в `downloads/`, `approved_pdfs/`, `prepared_pdfs/` и рабочие подборки.

Есть два разных типа дубликатов:

- точные файловые дубликаты - PDF полностью одинаковые байт-в-байт;
- визуальные дубликаты - PDF могут иметь разные имена, метаданные или сжатие, но страницы выглядят одинаково.

Оба типа нужно проверять после скачивания, экспорта и ручного копирования файлов.

### Точные файловые дубликаты

Для очистки используется точное сравнение по SHA-256 хэшу файла. Это значит, что удаляются только байт-в-байт одинаковые PDF. Похожие документы с разным содержимым не считаются дубликатами.

Скрипт:

```bash
python scripts/cleanup_duplicate_pdfs.py
```

По умолчанию скрипт ничего не удаляет, а только ищет дубликаты и пишет отчет:

```text
output/duplicate_cleanup_report.csv
```

Чтобы удалить дубликаты:

```bash
python scripts/cleanup_duplicate_pdfs.py --delete
```

Логика удаления:

- проверяются все PDF внутри проекта;
- `venv/`, `.git/`, `.agents/`, `.codex/` и `__pycache__/` пропускаются;
- дубликаты сравниваются внутри каждой отдельной папки;
- первый файл в группе, отсортированной по имени, остается;
- остальные точные копии удаляются;
- в CSV-отчете сохраняются путь к оставленному файлу, путь к удаленному файлу, SHA-256 и размер удаленного файла.

Проверить, остались ли дубликаты после чистки:

```bash
python scripts/cleanup_duplicate_pdfs.py --report output/duplicate_check_after_cleanup.csv
```

Если вывод:

```text
found: 0 duplicate PDF files
```

значит внутри рабочих папок не осталось точных PDF-дубликатов.

Текущая чистка уже выполнена. Отчет:

```text
output/duplicate_cleanup_report.csv
```

### Визуальные дубликаты

Некоторые документы выглядят одинаково, но имеют разные имена файлов или разные PDF-метаданные. Такие случаи SHA-256 не ловит, поэтому для них используется отдельный визуальный контроль:

```bash
python scripts/cleanup_visual_duplicate_pdfs.py --report output/visual_duplicate_report.csv
```

Как работает визуальная проверка:

- каждая PDF-страница рендерится как изображение;
- для изображения считается perceptual hash;
- документы сравниваются внутри каждой отдельной папки;
- если число страниц совпадает и хэши страниц достаточно близки, файл считается визуальным дублем;
- по умолчанию скрипт только пишет отчет и ничего не переносит.

Для аккуратной очистки визуальные дубликаты лучше не удалять сразу, а переносить:

```bash
python scripts/cleanup_visual_duplicate_pdfs.py \
  --action move \
  --report output/visual_duplicate_cleanup_report.csv
```

Перенесенные файлы складываются в:

```text
duplicates_removed_visual/
```

После переноса проверить еще раз:

```bash
python scripts/cleanup_visual_duplicate_pdfs.py \
  --report output/visual_duplicate_check_after_cleanup.csv
```

Если вывод:

```text
visual duplicate rows: 0
```

значит визуальных дубликатов внутри рабочих папок не осталось. Ошибки по битым или пустым PDF могут оставаться в отчете отдельно.

Текущая визуальная чистка уже выполнена:

- найдено 11 визуальных дубликатов;
- они перенесены в `duplicates_removed_visual/`;
- контроль после переноса показал `visual duplicate rows: 0`;
- отчет очистки: `output/visual_duplicate_cleanup_report.csv`;
- отчет проверки после очистки: `output/visual_duplicate_check_after_cleanup.csv`.

### Контроль после вытяжки файлов

После любого шага, который копирует PDF в новую папку, нужно делать контроль дубликатов. Это относится к:

- `python scripts/export_approved.py`;
- копированию файлов в `prepared_pdfs/`;
- созданию подборок вроде `prepared_pdfs/handfill_ready`;
- ручному переносу PDF между папками.

Рекомендуемый контрольный запуск:

```bash
python scripts/cleanup_duplicate_pdfs.py --report output/duplicate_check_after_export.csv
```

Затем визуальный контроль:

```bash
python scripts/cleanup_visual_duplicate_pdfs.py --report output/visual_duplicate_check_after_export.csv
```

Если скрипт нашел дубликаты:

```bash
python scripts/cleanup_duplicate_pdfs.py --delete --report output/duplicate_cleanup_after_export.csv
```

Если визуальный скрипт нашел дубликаты:

```bash
python scripts/cleanup_visual_duplicate_pdfs.py \
  --action move \
  --report output/visual_duplicate_cleanup_after_export.csv
```

После удаления можно снова проверить:

```bash
python scripts/cleanup_duplicate_pdfs.py --report output/duplicate_check_after_cleanup.csv
python scripts/cleanup_visual_duplicate_pdfs.py --report output/visual_duplicate_check_after_cleanup.csv
```
