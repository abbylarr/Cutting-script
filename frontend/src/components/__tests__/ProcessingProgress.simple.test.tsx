import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import ProcessingProgress from '../ProcessingProgress';
import { apiService } from '../../services/api';
import { ProcessingTask } from '../../types';

// Mock the API service
jest.mock('../../services/api');
const mockedApiService = apiService as jest.Mocked<typeof apiService>;

// Mock WebSocket service
jest.mock('../../services/websocket', () => ({
  websocketService: {
    connect: jest.fn().mockResolvedValue(undefined),
    subscribe: jest.fn(),
    unsubscribe: jest.fn(),
    disconnect: jest.fn(),
    isConnected: jest.fn().mockReturnValue(true),
  },
}));

// Mock react-router-dom
const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useParams: () => ({ taskId: 'test-task-id' }),
  useNavigate: () => mockNavigate,
}));

const renderWithRouter = (component: React.ReactElement) => {
  return render(
    <BrowserRouter>
      {component}
    </BrowserRouter>
  );
};

describe('ProcessingProgress Component - Simple Tests', () => {
  const mockTask: ProcessingTask = {
    task_id: 'test-task-id',
    user_id: 'test-user',
    status: 'processing',
    video_path: '/path/to/video.mp4',
    progress: 45,
    current_step: 'transcription',
    created_at: '2023-01-01T00:00:00Z',
    updated_at: '2023-01-01T00:05:00Z',
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders processing state with progress', async () => {
    mockedApiService.getTaskStatus.mockResolvedValue(mockTask);

    renderWithRouter(<ProcessingProgress />);

    await waitFor(() => {
      expect(screen.getByText('🎬 Обрабатываем ваше видео')).toBeInTheDocument();
    });

    expect(screen.getByText('Общий прогресс')).toBeInTheDocument();
    expect(screen.getByText('45%')).toBeInTheDocument();
  });

  test('renders completed state', async () => {
    const completedTask = { ...mockTask, status: 'completed' as const, progress: 100 };
    mockedApiService.getTaskStatus.mockResolvedValue(completedTask);

    renderWithRouter(<ProcessingProgress />);

    await waitFor(() => {
      expect(screen.getByText('✨ Обработка завершена!')).toBeInTheDocument();
    });

    expect(screen.getByText('Перейти к редактированию')).toBeInTheDocument();
  });

  test('shows processing steps', async () => {
    mockedApiService.getTaskStatus.mockResolvedValue(mockTask);

    renderWithRouter(<ProcessingProgress />);

    await waitFor(() => {
      expect(screen.getByText('Этапы обработки')).toBeInTheDocument();
    });

    // Check that some processing steps are displayed
    expect(screen.getByText(/Проверяем ваше видео/)).toBeInTheDocument();
    expect(screen.getAllByText(/Преобразуем речь в текст/)).toHaveLength(2); // Appears in both current step and timeline
  });
});