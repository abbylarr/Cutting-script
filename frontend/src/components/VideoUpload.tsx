import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import styled from 'styled-components';
import { FilmMetadata, ProjectSettings } from '../types';
import { apiService } from '../services/api';
import FilmMetadataForm from './FilmMetadataForm';
import ProjectSettingsForm from './ProjectSettingsForm';

const UploadContainer = styled.div`
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
`;

const Title = styled.h1`
  text-align: center;
  color: #333;
  margin-bottom: 30px;
`;

const DropzoneContainer = styled.div<{ isDragActive: boolean; hasFile: boolean }>`
  border: 2px dashed ${props => props.isDragActive ? '#007bff' : props.hasFile ? '#28a745' : '#ddd'};
  border-radius: 8px;
  padding: 40px;
  text-align: center;
  background-color: ${props => props.isDragActive ? '#f8f9fa' : 'white'};
  cursor: pointer;
  transition: all 0.2s ease;
  margin-bottom: 30px;

  &:hover {
    border-color: #007bff;
    background-color: #f8f9fa;
  }
`;

const DropzoneText = styled.p`
  margin: 0;
  font-size: 16px;
  color: #666;
`;

const FileInfo = styled.div`
  background-color: #e9ecef;
  padding: 15px;
  border-radius: 4px;
  margin-bottom: 20px;
`;

const ModeSelector = styled.div`
  display: flex;
  gap: 20px;
  margin-bottom: 30px;
  justify-content: center;
`;

const ModeButton = styled.button<{ active: boolean }>`
  padding: 12px 24px;
  border: 2px solid ${props => props.active ? '#007bff' : '#ddd'};
  background-color: ${props => props.active ? '#007bff' : 'white'};
  color: ${props => props.active ? 'white' : '#333'};
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;

  &:hover {
    border-color: #007bff;
    background-color: ${props => props.active ? '#0056b3' : '#f8f9fa'};
  }
`;

const SrtUploadContainer = styled.div`
  margin-top: 20px;
  padding: 20px;
  border: 1px solid #ddd;
  border-radius: 4px;
  background-color: #f8f9fa;
`;

const ProgressBar = styled.div`
  width: 100%;
  height: 20px;
  background-color: #e9ecef;
  border-radius: 10px;
  overflow: hidden;
  margin: 20px 0;
`;

const ProgressFill = styled.div<{ progress: number }>`
  width: ${props => props.progress}%;
  height: 100%;
  background-color: #007bff;
  transition: width 0.3s ease;
`;

const SubmitButton = styled.button`
  width: 100%;
  padding: 15px;
  background-color: #28a745;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 16px;
  cursor: pointer;
  margin-top: 20px;

  &:hover {
    background-color: #218838;
  }

  &:disabled {
    background-color: #6c757d;
    cursor: not-allowed;
  }
`;

interface VideoUploadProps {
  onTaskCreated: (taskId: string) => void;
}

