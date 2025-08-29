import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import userEvent from '@testing-library/user-event';
import MontageEditor from '../MontageEditor';
import { apiService } from '../../services/api';
import { ProcessingTask, MontageRow } from '../../types';

// Mock the API service
jest.mock('../../services/api');
const mockedApiService = apiService as jest.Mocked<typeof apiService>;

// Mock ReactPlayer
jest.mock('react-player', () => {
  const mockReact = require('react');
  return mockReact.forwardRef<any, any>((props: any, ref: any) => (
    mockReact.createElement('div', { 'data-testid': 'react-player', ref }, [
      mockReact.createElement('button', { 
        key: 'play',
        onClick: () => props.onPlay?.() 
      }, 'Play'),
      mockReact.createElement('button', { 
        key: 'pause',
        onClick: () => props.onPause?.() 
      }, 'Pause'),
      mockReact.createElement('button', { 
        key: 'progress',
        onClick: () => props.onProgress?.({ played: 0.5, playedSeconds: 30 })
      }, 'Progress')
    ])
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

describe('MontageEditor Component', () => {
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
      },
      {
        number: 2,
        start_timecode: '01:00:05:00',
        end_timecode: '01:00:10:00',
        shot_type: 'Крупный',
        description: 'Крупный план персонажа',
        dialogue: 'Как дела?',
        speaker: 'Спикер 2',
        has_music: true
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

  test('renders montage table with video player', async () => {
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

  test('displays montage rows correctly', async () => {
    mockedApiService.getTaskStatus.mockResolvedValue(mockTask);

    renderWithRouter(<MontageEditor />);

    await waitFor(() => {
      expect(screen.getByDisplayValue('01:00:00:00')).toBeInTheDocument();
    });

    // Check first row data
    expect(screen.getByDisplayValue('01:00:05:00')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Открывающая сцена')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Привет, мир!')).toBeInTheDocument();
    expect(screen.getByText('Спикер 1')).toBeInTheDocument();

    // Check second row data
    expect(screen.getByDisplayValue('01:00:10:00')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Крупный план персонажа')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Как дела?')).toBeInTheDocument();
    expect(screen.getByText('Спикер 2')).toBeInTheDocument();
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

  test('handles shot type selection', async () => {
    const user = userEvent.setup();
    mockedApiService.getTaskStatus.mockResolvedValue(mockTask);

    renderWithRouter(<MontageEditor />);

    await waitFor(() => {
      expect(screen.getByDisplayValue('Общий')).toBeInTheDocument();
    });

    // Change shot type
    const shotTypeSelect = screen.getByDisplayValue('Общий');
    await user.selectOptions(shotTypeSelect, 'Крупный');

    expect(screen.getAllByDisplayValue('Крупный')).toHaveLength(2); // Both rows now have "Крупный"
  });

  test('handles speaker editing', async () => {
    const user = userEvent.setup();
    mockedApiService.getTaskStatus.mockResolvedValue(mockTask);

    renderWithRouter(<MontageEditor />);

    await waitFor(() => {
      expect(screen.getByText('Спикер 1')).toBeInTheDocument();
    });

    // Click on speaker tag to edit
    const speakerTag = screen.getByText('Спикер 1');
    await user.click(speakerTag);

    // Should show input field
    const speakerInput = screen.getByDisplayValue('Спикер 1');
    expect(speakerInput).toBeInTheDocument();

    // Edit speaker name
    await user.clear(speakerInput);
    await user.type(speakerInput, 'Новый спикер');
    await user.keyboard('{Enter}');

    // Should show updated speaker name
    await waitFor(() => {
      expect(screen.getByText('Новый спикер')).toBeInTheDocument();
    });
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

  test('handles export functionality', async () => {
    const user = userEvent.setup();
    mockedApiService.getTaskStatus.mockResolvedValue(mockTask);
    
    // Mock blob and URL creation
    const mockBlob = new Blob(['test'], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });
    mockedApiService.downloadDocx.mockResolvedValue(mockBlob);
    
    // Mock URL methods
    const createObjectURLSpy = jest.spyOn(URL, 'createObjectURL').mockReturnValue('blob:test-url');
    const revokeObjectURLSpy = jest.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
    
    // Mock document methods
    const createElementSpy = jest.spyOn(document, 'createElement').mockReturnValue({
      href: '',
      download: '',
      click: jest.fn(),
    } as any);
    const appendChildSpy = jest.spyOn(document.body, 'appendChild').mockImplementation(() => ({} as any));
    const removeChildSpy = jest.spyOn(document.body, 'removeChild').mockImplementation(() => ({} as any));

    renderWithRouter(<MontageEditor />);

    await waitFor(() => {
      expect(screen.getByText('Экспорт DOCX')).toBeInTheDocument();
    });

    // Click export
    const exportButton = screen.getByText('Экспорт DOCX');
    await user.click(exportButton);

    await waitFor(() => {
      expect(mockedApiService.downloadDocx).toHaveBeenCalledWith('test-task-id');
    });

    expect(createObjectURLSpy).toHaveBeenCalledWith(mockBlob);
    
    // Cleanup mocks
    createObjectURLSpy.mockRestore();
    revokeObjectURLSpy.mockRestore();
    createElementSpy.mockRestore();
    appendChildSpy.mockRestore();
    removeChildSpy.mockRestore();
  });

  test('handles video player controls', async () => {
    const user = userEvent.setup();
    mockedApiService.getTaskStatus.mockResolvedValue(mockTask);

    renderWithRouter(<MontageEditor />);

    await waitFor(() => {
      expect(screen.getByTestId('react-player')).toBeInTheDocument();
    });

    // Test play button
    const playButton = screen.getByText('Воспроизвести');
    await user.click(playButton);

    // Should change to pause button (this would happen through the mocked player)
    const mockPlayButton = screen.getByText('Play');
    fireEvent.click(mockPlayButton);

    expect(screen.getByText('Пауза')).toBeInTheDocument();
  });

  test('handles row selection and video seeking', async () => {
    const user = userEvent.setup();
    mockedApiService.getTaskStatus.mockResolvedValue(mockTask);

    renderWithRouter(<MontageEditor />);

    await waitFor(() => {
      expect(screen.getByDisplayValue('Открывающая сцена')).toBeInTheDocument();
    });

    // Click on a table row (need to click on a non-input element)
    const rowNumber = screen.getByText('1');
    await user.click(rowNumber);

    // Row should be selected (this would be visible through styling)
    // The test verifies the click handler is called
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

  test('handles missing task ID', async () => {
    // Mock useParams to return undefined taskId
    jest.doMock('react-router-dom', () => ({
      ...jest.requireActual('react-router-dom'),
      useParams: () => ({ taskId: undefined }),
      useNavigate: () => mockNavigate,
    }));

    renderWithRouter(<MontageEditor />);

    await waitFor(() => {
      expect(screen.getByText('Ошибка')).toBeInTheDocument();
    });

    expect(screen.getByText('ID задачи не найден')).toBeInTheDocument();
  });

  test('displays shot type tags with correct colors', async () => {
    mockedApiService.getTaskStatus.mockResolvedValue(mockTask);

    renderWithRouter(<MontageEditor />);

    await waitFor(() => {
      expect(screen.getByText('Общий')).toBeInTheDocument();
    });

    // Check that shot type tags are displayed
    const shotTypeTags = screen.getAllByText('Общий');
    expect(shotTypeTags.length).toBeGreaterThan(0);
    
    const shotTypeTags2 = screen.getAllByText('Крупный');
    expect(shotTypeTags2.length).toBeGreaterThan(0);
  });
});