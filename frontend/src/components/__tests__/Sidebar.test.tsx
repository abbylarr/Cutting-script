import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import userEvent from '@testing-library/user-event';
import Sidebar from '../Sidebar';
import { apiService } from '../../services/api';
import { User, Project } from '../../types';

// Mock the API service
jest.mock('../../services/api');
const mockedApiService = apiService as jest.Mocked<typeof apiService>;

// Mock react-router-dom
const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate,
}));

const renderWithRouter = (component: React.ReactElement) => {
  return render(
    <BrowserRouter>
      {component}
    </BrowserRouter>
  );
};

describe('Sidebar Component', () => {
  const mockUser: User = {
    id: 'user-1',
    email: 'test@example.com',
    balance: 1500,
    created_at: '2023-01-01T00:00:00Z'
  };

  const mockProjects: Project[] = [
    {
      id: 'project-1',
      user_id: 'user-1',
      task_id: 'task-1',
      title: 'Тестовый фильм 1',
      metadata: {
        title: 'Тестовый фильм 1',
        production_company: 'Тестовая студия',
        year: 2023,
        country: 'Россия',
        screenwriters: ['Автор 1'],
        copyright_holders: ['Правообладатель 1'],
        duration: '01:30:00',
        episodes_count: 1,
        format: 'HD',
        color_type: 'Цветной',
        media_carrier: 'Цифровой',
        original_language: 'Русский',
        subtitle_language: 'Русский',
        audio_language: 'Русский'
      },
      montage_rows: [
        {
          number: 1,
          start_timecode: '01:00:00:00',
          end_timecode: '01:00:05:00',
          shot_type: 'Общий',
          description: 'Описание',
          dialogue: 'Диалог',
          has_music: false
        }
      ],
      created_at: '2023-01-01T00:00:00Z',
      updated_at: '2023-01-01T00:05:00Z'
    },
    {
      id: 'project-2',
      user_id: 'user-1',
      task_id: 'task-2',
      title: 'Фильм в обработке',
      metadata: {
        title: 'Фильм в обработке',
        production_company: 'Другая студия',
        year: 2023,
        country: 'Россия',
        screenwriters: ['Автор 2'],
        copyright_holders: ['Правообладатель 2'],
        duration: '02:00:00',
        episodes_count: 1,
        format: 'HD',
        color_type: 'Цветной',
        media_carrier: 'Цифровой',
        original_language: 'Русский',
        subtitle_language: 'Русский',
        audio_language: 'Русский'
      },
      created_at: '2023-01-02T00:00:00Z',
      updated_at: '2023-01-02T00:05:00Z'
    }
  ];

  const mockOnLogout = jest.fn();
  const mockOnTaskSelect = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders user information correctly', async () => {
    mockedApiService.getProjects.mockResolvedValue(mockProjects);

    renderWithRouter(
      <Sidebar
        user={mockUser}
        onLogout={mockOnLogout}
        currentTaskId={null}
        onTaskSelect={mockOnTaskSelect}
      />
    );

    expect(screen.getByText('test@example.com')).toBeInTheDocument();
    expect(screen.getByText('1500 ₽')).toBeInTheDocument();
    expect(screen.getByText('Пополнить')).toBeInTheDocument();
    expect(screen.getByText('Выйти')).toBeInTheDocument();
  });

  test('displays projects list correctly', async () => {
    mockedApiService.getProjects.mockResolvedValue(mockProjects);

    renderWithRouter(
      <Sidebar
        user={mockUser}
        onLogout={mockOnLogout}
        currentTaskId={null}
        onTaskSelect={mockOnTaskSelect}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Тестовый фильм 1')).toBeInTheDocument();
    });

    expect(screen.getByText('Фильм в обработке')).toBeInTheDocument();
    expect(screen.getByText('Тестовая студия • 01.01.2023')).toBeInTheDocument();
    expect(screen.getByText('Другая студия • 02.01.2023')).toBeInTheDocument();
  });

  test('shows project status correctly', async () => {
    mockedApiService.getProjects.mockResolvedValue(mockProjects);

    renderWithRouter(
      <Sidebar
        user={mockUser}
        onLogout={mockOnLogout}
        currentTaskId={null}
        onTaskSelect={mockOnTaskSelect}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Готов')).toBeInTheDocument();
    });

    expect(screen.getByText('Обработка')).toBeInTheDocument();
  });

  test('handles search functionality', async () => {
    const user = userEvent.setup();
    mockedApiService.getProjects.mockResolvedValue(mockProjects);

    renderWithRouter(
      <Sidebar
        user={mockUser}
        onLogout={mockOnLogout}
        currentTaskId={null}
        onTaskSelect={mockOnTaskSelect}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Тестовый фильм 1')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Поиск проектов...');
    await user.type(searchInput, 'Тестовый');

    // Should show only the first project
    expect(screen.getByText('Тестовый фильм 1')).toBeInTheDocument();
    expect(screen.queryByText('Фильм в обработке')).not.toBeInTheDocument();
  });

  test('handles status filtering', async () => {
    const user = userEvent.setup();
    mockedApiService.getProjects.mockResolvedValue(mockProjects);

    renderWithRouter(
      <Sidebar
        user={mockUser}
        onLogout={mockOnLogout}
        currentTaskId={null}
        onTaskSelect={mockOnTaskSelect}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Тестовый фильм 1')).toBeInTheDocument();
    });

    const filterSelect = screen.getByDisplayValue('Все проекты');
    await user.selectOptions(filterSelect, 'completed');

    // Should show only completed projects
    expect(screen.getByText('Тестовый фильм 1')).toBeInTheDocument();
    expect(screen.queryByText('Фильм в обработке')).not.toBeInTheDocument();
  });

  test('handles project click navigation', async () => {
    const user = userEvent.setup();
    mockedApiService.getProjects.mockResolvedValue(mockProjects);

    renderWithRouter(
      <Sidebar
        user={mockUser}
        onLogout={mockOnLogout}
        currentTaskId={null}
        onTaskSelect={mockOnTaskSelect}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Тестовый фильм 1')).toBeInTheDocument();
    });

    const projectItem = screen.getByText('Тестовый фильм 1');
    await user.click(projectItem);

    expect(mockOnTaskSelect).toHaveBeenCalledWith('task-1');
    expect(mockNavigate).toHaveBeenCalledWith('/editor/task-1');
  });

  test('handles project deletion', async () => {
    const user = userEvent.setup();
    mockedApiService.getProjects.mockResolvedValue(mockProjects);
    mockedApiService.deleteProject.mockResolvedValue({});

    // Mock window.confirm
    const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(true);

    renderWithRouter(
      <Sidebar
        user={mockUser}
        onLogout={mockOnLogout}
        currentTaskId={null}
        onTaskSelect={mockOnTaskSelect}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Тестовый фильм 1')).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByText('Удалить');
    await user.click(deleteButtons[0]);

    expect(confirmSpy).toHaveBeenCalledWith('Вы уверены, что хотите удалить этот проект?');
    
    await waitFor(() => {
      expect(mockedApiService.deleteProject).toHaveBeenCalledWith('project-1');
    });

    confirmSpy.mockRestore();
  });

  test('handles logout functionality', async () => {
    const user = userEvent.setup();
    mockedApiService.getProjects.mockResolvedValue(mockProjects);

    renderWithRouter(
      <Sidebar
        user={mockUser}
        onLogout={mockOnLogout}
        currentTaskId={null}
        onTaskSelect={mockOnTaskSelect}
      />
    );

    const logoutButton = screen.getByText('Выйти');
    await user.click(logoutButton);

    expect(mockOnLogout).toHaveBeenCalled();
  });

  test('handles new project creation', async () => {
    const user = userEvent.setup();
    mockedApiService.getProjects.mockResolvedValue(mockProjects);

    renderWithRouter(
      <Sidebar
        user={mockUser}
        onLogout={mockOnLogout}
        currentTaskId={null}
        onTaskSelect={mockOnTaskSelect}
      />
    );

    const newProjectButton = screen.getByText('+ Новый проект');
    await user.click(newProjectButton);

    expect(mockNavigate).toHaveBeenCalledWith('/upload');
  });

  test('shows empty state when no projects', async () => {
    mockedApiService.getProjects.mockResolvedValue([]);

    renderWithRouter(
      <Sidebar
        user={mockUser}
        onLogout={mockOnLogout}
        currentTaskId={null}
        onTaskSelect={mockOnTaskSelect}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('У вас пока нет проектов')).toBeInTheDocument();
    });

    expect(screen.getByText('📁')).toBeInTheDocument();
  });

  test('shows loading state initially', () => {
    mockedApiService.getProjects.mockImplementation(() => 
      new Promise(() => {}) // Never resolves to keep loading state
    );

    renderWithRouter(
      <Sidebar
        user={mockUser}
        onLogout={mockOnLogout}
        currentTaskId={null}
        onTaskSelect={mockOnTaskSelect}
      />
    );

    expect(screen.getByText('Загрузка проектов...')).toBeInTheDocument();
  });

  test('handles API errors gracefully', async () => {
    mockedApiService.getProjects.mockRejectedValue(new Error('API Error'));

    renderWithRouter(
      <Sidebar
        user={mockUser}
        onLogout={mockOnLogout}
        currentTaskId={null}
        onTaskSelect={mockOnTaskSelect}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('У вас пока нет проектов')).toBeInTheDocument();
    });
  });

  test('highlights current active project', async () => {
    mockedApiService.getProjects.mockResolvedValue(mockProjects);

    renderWithRouter(
      <Sidebar
        user={mockUser}
        onLogout={mockOnLogout}
        currentTaskId="task-1"
        onTaskSelect={mockOnTaskSelect}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Тестовый фильм 1')).toBeInTheDocument();
    });

    // The active project should have different styling (this would be tested through CSS classes)
    // For now, we just verify the component renders without errors
  });

  test('handles top-up button click', async () => {
    const user = userEvent.setup();
    mockedApiService.getProjects.mockResolvedValue(mockProjects);

    // Mock window.alert
    const alertSpy = jest.spyOn(window, 'alert').mockImplementation(() => {});

    renderWithRouter(
      <Sidebar
        user={mockUser}
        onLogout={mockOnLogout}
        currentTaskId={null}
        onTaskSelect={mockOnTaskSelect}
      />
    );

    const topUpButton = screen.getByText('Пополнить');
    await user.click(topUpButton);

    expect(alertSpy).toHaveBeenCalledWith('Функция пополнения баланса будет добавлена в следующей версии');

    alertSpy.mockRestore();
  });

  test('handles duplicate project functionality', async () => {
    const user = userEvent.setup();
    mockedApiService.getProjects.mockResolvedValue(mockProjects);

    // Mock window.alert
    const alertSpy = jest.spyOn(window, 'alert').mockImplementation(() => {});

    renderWithRouter(
      <Sidebar
        user={mockUser}
        onLogout={mockOnLogout}
        currentTaskId={null}
        onTaskSelect={mockOnTaskSelect}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Тестовый фильм 1')).toBeInTheDocument();
    });

    const duplicateButtons = screen.getAllByText('Копировать');
    await user.click(duplicateButtons[0]);

    expect(alertSpy).toHaveBeenCalledWith('Функция дублирования будет добавлена в следующей версии');

    alertSpy.mockRestore();
  });
}); 
= jest.spyOn(window, 'confirm').mockReturnValue(true);

    renderWithRouter(<Sidebar {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText('Мой первый проект')).toBeInTheDocument();
    });

    // Click delete button
    const deleteButton = screen.getAllByText('Удалить')[0];
    await user.click(deleteButton);

    expect(confirmSpy).toHaveBeenCalledWith('Вы уверены, что хотите удалить этот проект?');
    expect(mockedApiService.deleteProject).toHaveBeenCalledWith('project-1');

    // Should remove project from list
    await waitFor(() => {
      expect(screen.queryByText('Мой первый проект')).not.toBeInTheDocument();
    });

    confirmSpy.mockRestore();
  });

  test('handles logout action', async () => {
    const user = userEvent.setup();
    mockedApiService.getProjects.mockResolvedValue(mockProjects);

    renderWithRouter(<Sidebar {...mockProps} />);

    const logoutButton = screen.getByText('Выйти');
    await user.click(logoutButton);

    expect(mockProps.onLogout).toHaveBeenCalled();
  });

  test('handles top up navigation', async () => {
    const user = userEvent.setup();
    mockedApiService.getProjects.mockResolvedValue(mockProjects);

    renderWithRouter(<Sidebar {...mockProps} />);

    const topUpButton = screen.getByText('Пополнить');
    await user.click(topUpButton);

    expect(mockNavigate).toHaveBeenCalledWith('/payments');
  });

  test('handles new project navigation', async () => {
    const user = userEvent.setup();
    mockedApiService.getProjects.mockResolvedValue(mockProjects);

    renderWithRouter(<Sidebar {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText('+ Новый проект')).toBeInTheDocument();
    });

    const newProjectButton = screen.getByText('+ Новый проект');
    await user.click(newProjectButton);

    expect(mockNavigate).toHaveBeenCalledWith('/upload');
  });

  test('shows loading state', () => {
    mockedApiService.getProjects.mockImplementation(() => new Promise(() => {}));

    renderWithRouter(<Sidebar {...mockProps} />);

    expect(screen.getByText('Загрузка проектов...')).toBeInTheDocument();
  });

  test('shows empty state when no projects', async () => {
    mockedApiService.getProjects.mockResolvedValue([]);

    renderWithRouter(<Sidebar {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText('У вас пока нет проектов')).toBeInTheDocument();
    });

    expect(screen.getByText('📁')).toBeInTheDocument();
  });

  test('shows filtered empty state', async () => {
    const user = userEvent.setup();
    mockedApiService.getProjects.mockResolvedValue(mockProjects);

    renderWithRouter(<Sidebar {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText('Мой первый проект')).toBeInTheDocument();
    });

    // Search for non-existent project
    const searchInput = screen.getByPlaceholderText('Поиск проектов...');
    await user.type(searchInput, 'несуществующий проект');

    await waitFor(() => {
      expect(screen.getByText('Проекты не найдены')).toBeInTheDocument();
    });
  });

  test('highlights active project', async () => {
    mockedApiService.getProjects.mockResolvedValue(mockProjects);

    const propsWithActiveTask = {
      ...mockProps,
      currentTaskId: 'task-1'
    };

    renderWithRouter(<Sidebar {...propsWithActiveTask} />);

    await waitFor(() => {
      const projectItem = screen.getByText('Мой первый проект').closest('div');
      expect(projectItem).toHaveStyle('background-color: #3498db');
    });
  });

  test('handles API error gracefully', async () => {
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
    mockedApiService.getProjects.mockRejectedValue(new Error('API Error'));

    renderWithRouter(<Sidebar {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText('У вас пока нет проектов')).toBeInTheDocument();
    });

    expect(consoleSpy).toHaveBeenCalledWith('Failed to fetch projects:', expect.any(Error));
    consoleSpy.mockRestore();
  });

  test('formats dates correctly', async () => {
    mockedApiService.getProjects.mockResolvedValue(mockProjects);

    renderWithRouter(<Sidebar {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText('01.01.23')).toBeInTheDocument();
      expect(screen.getByText('02.01.23')).toBeInTheDocument();
    });
  });

  test('displays correct status badges', async () => {
    mockedApiService.getProjects.mockResolvedValue([
      ...mockProjects,
      {
        ...mockProjects[0],
        id: 'project-3',
        title: 'Проект с ошибкой',
        metadata: { ...mockProjects[0].metadata, status: 'failed' }
      }
    ]);

    renderWithRouter(<Sidebar {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText('Готов')).toBeInTheDocument();
      expect(screen.getByText('Обработка')).toBeInTheDocument();
      expect(screen.getByText('Ошибка')).toBeInTheDocument();
    });
  });

  test('handles escape key during project editing', async () => {
    const user = userEvent.setup();
    mockedApiService.getProjects.mockResolvedValue(mockProjects);

    renderWithRouter(<Sidebar {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText('Мой первый проект')).toBeInTheDocument();
    });

    // Start editing
    const renameButton = screen.getAllByText('Переименовать')[0];
    await user.click(renameButton);

    const input = screen.getByDisplayValue('Мой первый проект');
    await user.clear(input);
    await user.type(input, 'Новое название');
    
    // Press escape to cancel
    await user.keyboard('{Escape}');

    // Should revert to original name
    expect(screen.getByText('Мой первый проект')).toBeInTheDocument();
    expect(screen.queryByText('Новое название')).not.toBeInTheDocument();
  });
});