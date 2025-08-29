import React from 'react';
import styled from 'styled-components';
import { FilmMetadata } from '../types';

const FormContainer = styled.div`
  background-color: white;
  padding: 25px;
  border-radius: 8px;
  margin-bottom: 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
`;

const FormTitle = styled.h3`
  margin-bottom: 20px;
  color: #333;
  border-bottom: 2px solid #007bff;
  padding-bottom: 10px;
`;

const FormRow = styled.div`
  display: flex;
  gap: 20px;
  margin-bottom: 15px;

  @media (max-width: 768px) {
    flex-direction: column;
    gap: 0;
  }
`;

const FormGroup = styled.div`
  flex: 1;
  margin-bottom: 15px;
`;

const Label = styled.label`
  display: block;
  margin-bottom: 5px;
  font-weight: 500;
  color: #333;
`;

const Input = styled.input`
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;

  &:focus {
    outline: none;
    border-color: #007bff;
    box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.25);
  }
`;

const Select = styled.select`
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
  background-color: white;

  &:focus {
    outline: none;
    border-color: #007bff;
    box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.25);
  }
`;

const TextArea = styled.textarea`
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
  min-height: 80px;
  resize: vertical;

  &:focus {
    outline: none;
    border-color: #007bff;
    box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.25);
  }
`;

const TagInput = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  min-height: 40px;
  background-color: white;

  &:focus-within {
    border-color: #007bff;
    box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.25);
  }
`;

const Tag = styled.span`
  background-color: #007bff;
  color: white;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 5px;
`;

const TagRemove = styled.button`
  background: none;
  border: none;
  color: white;
  cursor: pointer;
  font-size: 14px;
  padding: 0;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;

  &:hover {
    background-color: rgba(255, 255, 255, 0.2);
  }
`;

const TagInputField = styled.input`
  border: none;
  outline: none;
  flex: 1;
  min-width: 100px;
  font-size: 14px;
