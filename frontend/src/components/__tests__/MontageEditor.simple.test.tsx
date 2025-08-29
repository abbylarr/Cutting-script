import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import userEvent from '@testing-library/user-event';
import MontageEditor from '../MontageEditor';
import { apiService } from '../../services/api';
import { ProcessingTask } from '../../types';

// Mock the API service
jest.mock('../../services/api');
const mockedApiService = apiService as jest.Mocked<typeof apiService>;

// Mock ReactPlayer
jest.mock('react-player', () => {
  const mockReact = require('react');
  return mockReact.forwardRef<any, any>((props: any, ref: any) => (
    mockReact.createElement('div', { 
      'data-testid': 'react-player', 
      ref,
      onClick: () => props.onProgress?.({ played: 0.5, playedSeconds: 30 })
    }, 'Mock Video Player')
  ));
});

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

describe('MontageEditor Component - Simple Tests', () => {
  const mockTask: ProcessingTask = {
    task_id: 'test-task-id',
    user_id: 'test-user',
    status: 'completed',
    video_path: '/path/to/video.mp4',
    progress: 100,
    current_step: 'completed',
    created_at: '2023-01-01T00:00:00Z',
    updated_at: '2023-01-01T00:05:00Z',
    result: [
      {
        number: 1,
        start_timecode: '01:00:00:00',
        end_timecode: '01:00:05:00',
        shot_type: 'Общий',
        description: 'Открывающая сцена',
        dialogue: 'Привет, мир!',
        speaker: 'Спикер 1',
        has_music: false
      }
    ]
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders loading state initially', () => {
    mockedApiService.getTaskStatus.mockImplementation(() => 
      new Promise(() => {}) // Never resolves to keep loading state
    );

    renderWithRouter(<MontageEditor />);
    
    expect(screen.getByText('Загрузка монтажного листа...')).toBeInTheDocument();
  });

  test('renders montage editor with video player and table', async () => {
    mockedApiService.getTaskStatus.mockResolvedValue(mockTask);

    renderWithRouter(<MontageEditor />);

    await waitFor(() => {
      expect(screen.getByText('Монтажный лист')).toBeInTheDocument();
    });

    // Check video player is rendered
    expect(screen.getByTestId('react-player')).toBeInTheDocument();
    expect(screen.getByText('Видеоплеер')).toBeInTheDocument();

    // Check table headers
    expect(screen.getByText('№')).toBeInTheDocument();
    expect(screen.getByText('Начало')).toBeInTheDocument();
    expect(screen.getByText('Конец')).toBeInTheDocument();
    expect(screen.getByText('Тип плана')).toBeInTheDocument();
    expect(screen.getByText('Описание')).toBeInTheDocument();
    expect(screen.getByText('Диалоги')).toBeInTheDocument();
    expect(screen.getByText('Спикер')).toBeInTheDocument();
  });

  test('displays montage data correctly', async () => {
    mockedApiService.getTaskStatus.mockResolvedValue(mockTask);

    renderWithRouter(<MontageEditor />);

    await waitFor(() => {
      expect(screen.getByDisplayValue('01:00:00:00')).toBeInTheDocument();
    });

    // Check row data
    expect(screen.getByDisplayValue('01:00:05:00')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Открывающая сцена')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Привет, мир!')).toBeInTheDocument();
    expect(screen.getByText('Спикер 1')).toBeInTheDocument();
  });

  test('handles cell editing', async () => {
    const user = userEvent.setup();
    mockedApiService.getTaskStatus.mockResolvedValue(mockTask);

    renderWithRouter(<MontageEditor />);

    await waitFor(() => {
      expect(screen.getByDisplayValue('Открывающая сцена')).toBeInTheDocument();
    });

    // Edit description
    const descriptionInput = screen.getByDisplayValue('Открывающая сцена');
    await user.clear(descriptionInput);
    await user.type(descriptionInput, 'Новое описание');

    expect(screen.getByDisplayValue('Новое описание')).toBeInTheDocument();
    
    // Check that save button becomes enabled
    expect(screen.getByText('Сохранить изменения')).toBeInTheDocument();
  });

  test('handles save functionality', async () => {
    const user = userEvent.setup();
    mockedApiService.getTaskStatus.mockResolvedValue(mockTask);
    mockedApiService.updateMontage.mockResolvedValue({});

    // Mock window.alert
    const alertSpy = jest.spyOn(window, 'alert').mockImplementation(() => {});

    renderWithRouter(<MontageEditor />);

    await waitFor(() => {
      expect(screen.getByDisplayValue('Открывающая сцена')).toBeInTheDocument();
    });

    // Make a change
    const descriptionInput = screen.getByDisplayValue('Открывающая сцена');
    await user.clear(descriptionInput);
    await user.type(descriptionInput, 'Измененное описание');

    // Click save
    const saveButton = screen.getByText('Сохранить изменения');
    await user.click(saveButton);

    await waitFor(() => {
      expect(mockedApiService.updateMontage).toHaveBeenCalledWith('test-task-id', expect.any(Array));
    });

    expect(alertSpy).toHaveBeenCalledWith('Изменения сохранены');
    
    alertSpy.mockRestore();
  });

  test('handles API errors gracefully', async () => {
    mockedApiService.getTaskStatus.mockRejectedValue(new Error('API Error'));

    renderWithRouter(<MontageEditor />);

    await waitFor(() => {
      expect(screen.getByText('Ошибка')).toBeInTheDocument();
    });

    expect(screen.getByText('Не удалось загрузить данные задачи')).toBeInTheDocument();
    expect(screen.getByText('Вернуться к загрузке')).toBeInTheDocument();
  });
});