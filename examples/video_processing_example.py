"""
Example usage of video processing services.
"""
import asyncio
from pathlib import Path
from app.services.video_processor import (
    VideoValidationService,
    AudioExtractionService,
    SceneDetectionService
)


async def process_video_example(video_path: str):
    """
    Example of processing a video file through the complete pipeline.
    
    Args:
        video_path: Path to the video file to process
    """
    print(f"Processing video: {video_path}")
    
    # Step 1: Validate video
    print("1. Validating video...")
    validation_service = VideoValidationService()
    validation_result = await validation_service.validate_video(video_path)
    
    if not validation_result.is_valid:
        print(f"❌ Video validation failed: {validation_result.error}")
        return
    
    metadata = validation_result.metadata
    print(f"✅ Video is valid:")
    print(f"   Duration: {metadata.duration:.1f} seconds")
    print(f"   Resolution: {metadata.width}x{metadata.height}")
    print(f"   FPS: {metadata.fps}")
    print(f"   Codec: {metadata.codec}")
    print(f"   Format: {metadata.format}")
    
    # Step 2: Extract audio
    print("\n2. Extracting audio...")
    audio_service = AudioExtractionService()
    try:
        audio_path = await audio_service.extract_audio(video_path)
        print(f"✅ Audio extracted to: {audio_path}")
    except Exception as e:
        print(f"❌ Audio extraction failed: {e}")
        return
    
    # Step 3: Detect scenes
    print("\n3. Detecting scenes...")
    scene_service = SceneDetectionService()
    try:
        scenes = await scene_service.detect_scenes(video_path, min_scene_length=2.0)
        print(f"✅ Detected {len(scenes)} scenes:")
        
        for scene in scenes[:5]:  # Show first 5 scenes
            print(f"   Scene {scene.scene_number}: {scene.start_time:.1f}s - {scene.end_time:.1f}s ({scene.duration:.1f}s)")
        
        if len(scenes) > 5:
            print(f"   ... and {len(scenes) - 5} more scenes")
        
        # Get scene statistics
        stats = await scene_service.get_scene_statistics(scenes)
        print(f"\n📊 Scene Statistics:")
        print(f"   Total scenes: {stats['total_scenes']}")
        print(f"   Average duration: {stats['average_duration']:.1f}s")
        print(f"   Shortest scene: {stats['shortest_scene']:.1f}s")
        print(f"   Longest scene: {stats['longest_scene']:.1f}s")
        
    except Exception as e:
        print(f"❌ Scene detection failed: {e}")
        return
    
    # Step 4: Check video integrity
    print("\n4. Checking video integrity...")
    is_valid, error = await validation_service.check_video_integrity(video_path)
    if is_valid:
        print("✅ Video integrity check passed")
    else:
        print(f"❌ Video integrity check failed: {error}")
    
    print(f"\n🎉 Video processing completed successfully!")
    print(f"   Video: {video_path}")
    print(f"   Audio: {audio_path}")
    print(f"   Scenes: {len(scenes)} detected")


async def main():
    """Main example function."""
    # Example usage - replace with actual video path
    video_path = "example_video.mp4"
    
    if not Path(video_path).exists():
        print(f"❌ Video file not found: {video_path}")
        print("Please provide a valid video file path.")
        return
    
    await process_video_example(video_path)


if __name__ == "__main__":
    asyncio.run(main())