const VideoUpload: React.FC<VideoUploadProps> = ({ onTaskCreated }) => {
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [srtFile, setSrtFile] = useState<File | null>(null);
  const [mode, setMode] = useState<'auto' | 'srt'>('auto');
  const [metadata, setMetadata] = useState<FilmMetadata>({
    title: '',
    production_company: '',
    year: new Date().getFullYear(),
    country: 'Россия',
    screenwriters: [],
    copyright_holders: [],
    duration: '',
    episodes_count: 1,
    format: 'HD',
    color_type: 'Цветной',
    media_carrier: 'Цифровой',
    original_language: 'Русский',
    subtitle_language: 'Русский',
    audio_language: 'Русский'
  });
  const [settings, setSettings] = useState<ProjectSettings>({
    timecode_start: '01:00:00:00',
    standard: 'ГФФ',
    fps: 25
  });
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);

  const onVideoDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      setVideoFile(acceptedFiles[0]);
    }
  }, []);

  const onSrtDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      setSrtFile(acceptedFiles[0]);
    }
  }, []);

  const { getRootProps: getVideoRootProps, getInputProps: getVideoInputProps, isDragActive: isVideoDragActive } = useDropzone({
    onDrop: onVideoDrop,
    accept: {
      'video/*': ['.mp4', '.avi', '.mov', '.mkv', '.wmv']
    },
    multiple: false
  });

  const { getRootProps: getSrtRootProps, getInputProps: getSrtInputProps, isDragActive: isSrtDragActive } = useDropzone({
    onDrop: onSrtDrop,
    accept: {
      'text/plain': ['.srt']
    },
    multiple: false
  });

  const handleSubmit = async () => {
    if (!videoFile || !metadata.title) {
      alert('Пожалуйста, выберите видеофайл и заполните название фильма');
      return;
    }

    if (mode === 'srt' && !srtFile) {
      alert('Пожалуйста, выберите SRT файл для режима с субтитрами');
      return;
    }

    setIsUploading(true);
    setUploadProgress(0);

    try {
      const uploadSettings = {
        ...settings,
        use_srt: mode === 'srt'
      };

      const response = await apiService.uploadVideo(
        videoFile,
        metadata,
        uploadSettings,
        setUploadProgress
      );

      if (mode === 'srt' && srtFile) {
        await apiService.uploadSrt(response.task_id, srtFile);
      }

      onTaskCreated(response.task_id);
    } catch (error) {
      console.error('Upload failed:', error);
      alert('Ошибка при загрузке файла. Попробуйте еще раз.');
    } finally {
      setIsUploading(false);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <UploadContainer>
      <Title>Создание монтажного листа</Title>

      {/* Video Upload */}
      <DropzoneContainer 
        {...getVideoRootProps()} 
        isDragActive={isVideoDragActive}
        hasFile={!!videoFile}
      >
        <input {...getVideoInputProps()} />
        {videoFile ? (
          <DropzoneText>
            Выбран файл: {videoFile.name} ({formatFileSize(videoFile.size)})
          </DropzoneText>
        ) : (
          <DropzoneText>
            {isVideoDragActive 
              ? 'Отпустите файл здесь...' 
              : 'Перетащите видеофайл сюда или нажмите для выбора'
            }
          </DropzoneText>
        )}
      </DropzoneContainer>

      {/* Mode Selection */}
      <ModeSelector>
        <ModeButton 
          active={mode === 'auto'} 
          onClick={() => setMode('auto')}
        >
          Автоматическая транскрипция
        </ModeButton>
        <ModeButton 
          active={mode === 'srt'} 
          onClick={() => setMode('srt')}
        >
          Загрузить SRT файл
        </ModeButton>
      </ModeSelector>

      {/* SRT Upload (if SRT mode selected) */}
      {mode === 'srt' && (
        <SrtUploadContainer>
          <h3>Загрузка SRT файла</h3>
          <DropzoneContainer 
            {...getSrtRootProps()} 
            isDragActive={isSrtDragActive}
            hasFile={!!srtFile}
          >
            <input {...getSrtInputProps()} />
            {srtFile ? (
              <DropzoneText>
                Выбран SRT файл: {srtFile.name}
              </DropzoneText>
            ) : (
              <DropzoneText>
                {isSrtDragActive 
                  ? 'Отпустите SRT файл здесь...' 
                  : 'Перетащите SRT файл сюда или нажмите для выбора'
                }
              </DropzoneText>
            )}
          </DropzoneContainer>
        </SrtUploadContainer>
      )}

      {/* Film Metadata Form */}
      <FilmMetadataForm 
        metadata={metadata} 
        onChange={setMetadata} 
      />

      {/* Project Settings Form */}
      <ProjectSettingsForm 
        settings={settings} 
        onChange={setSettings} 
      />

      {/* Upload Progress */}
      {isUploading && (
        <div>
          <p>Загрузка файла: {uploadProgress}%</p>
          <ProgressBar>
            <ProgressFill progress={uploadProgress} />
          </ProgressBar>
        </div>
      )}

      {/* Submit Button */}
      <SubmitButton 
        onClick={handleSubmit} 
        disabled={isUploading || !videoFile || !metadata.title}
      >
        {isUploading ? 'Загрузка...' : 'Создать монтажный лист'}
      </SubmitButton>
    </UploadContainer>
  );
};

export default VideoUpload;