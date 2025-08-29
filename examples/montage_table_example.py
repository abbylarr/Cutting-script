#!/usr/bin/env python3
"""
Example demonstrating montage table generation and formatting.

This example shows how to use the MontageTableAssemblyService to generate
montage tables from processed video data with advanced timecode features.
"""

import asyncio
from app.services.montage_table import MontageTableAssemblyService, TimecodeService
from app.schemas.film_project import ProjectSettings, TimecodeStandard
from app.services.video_processor import Scene
from app.services.dialogue_mapping import SceneDialogue, DialogueSegment, DialogueMappingResult


async def main():
    """Demonstrate montage table generation."""
    
    print("=== Montage Table Generation Example ===\n")
    
    # Create sample scenes
    scenes = [
        Scene(start_time=0.0, end_time=5.0, duration=5.0, scene_number=1),
        Scene(start_time=5.5, end_time=12.0, duration=6.5, scene_number=2),
        Scene(start_time=13.0, end_time=18.0, duration=5.0, scene_number=3),
        Scene(start_time=19.0, end_time=25.0, duration=6.0, scene_number=4)
    ]
    
    print(f"Input scenes: {len(scenes)} scenes")
    for scene in scenes:
        print(f"  Scene {scene.scene_number}: {scene.start_time:.1f}s - {scene.end_time:.1f}s ({scene.duration:.1f}s)")
    
    # Create sample dialogue
    dialogue_segments = [
        DialogueSegment(
            text="Добро пожаловать в наш фильм!",
            speaker="Рассказчик",
            start_time=1.0,
            end_time=3.5
        ),
        DialogueSegment(
            text="Это очень интересная история.",
            speaker="Главный герой",
            start_time=6.0,
            end_time=9.0
        ),
        DialogueSegment(
            text="Музыка создает особую атмосферу.",
            speaker="Рассказчик",
            start_time=20.0,
            end_time=23.0
        )
    ]
    
    scene_dialogues = [
        SceneDialogue(
            scene_number=1,
            start_time=0.0,
            end_time=5.0,
            dialogue_segments=[dialogue_segments[0]],
            full_text="Рассказчик: Добро пожаловать в наш фильм!",
            speakers=["Рассказчик"]
        ),
        SceneDialogue(
            scene_number=2,
            start_time=5.5,
            end_time=12.0,
            dialogue_segments=[dialogue_segments[1]],
            full_text="Главный герой: Это очень интересная история.",
            speakers=["Главный герой"]
        ),
        SceneDialogue(
            scene_number=4,
            start_time=19.0,
            end_time=25.0,
            dialogue_segments=[dialogue_segments[2]],
            full_text="Рассказчик: Музыка создает особую атмосферу.",
            speakers=["Рассказчик"]
        )
    ]
    
    dialogue_result = DialogueMappingResult(
        scene_dialogues=scene_dialogues,
        total_scenes=4,
        total_dialogue_segments=3,
        unmapped_segments=[],
        processing_time=1.0
    )
    
    # Create sample visual analysis with special tags
    from app.services.gpt_visual_analysis import SceneAnalysisResult
    from app.services.visual_analysis import VisualAnalysisResult, ShotType as VisualShotType, SpecialTag
    
    visual_analysis_results = [
        SceneAnalysisResult(
            scene_index=0,
            scene=scenes[0],
            keyframes=[],
            visual_analysis=VisualAnalysisResult(
                shot_type=VisualShotType.GENERAL,
                description="Общий план города с надписью",
                text_in_frame="Добро пожаловать",
                special_tags=[SpecialTag.TEXT_OVERLAY],
                confidence_score=0.9
            )
        ),
        SceneAnalysisResult(
            scene_index=1,
            scene=scenes[1],
            keyframes=[],
            visual_analysis=VisualAnalysisResult(
                shot_type=VisualShotType.CLOSE,
                description="Крупный план главного героя",
                special_tags=[SpecialTag.OFF_SCREEN_VOICE],
                confidence_score=0.85
            )
        ),
        SceneAnalysisResult(
            scene_index=3,
            scene=scenes[3],
            keyframes=[],
            visual_analysis=VisualAnalysisResult(
                shot_type=VisualShotType.MEDIUM,
                description="Средний план с затемнением",
                special_tags=[SpecialTag.DARKENING],
                confidence_score=0.8
            )
        )
    ]
    
    # Create sample music detection
    from app.services.music_detection import MusicDetectionResult, SceneMusicAnalysis
    
    music_result = MusicDetectionResult(
        scene_analyses=[
            SceneMusicAnalysis(
                scene_number=3,  # Third scene has background music
                start_time=13.0,
                end_time=18.0,
                has_music=True,
                music_segments=[],
                music_coverage=0.8,
                dominant_music_type="background",
                average_music_confidence=0.75
            ),
            SceneMusicAnalysis(
                scene_number=4,  # Fourth scene has foreground music
                start_time=19.0,
                end_time=25.0,
                has_music=True,
                music_segments=[],
                music_coverage=0.9,
                dominant_music_type="foreground",
                average_music_confidence=0.85
            )
        ],
        total_scenes=4,
        scenes_with_music=2,
        total_music_duration=11.0,
        processing_time=1.5
    )
    
    print(f"\nDialogue mapping: {len(scene_dialogues)} scenes with dialogue")
    print(f"Visual analysis: {len(visual_analysis_results)} scenes analyzed")
    print(f"Music detection: {music_result.scenes_with_music} scenes with music")
    
    # Test different project settings
    test_cases = [
        {
            "name": "ГФФ Standard (25 fps, start at 01:00:00:00)",
            "settings": ProjectSettings(
                timecode_start="01:00:00:00",
                standard=TimecodeStandard.GFF,
                fps=25.0
            )
        },
        {
            "name": "Красногорский Standard (24 fps, start at 00:00:00:00)",
            "settings": ProjectSettings(
                timecode_start="00:00:00:00",
                standard=TimecodeStandard.KRASNOGORSKY,
                fps=24.0
            )
        },
        {
            "name": "High Frame Rate (50 fps)",
            "settings": ProjectSettings(
                timecode_start="01:00:00:00",
                standard=TimecodeStandard.GFF,
                fps=50.0
            )
        }
    ]
    
    for test_case in test_cases:
        print(f"\n=== {test_case['name']} ===")
        
        # Create service with specific settings
        service = MontageTableAssemblyService(test_case['settings'])
        
        # Generate montage table
        result = await service.generate_montage_table(
            scenes=scenes,
            dialogue_result=dialogue_result,
            visual_analysis_results=visual_analysis_results,
            music_detection_result=music_result
        )
        
        print(f"Generated {len(result.montage_rows)} montage rows")
        print(f"Processing time: {result.processing_time:.3f}s")
        print(f"Validation errors: {len(result.validation_errors)}")
        
        if result.validation_errors:
            for error in result.validation_errors:
                print(f"  - {error}")
        
        # Display montage table - стандартные 6 столбцов
        print("\nТаблица монтажа:")
        print("№  | Начальный тайм-код | Конечный тайм-код | Вид плана | Содержание плана, титры        | Монологи, разговоры, музыка")
        print("---|-------------------|-------------------|-----------|--------------------------------|-----------------------------")
        
        for row in result.montage_rows:
            # Столбец 5: Содержание (описание) плана, титры
            content = row.description
            if row.special_tags:
                tags_text = ", ".join(row.special_tags)
                content = f"{content}. {tags_text}"
            content = content[:30] + "..." if len(content) > 30 else content
            
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
            audio_content = audio_content[:27] + "..." if len(audio_content) > 27 else audio_content
            
            print(f"{row.number:2d} | {row.start_timecode:17s} | {row.end_timecode:17s} | {row.shot_type.value:9s} | {content:30s} | {audio_content}")
        
        # Show statistics
        stats = result.statistics
        print(f"\nStatistics:")
        print(f"  - Total duration: {stats['total_duration']:.1f}s")
        print(f"  - Average scene duration: {stats['average_scene_duration']:.1f}s")
        print(f"  - Dialogue coverage: {stats['dialogue_coverage']:.1%}")
        print(f"  - Unique speakers: {stats['unique_speakers']}")
        
        # Show timecode info
        tc_info = service.timecode_service.get_timecode_info()
        print(f"\nTimecode Configuration:")
        print(f"  - Standard: {tc_info['standard']}")
        print(f"  - Frame rate: {tc_info['fps']} fps")
        print(f"  - Frame duration: {tc_info['frame_duration']:.4f}s")
        print(f"  - Start time: {tc_info['start_time']}")
    
    # Demonstrate advanced timecode features
    print(f"\n=== Advanced Timecode Features ===")
    
    # Frame rate detection simulation
    print("\n1. Frame Rate Detection:")
    detected_fps = 23.976  # Common cinema frame rate
    
    settings = ProjectSettings(
        timecode_start="01:00:00:00",
        standard=TimecodeStandard.GFF,
        fps=25.0
    )
    
    service = TimecodeService(settings, detected_fps=detected_fps)
    print(f"   Detected FPS: {detected_fps}")
    print(f"   Validated FPS: {service.fps}")
    
    # Timecode validation
    print("\n2. Timecode Validation:")
    test_timecodes = [
        "01:23:45:12",  # Valid
        "01:60:45:12",  # Invalid minutes
        "01:23:45:25",  # Invalid frames for 25fps
        "1:23:45:12",   # Invalid format
    ]
    
    for tc in test_timecodes:
        valid, error = service.validate_timecode_format(tc)
        status = "✓ Valid" if valid else f"✗ Invalid: {error}"
        print(f"   {tc:12s} -> {status}")
    
    # Scene continuity adjustment
    print("\n3. Scene Continuity Adjustment:")
    print("   Original scenes:")
    for scene in scenes[:2]:
        print(f"     Scene {scene.scene_number}: {scene.start_time:.3f}s - {scene.end_time:.3f}s")
    
    adjusted_scenes = service.ensure_scene_continuity(scenes[:2])
    print("   Adjusted for continuity:")
    for scene in adjusted_scenes:
        print(f"     Scene {scene.scene_number}: {scene.start_time:.3f}s - {scene.end_time:.3f}s")
    
    gap = adjusted_scenes[1].start_time - adjusted_scenes[0].end_time
    print(f"   Gap between scenes: {gap:.4f}s (expected: {service.frame_duration:.4f}s)")
    
    print("\n=== Example Complete ===")


if __name__ == "__main__":
    asyncio.run(main())