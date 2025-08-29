#!/usr/bin/env python3
"""
Пример стандартной таблицы монтажа с 6 столбцами.

Показывает правильный формат таблицы монтажа согласно стандарту:
1) № плана
2) Начальный тайм-код плана (часы:мин.:сек.:кадры)
3) Конечный тайм-код плана (часы:мин.:сек.:кадры)
4) Вид плана
5) Содержание (описание) плана, титры
6) Монологи, разговоры, песни, субтитры. Музыка.
"""

import asyncio
from app.services.montage_table import MontageTableAssemblyService
from app.schemas.film_project import ProjectSettings, TimecodeStandard
from app.services.video_processor import Scene
from app.services.dialogue_mapping import SceneDialogue, DialogueSegment, DialogueMappingResult
from app.services.gpt_visual_analysis import SceneAnalysisResult
from app.services.visual_analysis import VisualAnalysisResult, ShotType as VisualShotType, SpecialTag
from app.services.music_detection import MusicDetectionResult, SceneMusicAnalysis


async def main():
    """Создать стандартную таблицу монтажа."""
    
    print("=== СТАНДАРТНАЯ ТАБЛИЦА МОНТАЖА ===\n")
    
    # Создаем реалистичные сцены документального фильма
    scenes = [
        Scene(start_time=0.0, end_time=12.5, duration=12.5, scene_number=1),
        Scene(start_time=13.0, end_time=28.3, duration=15.3, scene_number=2),
        Scene(start_time=29.0, end_time=45.8, duration=16.8, scene_number=3),
        Scene(start_time=46.5, end_time=62.2, duration=15.7, scene_number=4),
        Scene(start_time=63.0, end_time=78.4, duration=15.4, scene_number=5),
        Scene(start_time=79.2, end_time=95.0, duration=15.8, scene_number=6)
    ]
    
    # Создаем детальные диалоги
    dialogue_segments = [
        DialogueSegment(text="Добро пожаловать в документальный фильм 'Природа России'", speaker="Ведущий", start_time=2.0, end_time=6.5),
        DialogueSegment(text="Сегодня мы познакомимся с удивительным миром дикой природы", speaker="Ведущий", start_time=7.0, end_time=11.5),
        DialogueSegment(text="Эти величественные горы хранят множество тайн", speaker="Экскурсовод", start_time=15.0, end_time=19.0),
        DialogueSegment(text="Здесь, на высоте трех тысяч метров, обитают редкие животные", speaker="Экскурсовод", start_time=20.0, end_time=25.5),
        DialogueSegment(text="Бурый медведь - символ русской природы", speaker="Биолог", start_time=32.0, end_time=36.0),
        DialogueSegment(text="Его вес может достигать 300 килограммов", speaker="Биолог", start_time=37.0, end_time=41.0),
        DialogueSegment(text="Весной медведи выходят из спячки очень голодными", speaker="Биолог", start_time=48.0, end_time=53.0),
        DialogueSegment(text="Они питаются рыбой, ягодами и молодыми побегами", speaker="Биолог", start_time=54.0, end_time=59.0),
        DialogueSegment(text="Лес - это дом для тысяч видов животных и растений", speaker="Ведущий", start_time=65.0, end_time=70.0),
        DialogueSegment(text="Каждое дерево здесь живет уже более ста лет", speaker="Ведущий", start_time=71.0, end_time=75.5),
        DialogueSegment(text="Природа учит нас гармонии и бережному отношению к миру", speaker="Ведущий", start_time=82.0, end_time=88.0),
        DialogueSegment(text="Спасибо за внимание к нашему фильму", speaker="Ведущий", start_time=89.0, end_time=92.5)
    ]
    
    scene_dialogues = [
        SceneDialogue(scene_number=1, start_time=0.0, end_time=12.5, dialogue_segments=dialogue_segments[:2], 
                     full_text="Ведущий: Добро пожаловать в документальный фильм 'Природа России'. Сегодня мы познакомимся с удивительным миром дикой природы.", 
                     speakers=["Ведущий"]),
        SceneDialogue(scene_number=2, start_time=13.0, end_time=28.3, dialogue_segments=dialogue_segments[2:4], 
                     full_text="Экскурсовод: Эти величественные горы хранят множество тайн. Здесь, на высоте трех тысяч метров, обитают редкие животные.", 
                     speakers=["Экскурсовод"]),
        SceneDialogue(scene_number=3, start_time=29.0, end_time=45.8, dialogue_segments=dialogue_segments[4:6], 
                     full_text="Биолог: Бурый медведь - символ русской природы. Его вес может достигать 300 килограммов.", 
                     speakers=["Биолог"]),
        SceneDialogue(scene_number=4, start_time=46.5, end_time=62.2, dialogue_segments=dialogue_segments[6:8], 
                     full_text="Биолог: Весной медведи выходят из спячки очень голодными. Они питаются рыбой, ягодами и молодыми побегами.", 
                     speakers=["Биолог"]),
        SceneDialogue(scene_number=5, start_time=63.0, end_time=78.4, dialogue_segments=dialogue_segments[8:10], 
                     full_text="Ведущий: Лес - это дом для тысяч видов животных и растений. Каждое дерево здесь живет уже более ста лет.", 
                     speakers=["Ведущий"]),
        SceneDialogue(scene_number=6, start_time=79.2, end_time=95.0, dialogue_segments=dialogue_segments[10:12], 
                     full_text="Ведущий: Природа учит нас гармонии и бережному отношению к миру. Спасибо за внимание к нашему фильму.", 
                     speakers=["Ведущий"])
    ]
    
    dialogue_result = DialogueMappingResult(
        scene_dialogues=scene_dialogues, total_scenes=6, total_dialogue_segments=12, 
        unmapped_segments=[], processing_time=1.8
    )
    
    # Создаем детальный визуальный анализ
    visual_analysis_results = [
        SceneAnalysisResult(scene_index=0, scene=scenes[0], keyframes=[], 
                           visual_analysis=VisualAnalysisResult(shot_type=VisualShotType.GENERAL, 
                                                              description="Общий план телестудии с ведущим", 
                                                              text_in_frame="Природа России", 
                                                              special_tags=[SpecialTag.TEXT_OVERLAY], confidence_score=0.95)),
        SceneAnalysisResult(scene_index=1, scene=scenes[1], keyframes=[], 
                           visual_analysis=VisualAnalysisResult(shot_type=VisualShotType.DISTANT, 
                                                              description="Дальний план горного массива Кавказа", 
                                                              special_tags=[], confidence_score=0.92)),
        SceneAnalysisResult(scene_index=2, scene=scenes[2], keyframes=[], 
                           visual_analysis=VisualAnalysisResult(shot_type=VisualShotType.CLOSE, 
                                                              description="Крупный план бурого медведя", 
                                                              special_tags=[SpecialTag.OFF_SCREEN_VOICE], confidence_score=0.89)),
        SceneAnalysisResult(scene_index=3, scene=scenes[3], keyframes=[], 
                           visual_analysis=VisualAnalysisResult(shot_type=VisualShotType.MEDIUM, 
                                                              description="Средний план медведя у реки", 
                                                              special_tags=[], confidence_score=0.87)),
        SceneAnalysisResult(scene_index=4, scene=scenes[4], keyframes=[], 
                           visual_analysis=VisualAnalysisResult(shot_type=VisualShotType.GENERAL, 
                                                              description="Общий план таежного леса", 
                                                              special_tags=[], confidence_score=0.91)),
        SceneAnalysisResult(scene_index=5, scene=scenes[5], keyframes=[], 
                           visual_analysis=VisualAnalysisResult(shot_type=VisualShotType.GENERAL, 
                                                              description="Общий план заката в лесу", 
                                                              special_tags=[SpecialTag.DARKENING], confidence_score=0.88))
    ]
    
    # Создаем музыкальное сопровождение
    music_result = MusicDetectionResult(
        scene_analyses=[
            SceneMusicAnalysis(scene_number=1, start_time=0.0, end_time=12.5, has_music=True, 
                             music_segments=[], music_coverage=0.8, dominant_music_type="orchestral", average_music_confidence=0.85),
            SceneMusicAnalysis(scene_number=2, start_time=13.0, end_time=28.3, has_music=True, 
                             music_segments=[], music_coverage=0.6, dominant_music_type="ambient", average_music_confidence=0.75),
            SceneMusicAnalysis(scene_number=5, start_time=63.0, end_time=78.4, has_music=True, 
                             music_segments=[], music_coverage=0.7, dominant_music_type="nature", average_music_confidence=0.80),
            SceneMusicAnalysis(scene_number=6, start_time=79.2, end_time=95.0, has_music=True, 
                             music_segments=[], music_coverage=0.9, dominant_music_type="orchestral", average_music_confidence=0.88)
        ],
        total_scenes=6, scenes_with_music=4, total_music_duration=52.0, processing_time=2.5
    )
    
    # Генерируем таблицу монтажа
    settings = ProjectSettings(timecode_start="01:00:00:00", standard=TimecodeStandard.GFF, fps=25.0)
    service = MontageTableAssemblyService(settings)
    
    result = await service.generate_montage_table(
        scenes=scenes,
        dialogue_result=dialogue_result,
        visual_analysis_results=visual_analysis_results,
        music_detection_result=music_result
    )
    
    print("ТАБЛИЦА МОНТАЖА")
    print("Фильм: 'Природа России'")
    print("Стандарт: ГФФ, 25 fps, начало: 01:00:00:00")
    print("=" * 160)
    print()
    
    # Заголовки стандартных 6 столбцов
    print(f"{'№':>3} │ {'Начальный тайм-код':>17} │ {'Конечный тайм-код':>16} │ {'Вид плана':>12} │ {'Содержание (описание) плана, титры':>45} │ {'Монологи, разговоры, песни, субтитры. Музыка.':>55}")
    print("─" * 160)
    
    # Экспортируем в стандартный формат
    standard_rows = service.export_to_standard_format(result.montage_rows)
    
    for i, row in enumerate(standard_rows):
        # Ограничиваем длину для красивого отображения
        content = row["Содержание (описание) плана, титры"]
        content = content[:43] + ".." if len(content) > 45 else content
        
        audio = row["Монологи, разговоры, песни, субтитры. Музыка."]
        audio = audio[:53] + ".." if len(audio) > 55 else audio
        
        print(f"{row['№ плана']:>3} │ {row['Начальный тайм-код плана']:>17} │ {row['Конечный тайм-код плана']:>16} │ {row['Вид плана']:>12} │ {content:>45} │ {audio:>55}")
    
    print("─" * 160)
    print()
    
    # Статистика
    stats = result.statistics
    print("СТАТИСТИКА ФИЛЬМА:")
    print(f"• Общая продолжительность: {stats['total_duration']:.1f} сек ({stats['total_duration']//60:.0f} мин {stats['total_duration']%60:.0f} сек)")
    print(f"• Количество планов: {stats['total_rows']}")
    print(f"• Средняя длительность плана: {stats['average_scene_duration']:.1f} сек")
    print(f"• Покрытие диалогами: {stats['dialogue_coverage']:.1%}")
    print(f"• Покрытие музыкой: {stats['music_coverage']:.1%}")
    print(f"• Участники: {', '.join(stats['speaker_list'])}")
    
    print(f"\nРАСПРЕДЕЛЕНИЕ ПЛАНОВ:")
    for shot_type, count in stats['shot_type_distribution'].items():
        percentage = (count / stats['total_rows']) * 100
        print(f"• {shot_type}: {count} ({percentage:.1f}%)")
    
    print(f"\nВремя обработки: {result.processing_time:.3f} сек")
    
    # Демонстрация экспорта данных
    print(f"\n=== ЭКСПОРТ В СТАНДАРТНЫЙ ФОРМАТ ===")
    print("Данные готовы для экспорта в Excel, CSV или другие форматы:")
    print()
    
    # Показываем первые 3 строки как пример
    for i, row in enumerate(standard_rows[:3]):
        print(f"Строка {i+1}:")
        for column, value in row.items():
            print(f"  {column}: {value}")
        print()


if __name__ == "__main__":
    asyncio.run(main())