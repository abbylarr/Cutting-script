#!/usr/bin/env python3
"""
Detailed example showing complete montage table with all columns.
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
    """Generate detailed montage table example."""
    
    print("=== Полная таблица монтажа ===\n")
    
    # Create realistic scenes
    scenes = [
        Scene(start_time=0.0, end_time=8.5, duration=8.5, scene_number=1),
        Scene(start_time=9.0, end_time=15.2, duration=6.2, scene_number=2),
        Scene(start_time=16.0, end_time=22.8, duration=6.8, scene_number=3),
        Scene(start_time=23.5, end_time=31.0, duration=7.5, scene_number=4),
        Scene(start_time=32.0, end_time=38.4, duration=6.4, scene_number=5)
    ]
    
    # Create detailed dialogue
    dialogue_segments = [
        DialogueSegment(text="Добро пожаловать в наш документальный фильм о природе.", speaker="Ведущий", start_time=1.0, end_time=4.5),
        DialogueSegment(text="Сегодня мы отправимся в удивительное путешествие.", speaker="Ведущий", start_time=5.0, end_time=8.0),
        DialogueSegment(text="Посмотрите на эти величественные горы!", speaker="Экскурсовод", start_time=10.0, end_time=13.0),
        DialogueSegment(text="Здесь обитают редкие виды животных.", speaker="Биолог", start_time=24.0, end_time=27.5),
        DialogueSegment(text="Музыка природы завораживает своей красотой.", speaker="Ведущий", start_time=33.0, end_time=37.0)
    ]
    
    scene_dialogues = [
        SceneDialogue(scene_number=1, start_time=0.0, end_time=8.5, dialogue_segments=dialogue_segments[:2], 
                     full_text="Ведущий: Добро пожаловать в наш документальный фильм о природе. Сегодня мы отправимся в удивительное путешествие.", 
                     speakers=["Ведущий"]),
        SceneDialogue(scene_number=2, start_time=9.0, end_time=15.2, dialogue_segments=[dialogue_segments[2]], 
                     full_text="Экскурсовод: Посмотрите на эти величественные горы!", 
                     speakers=["Экскурсовод"]),
        SceneDialogue(scene_number=4, start_time=23.5, end_time=31.0, dialogue_segments=[dialogue_segments[3]], 
                     full_text="Биолог: Здесь обитают редкие виды животных.", 
                     speakers=["Биолог"]),
        SceneDialogue(scene_number=5, start_time=32.0, end_time=38.4, dialogue_segments=[dialogue_segments[4]], 
                     full_text="Ведущий: Музыка природы завораживает своей красотой.", 
                     speakers=["Ведущий"])
    ]
    
    dialogue_result = DialogueMappingResult(
        scene_dialogues=scene_dialogues, total_scenes=5, total_dialogue_segments=5, 
        unmapped_segments=[], processing_time=1.2
    )
    
    # Create detailed visual analysis
    visual_analysis_results = [
        SceneAnalysisResult(scene_index=0, scene=scenes[0], keyframes=[], 
                           visual_analysis=VisualAnalysisResult(shot_type=VisualShotType.GENERAL, 
                                                              description="Общий план студии с ведущим", 
                                                              text_in_frame="Природа России", 
                                                              special_tags=[SpecialTag.TEXT_OVERLAY], confidence_score=0.95)),
        SceneAnalysisResult(scene_index=1, scene=scenes[1], keyframes=[], 
                           visual_analysis=VisualAnalysisResult(shot_type=VisualShotType.DISTANT, 
                                                              description="Дальний план горного пейзажа", 
                                                              special_tags=[], confidence_score=0.88)),
        SceneAnalysisResult(scene_index=2, scene=scenes[2], keyframes=[], 
                           visual_analysis=VisualAnalysisResult(shot_type=VisualShotType.MEDIUM, 
                                                              description="Средний план леса с животными", 
                                                              special_tags=[], confidence_score=0.82)),
        SceneAnalysisResult(scene_index=3, scene=scenes[3], keyframes=[], 
                           visual_analysis=VisualAnalysisResult(shot_type=VisualShotType.CLOSE, 
                                                              description="Крупный план редкого животного", 
                                                              special_tags=[SpecialTag.OFF_SCREEN_VOICE], confidence_score=0.91)),
        SceneAnalysisResult(scene_index=4, scene=scenes[4], keyframes=[], 
                           visual_analysis=VisualAnalysisResult(shot_type=VisualShotType.GENERAL, 
                                                              description="Общий план заката с затемнением", 
                                                              special_tags=[SpecialTag.DARKENING], confidence_score=0.87))
    ]
    
    # Create music detection
    music_result = MusicDetectionResult(
        scene_analyses=[
            SceneMusicAnalysis(scene_number=1, start_time=0.0, end_time=8.5, has_music=True, 
                             music_segments=[], music_coverage=0.6, dominant_music_type="background", average_music_confidence=0.7),
            SceneMusicAnalysis(scene_number=3, start_time=16.0, end_time=22.8, has_music=True, 
                             music_segments=[], music_coverage=0.8, dominant_music_type="ambient", average_music_confidence=0.75),
            SceneMusicAnalysis(scene_number=5, start_time=32.0, end_time=38.4, has_music=True, 
                             music_segments=[], music_coverage=0.9, dominant_music_type="orchestral", average_music_confidence=0.85)
        ],
        total_scenes=5, scenes_with_music=3, total_music_duration=18.7, processing_time=2.1
    )
    
    # Generate montage table
    settings = ProjectSettings(timecode_start="01:00:00:00", standard=TimecodeStandard.GFF, fps=25.0)
    service = MontageTableAssemblyService(settings)
    
    result = await service.generate_montage_table(
        scenes=scenes,
        dialogue_result=dialogue_result,
        visual_analysis_results=visual_analysis_results,
        music_detection_result=music_result
    )
    
    print("ТАБЛИЦА МОНТАЖА")
    print("=" * 120)
    print()
    
    # Header - стандартные 6 столбцов таблицы монтажа
    print(f"{'№':>3} │ {'Начальный тайм-код':>16} │ {'Конечный тайм-код':>15} │ {'Вид плана':>12} │ {'Содержание (описание) плана, титры':>40} │ {'Монологи, разговоры, песни, субтитры. Музыка.':>50}")
    print("─" * 140)
    
    # Rows
    for row in result.montage_rows:
        # Столбец 5: Содержание (описание) плана, титры
        content = row.description
        if row.special_tags:
            # Добавляем специальные теги к описанию
            tags_text = ", ".join(row.special_tags)
            content = f"{content}. {tags_text}"
        content = content[:38] + ".." if len(content) > 40 else content
        
        # Столбец 6: Монологи, разговоры, песни, субтитры. Музыка.
        audio_content = ""
        if row.dialogue:
            audio_content = row.dialogue
        if row.has_music:
            music_text = "Музыка"
            if audio_content:
                audio_content = f"{audio_content}. {music_text}"
            else:
                audio_content = music_text
        audio_content = audio_content[:48] + ".." if len(audio_content) > 50 else audio_content
        
        print(f"{row.number:>3} │ {row.start_timecode:>16} │ {row.end_timecode:>15} │ {row.shot_type.value:>12} │ {content:>40} │ {audio_content:>50}")
    
    print("─" * 120)
    print()
    
    # Statistics
    stats = result.statistics
    print("СТАТИСТИКА:")
    print(f"• Общая продолжительность: {stats['total_duration']:.1f} сек")
    print(f"• Средняя длительность сцены: {stats['average_scene_duration']:.1f} сек")
    print(f"• Покрытие диалогами: {stats['dialogue_coverage']:.1%}")
    print(f"• Покрытие музыкой: {stats['music_coverage']:.1%}")
    print(f"• Уникальных спикеров: {stats['unique_speakers']}")
    print(f"• Спикеры: {', '.join(stats['speaker_list'])}")
    
    print(f"\nРаспределение планов:")
    for shot_type, count in stats['shot_type_distribution'].items():
        print(f"• {shot_type}: {count}")
    
    print(f"\nСпециальные теги:")
    for tag, count in stats['special_tag_distribution'].items():
        print(f"• {tag}: {count}")
    
    print(f"\nВремя обработки: {result.processing_time:.3f} сек")
    print(f"Ошибки валидации: {len(result.validation_errors)}")


if __name__ == "__main__":
    asyncio.run(main())