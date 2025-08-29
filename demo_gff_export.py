#!/usr/bin/env python3
"""
Демонстрация экспорта DOCX в формате ГФФ (Госфильмфонд).
"""

import asyncio
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.docx_generator import DOCXGeneratorService
from app.schemas.film_project import (
    MontageRow, FilmMetadata, ProjectSettings,
    ShotType, ColorType, TimecodeStandard
)


async def demo_gff_export():
    """Демонстрация экспорта в формате ГФФ."""
    
    print("🎬 Демонстрация экспорта монтажного листа в формате ГФФ")
    print("=" * 60)
    
    # Создаем метаданные фильма
    film_metadata = FilmMetadata(
        title="Весенние грёзы",
        production_company="Мосфильм",
        year=2024,
        country="Россия",
        screenwriters=["Александр Пушкин", "Михаил Лермонтов"],
        copyright_holders=["Мосфильм", "Министерство культуры РФ"],
        duration="01:45:30",
        episodes_count=1,
        format="Digital 4K",
        color_type=ColorType.COLOR,
        media_carrier="Жёсткий диск",
        original_language="Русский",
        subtitle_language="Английский",
        audio_language="Русский"
    )
    
    # Настройки проекта
    project_settings = ProjectSettings(
        timecode_start="01:00:00:00",
        standard=TimecodeStandard.GFF,
        fps=25.0
    )
    
    # Создаем монтажные строки
    montage_rows = [
        MontageRow(
            number=1,
            start_timecode="01:00:00:00",
            end_timecode="01:00:08:12",
            shot_type=ShotType.GENERAL,
            description="Фильм снят при государственной финансовой поддержке Министерства культуры Российской Федерации",
            dialogue="",
            speaker=None,
            has_music=False,
            special_tags=["НДП"]
        ),
        MontageRow(
            number=2,
            start_timecode="01:00:08:13",
            end_timecode="01:00:15:08",
            shot_type=ShotType.MEDIUM,
            description="Начальные титры. Название фильма на фоне весеннего пейзажа",
            dialogue="",
            speaker=None,
            has_music=True,
            special_tags=[]
        ),
        MontageRow(
            number=3,
            start_timecode="01:00:15:09",
            end_timecode="01:00:22:24",
            shot_type=ShotType.CLOSE,
            description="Крупный план главной героини у окна",
            dialogue="Какая прекрасная весна! Наконец-то пришло тепло.",
            speaker="Анна",
            has_music=False,
            special_tags=["ГЗК"]
        ),
        MontageRow(
            number=4,
            start_timecode="01:00:22:25",
            end_timecode="01:00:35:12",
            shot_type=ShotType.GENERAL,
            description="Общий план парка. Люди гуляют среди цветущих деревьев",
            dialogue="",
            speaker=None,
            has_music=True,
            special_tags=[]
        ),
        MontageRow(
            number=5,
            start_timecode="01:00:35:13",
            end_timecode="01:00:42:00",
            shot_type=ShotType.MEDIUM,
            description="Средний план. Встреча двух главных героев",
            dialogue="Здравствуйте! Какой замечательный день!",
            speaker="Иван",
            has_music=False,
            special_tags=[]
        ),
        MontageRow(
            number=6,
            start_timecode="01:00:42:01",
            end_timecode="01:00:48:15",
            shot_type=ShotType.CLOSE,
            description="Крупный план Анны. Улыбка",
            dialogue="Да, действительно! Весна всегда приносит надежду.",
            speaker="Анна",
            has_music=False,
            special_tags=["ГЗК"]
        ),
        MontageRow(
            number=7,
            start_timecode="01:00:48:16",
            end_timecode="01:00:55:24",
            shot_type=ShotType.DISTANT,
            description="Дальний план. Герои идут по аллее",
            dialogue="",
            speaker=None,
            has_music=True,
            special_tags=[]
        ),
        MontageRow(
            number=8,
            start_timecode="01:00:55:25",
            end_timecode="01:01:05:00",
            shot_type=ShotType.MEDIUM,
            description="Финальные титры",
            dialogue="",
            speaker=None,
            has_music=True,
            special_tags=["НДП"]
        ),
        MontageRow(
            number=9,
            start_timecode="01:01:05:01",
            end_timecode="01:01:08:00",
            shot_type=ShotType.DETAIL,
            description="Знак охраны авторского права.\n2024 год выпуска.",
            dialogue="",
            speaker=None,
            has_music=False,
            special_tags=[]
        )
    ]
    
    # Генерируем документ
    generator = DOCXGeneratorService()
    
    print(f"📝 Генерация документа для фильма: '{film_metadata.title}'")
    print(f"🎭 Производитель: {film_metadata.production_company}")
    print(f"📅 Год: {film_metadata.year}")
    print(f"⏱️  Количество планов: {len(montage_rows)}")
    print()
    
    # Проверка соответствия ГФФ
    print("🔍 Проверка соответствия требованиям ГФФ...")
    is_compliant, issues, report = await generator.validate_goskino_compliance(
        montage_rows,
        film_metadata,
        project_settings
    )
    
    if is_compliant:
        print("✅ Документ соответствует всем требованиям ГФФ")
    else:
        print("❌ Найдены проблемы:")
        for issue in issues:
            print(f"   - {issue}")
    
    print()
    print("📊 Отчет о соответствии:")
    for check, result in report["compliance_checks"].items():
        status = "✅" if result else "❌"
        check_names = {
            "metadata": "Метаданные",
            "timecodes": "Таймкоды", 
            "table_structure": "Структура таблицы",
            "content": "Содержимое"
        }
        print(f"   {status} {check_names.get(check, check)}")
    
    print()
    
    # Генерация документа
    print("📄 Генерация DOCX документа в формате ГФФ...")
    
    output_path = "montage_list_gff_format.docx"
    await generator.save_document_to_file(
        montage_rows,
        film_metadata,
        output_path,
        project_settings,
        use_gff_format=True
    )
    
    print(f"✅ Документ сохранен: {output_path}")
    
    # Статистика документа
    stats = await generator.get_document_statistics(montage_rows)
    
    print()
    print("📈 Статистика документа:")
    print(f"   📋 Всего планов: {stats['total_rows']}")
    print(f"   🎬 Планов с диалогами: {stats['rows_with_dialogue']} ({stats['dialogue_coverage_percent']:.1f}%)")
    print(f"   🎵 Планов с музыкой: {stats['rows_with_music']} ({stats['music_coverage_percent']:.1f}%)")
    print(f"   👥 Уникальных персонажей: {stats['unique_speakers']}")
    
    if stats['speaker_list']:
        print(f"   🗣️  Персонажи: {', '.join(stats['speaker_list'])}")
    
    print()
    print("🎯 Распределение типов планов:")
    for shot_type, count in stats['shot_type_distribution'].items():
        percentage = (count / stats['total_rows']) * 100
        print(f"   📹 {shot_type}: {count} ({percentage:.1f}%)")
    
    print()
    print("🎉 Экспорт завершен успешно!")
    print(f"📁 Откройте файл '{output_path}' для просмотра результата")


if __name__ == "__main__":
    asyncio.run(demo_gff_export())