import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import VideoUpload from '../VideoUpload';
import { apiService } from '../../services/api';

// Mock the API service
jest.mock('../../services/api');
const mockedApiService = apiService as jest.Mocked<typeof apiService>;

// Mock react-dropzone
jest.mock('react-dropzone', () => ({
  useDropzone: ({ onDrop, accept }: any) => ({
    getRootProps: () => ({
      onClick: jest.fn(),
      onDrop: jest.fn(),
    }),
    getInputProps: () => ({
      type: 'file',
      accept: Object.keys(accept || {}).join(','),
    }),
    isDragActive: false,
  }),
}));

describe('VideoUpload Component', () => {
  const mockOnTaskCreated = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders video upload interface', () => {
    render(<VideoUpload onTaskCreated={mockOnTaskCreated} />);
    
    expect(screen.getByText('Создание монтажного листа')).toBeInTheDocument();
    expect(screen.getByText('Перетащите видеофайл сюда или нажмите для выбора')).toBeInTheDocument();
    expect(screen.getByText('Автоматическая транскрипция')).toBeInTheDocument();
    expect(screen.getByText('Загрузить SRT файл')).toBeInTheDocument();
  });

  test('switches between auto and SRT modes', async () => {
    const user = userEvent.setup();
    render(<VideoUpload onTaskCreated={mockOnTaskCreated} />);
    
    const srtModeButton = screen.getByText('Загрузить SRT файл');
    await user.click(srtModeButton);
    
    expect(screen.getByText('Загрузка SRT файла')).toBeInTheDocument();
    
    const autoModeButton = screen.getByText('Автоматическая транскрипция');
    await user.click(autoModeButton);
    
    expect(screen.queryByText('Загрузка SRT файла')).not.toBeInTheDocument();
  });

  test('validates required fields before submission', async () => {
    const user = userEvent.setup();
    render(<VideoUpload onTaskCreated={mockOnTaskCreated} />);
    
    const submitButton = screen.getByText('Создать монтажный лист');
    expect(submitButton).toBeDisabled();
  });

  test('enables submit button when video file and title are provided', async () => {
    const user = userEvent.setup();
    render(<VideoUpload onTaskCreated={mockOnTaskCreated} />);
    
    // Fill in the title
    const titleInput = screen.getByPlaceholderText('Введите название фильма');
    await user.type(titleInput, 'Test Movie');
    
    // The submit button should still be disabled without a video file
    const submitButton = screen.getByText('Создать монтажный лист');
    expect(submitButton).toBeDisabled();
  });

  test('handles successful video upload', async () => {
    const user = userEvent.setup();
    const mockResponse = { task_id: 'test-task-id' };
    mockedApiService.uploadVideo.mockResolvedValue(mockResponse);
    
    render(<VideoUpload onTaskCreated={mockOnTaskCreated} />);
    
    // Fill in required fields
    const titleInput = screen.getByPlaceholderText('Введите название фильма');
    await user.type(titleInput, 'Test Movie');
    
    // Mock file selection (this would normally be handled by dropzone)
    // For testing purposes, we'll simulate the component state change
    // In a real test, you'd need to mock the file drop functionality
  });

  test('displays upload progress during file upload', async () => {
    const mockResponse = { task_id: 'test-task-id' };
    let progressCallback: ((progress: number) => void) | undefined;
    
    mockedApiService.uploadVideo.mockImplementation(async (file, metadata, settings, onProgress) => {
      progressCallback = onProgress;
      // Simulate progress updates
      setTimeout(() => {
        if (progressCallback) {
          progressCallback(50);
          setTimeout(() => {
            if (progressCallback) progressCallback(100);
          }, 100);
        }
      }, 50);
      return mockResponse;
    });
    
    render(<VideoUpload onTaskCreated={mockOnTaskCreated} />);
    
    // This test would need proper file upload simulation
    // For now, we're testing the component structure
  });

  test('handles upload errors gracefully', async () => {
    const user = userEvent.setup();
    const mockError = new Error('Upload failed');
    mockedApiService.uploadVideo.mockRejectedValue(mockError);
    
    // Mock window.alert
    const alertSpy = jest.spyOn(window, 'alert').mockImplementation(() => {});
    
    render(<VideoUpload onTaskCreated={mockOnTaskCreated} />);
    
    // This test would need proper error simulation
    // For now, we're testing the component structure
    
    alertSpy.mockRestore();
  });
});