`;

interface FilmMetadataFormProps {
  metadata: FilmMetadata;
  onChange: (metadata: FilmMetadata) => void;
}

const FilmMetadataForm: React.FC<FilmMetadataFormProps> = ({ metadata, onChange }) => {
  const handleInputChange = (field: keyof FilmMetadata, value: any) => {
    onChange({
      ...metadata,
      [field]: value
    });
  };

  const handleArrayInputChange = (field: 'screenwriters' | 'copyright_holders', value: string) => {
    if (value.trim() && !metadata[field].includes(value.trim())) {
      handleInputChange(field, [...metadata[field], value.trim()]);
    }
  };

  const removeArrayItem = (field: 'screenwriters' | 'copyright_holders', index: number) => {
    const newArray = metadata[field].filter((_, i) => i !== index);
    handleInputChange(field, newArray);
  };

  const handleKeyPress = (e: React.KeyboardEvent, field: 'screenwriters' | 'copyright_holders') => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      const target = e.target as HTMLInputElement;
      handleArrayInputChange(field, target.value);
      target.value = '';
    }
  };

  return (
    <FormContainer>
      <FormTitle>Метаданные фильма</FormTitle>
      
      <FormRow>
        <FormGroup>
          <Label>Название фильма *</Label>
          <Input
            type="text"
            value={metadata.title}
            onChange={(e) => handleInputChange('title', e.target.value)}
            placeholder="Введите название фильма"
            required
          />
        </FormGroup>
        <FormGroup>
          <Label>Производитель</Label>
          <Input
            type="text"
            value={metadata.production_company}
            onChange={(e) => handleInputChange('production_company', e.target.value)}
            placeholder="Название студии или компании"
          />
        </FormGroup>
      </FormRow>

      <FormRow>
        <FormGroup>
          <Label>Год производства</Label>
          <Input
            type="number"
            value={metadata.year}
            onChange={(e) => handleInputChange('year', parseInt(e.target.value) || new Date().getFullYear())}
            min="1900"
            max={new Date().getFullYear() + 5}
          />
        </FormGroup>
        <FormGroup>
          <Label>Страна</Label>
          <Input
            type="text"
            value={metadata.country}
            onChange={(e) => handleInputChange('country', e.target.value)}
            placeholder="Страна производства"
          />
        </FormGroup>
      </FormRow>

      <FormGroup>
        <Label>Авторы сценария</Label>
        <TagInput>
          {metadata.screenwriters.map((writer, index) => (
            <Tag key={index}>
              {writer}
              <TagRemove onClick={() => removeArrayItem('screenwriters', index)}>
                ×
              </TagRemove>
            </Tag>
          ))}
          <TagInputField
            placeholder="Введите имя и нажмите Enter"
            onKeyPress={(e) => handleKeyPress(e, 'screenwriters')}
          />
        </TagInput>
      </FormGroup>

      <FormGroup>
        <Label>Правообладатели</Label>
        <TagInput>
          {metadata.copyright_holders.map((holder, index) => (
            <Tag key={index}>
              {holder}
              <TagRemove onClick={() => removeArrayItem('copyright_holders', index)}>
                ×
              </TagRemove>
            </Tag>
          ))}
          <TagInputField
            placeholder="Введите правообладателя и нажмите Enter"
            onKeyPress={(e) => handleKeyPress(e, 'copyright_holders')}
          />
        </TagInput>
      </FormGroup>

      <FormRow>
        <FormGroup>
          <Label>Продолжительность</Label>
          <Input
            type="text"
            value={metadata.duration}
            onChange={(e) => handleInputChange('duration', e.target.value)}
            placeholder="например: 01:30:00"
          />
        </FormGroup>
        <FormGroup>
          <Label>Количество серий</Label>
          <Input
            type="number"
            value={metadata.episodes_count}
            onChange={(e) => handleInputChange('episodes_count', parseInt(e.target.value) || 1)}
            min="1"
          />
        </FormGroup>
      </FormRow>

      <FormRow>
        <FormGroup>
          <Label>Формат</Label>
          <Select
            value={metadata.format}
            onChange={(e) => handleInputChange('format', e.target.value)}
          >
            <option value="HD">HD</option>
            <option value="4K">4K</option>
            <option value="SD">SD</option>
            <option value="Full HD">Full HD</option>
          </Select>
        </FormGroup>
        <FormGroup>
          <Label>Цвет</Label>
          <Select
            value={metadata.color_type}
            onChange={(e) => handleInputChange('color_type', e.target.value as 'Цветной' | 'Черно-белый')}
          >
            <option value="Цветной">Цветной</option>
            <option value="Черно-белый">Черно-белый</option>
          </Select>
        </FormGroup>
      </FormRow>

      <FormRow>
        <FormGroup>
          <Label>Носитель</Label>
          <Input
            type="text"
            value={metadata.media_carrier}
            onChange={(e) => handleInputChange('media_carrier', e.target.value)}
            placeholder="например: Цифровой, DVD, Blu-ray"
          />
        </FormGroup>
      </FormRow>

      <FormRow>
        <FormGroup>
          <Label>Язык оригинала</Label>
          <Input
            type="text"
            value={metadata.original_language}
            onChange={(e) => handleInputChange('original_language', e.target.value)}
          />
        </FormGroup>
        <FormGroup>
          <Label>Язык субтитров</Label>
          <Input
            type="text"
            value={metadata.subtitle_language}
            onChange={(e) => handleInputChange('subtitle_language', e.target.value)}
          />
        </FormGroup>
      </FormRow>

      <FormGroup>
        <Label>Язык звука</Label>
        <Input
          type="text"
          value={metadata.audio_language}
          onChange={(e) => handleInputChange('audio_language', e.target.value)}
        />
      </FormGroup>
    </FormContainer>
  );
};

export default FilmMetadataForm;