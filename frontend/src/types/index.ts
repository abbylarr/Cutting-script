export interface FilmMetadata {
  title: string;
  production_company: string;
  year: number;
  country: string;
  screenwriters: string[];
  copyright_holders: string[];
  duration: string;
  episodes_count: number;
  format: string;
  color_type: 'Цветной' | 'Черно-белый';
  media_carrier: string;
  original_language: string;
  subtitle_language: string;
  audio_language: string;
}

export interface ProjectSettings {
  timecode_start: '01:00:00:00' | '00:00:00:00';
  standard: 'ГФФ' | 'Красногорский';
  fps: number;
}

export interface MontageRow {
  number: number;
  start_timecode: string;
  end_timecode: string;
  shot_type: ShotType;
  description: string;
  dialogue: string;
  speaker?: string;
  has_music: boolean;
}

export type ShotType = 'Дальний' | 'Общий' | 'Средний' | 'Крупный' | 'Деталь';

export type TaskStatus = 'pending' | 'processing' | 'completed' | 'failed';

export interface ProcessingTask {
  task_id: string;
  user_id: string;
  status: TaskStatus;
  video_path: string;
  srt_path?: string;
  progress: number;
  current_step: string;
  result?: MontageRow[];
  error?: string;
  created_at: string;
  updated_at: string;
}

export interface Project {
  id: string;
  user_id: string;
  task_id: string;
  title: string;
  metadata: FilmMetadata;
  montage_rows?: MontageRow[];
  created_at: string;
  updated_at: string;
}

export interface User {
  id: string;
  email: string;
  balance: number;
  created_at: string;
}

export interface UploadProgress {
  loaded: number;
  total: number;
  percentage: number;
}

export interface ProcessingStep {
  name: string;
  description: string;
  progress: number;
  eta_seconds?: number;
}