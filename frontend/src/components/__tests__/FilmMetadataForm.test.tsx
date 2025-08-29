import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import FilmMetadataForm from '../FilmMetadataForm';
import { FilmMetadata } from '../../types';

describe('FilmMetadataForm Component', () => {
  const mockMetadata: FilmMetadata = {
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
  };

  const mockOnChange = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders all form fields', () => {
    render(<FilmMetadataForm metadata={mockMetadata} onChange={mockOnChange} />);
    
    expect(screen.getByText('Метаданные фильма')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Введите название фильма')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Название студии или компании')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Россия')).toBeInTheDocument();
  });

  test('handles text input changes', async () => {
    const user = userEvent.setup();
    render(<FilmMetadataForm metadata={mockMetadata} onChange={mockOnChange} />);
    
    const titleInput = screen.getByPlaceholderText('Введите название фильма');
    await user.type(titleInput, 'Test Movie');
    
    // Check that onChange was called with the final value
    expect(mockOnChange).toHaveBeenLastCalledWith({
      ...mockMetadata,
      title: 'Test Movie'
    });
  });

  test('handles select changes', async () => {
    const user = userEvent.setup();
    render(<FilmMetadataForm metadata={mockMetadata} onChange={mockOnChange} />);
    
    const colorSelect = screen.getByDisplayValue('Цветной');
    await user.selectOptions(colorSelect, 'Черно-белый');
    
    expect(mockOnChange).toHaveBeenCalledWith({
      ...mockMetadata,
      color_type: 'Черно-белый'
    });
  });

  test('handles array input for screenwriters', async () => {
    const user = userEvent.setup();
    render(<FilmMetadataForm metadata={mockMetadata} onChange={mockOnChange} />);
    
    const screenwriterInput = screen.getByPlaceholderText('Введите имя и нажмите Enter');
    await user.type(screenwriterInput, 'John Doe');
    await user.keyboard('{Enter}');
    
    expect(mockOnChange).toHaveBeenCalledWith({
      ...mockMetadata,
      screenwriters: ['John Doe']
    });
  });

  test('removes items from arrays', async () => {
    const user = userEvent.setup();
    const metadataWithScreenwriters = {
      ...mockMetadata,
      screenwriters: ['John Doe', 'Jane Smith']
    };
    
    render(<FilmMetadataForm metadata={metadataWithScreenwriters} onChange={mockOnChange} />);
    
    const removeButtons = screen.getAllByText('×');
    await user.click(removeButtons[0]);
    
    expect(mockOnChange).toHaveBeenCalledWith({
      ...metadataWithScreenwriters,
      screenwriters: ['Jane Smith']
    });
  });

  test('handles number input validation', async () => {
    const user = userEvent.setup();
    render(<FilmMetadataForm metadata={mockMetadata} onChange={mockOnChange} />);
    
    const yearInput = screen.getByDisplayValue(new Date().getFullYear().toString());
    await user.clear(yearInput);
    await user.type(yearInput, '2023');
    
    // Check that onChange was called with the final value
    expect(mockOnChange).toHaveBeenLastCalledWith({
      ...mockMetadata,
      year: 2023
    });
  });

  test('prevents duplicate entries in arrays', async () => {
    const user = userEvent.setup();
    const metadataWithScreenwriters = {
      ...mockMetadata,
      screenwriters: ['John Doe']
    };
    
    render(<FilmMetadataForm metadata={metadataWithScreenwriters} onChange={mockOnChange} />);
    
    const screenwriterInput = screen.getByPlaceholderText('Введите имя и нажмите Enter');
    await user.type(screenwriterInput, 'John Doe');
    await user.keyboard('{Enter}');
    
    // Should not add duplicate
    expect(mockOnChange).not.toHaveBeenCalledWith({
      ...metadataWithScreenwriters,
      screenwriters: ['John Doe', 'John Doe']
    });
  });
});