import React from 'react';
import styled from 'styled-components';
import { ProjectSettings } from '../types';

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

const ToggleContainer = styled.div`
  display: flex;
  align-items: center;
  gap: 15px;
  margin-bottom: 15px;
`;

const ToggleSwitch = styled.div<{ active: boolean }>`
  position: relative;
  width: 60px;
  height: 30px;
  background-color: ${props => props.active ? '#007bff' : '#ccc'};
  border-radius: 15px;
  cursor: pointer;
  transition: background-color 0.3s;

  &::after {
    content: '';
    position: absolute;
    top: 3px;
    left: ${props => props.active ? '33px' : '3px'};
    width: 24px;
    height: 24px;
    background-color: white;
    border-radius: 50%;
    transition: left 0.3s;
  }
`;

const ToggleLabel = styled.span<{ active: boolean }>`
  font-weight: ${props => props.active ? '600' : '400'};
  color: ${props => props.active ? '#007bff' : '#666'};
`;

const InfoText = styled.p`
  font-size: 12px;
  color: #666;
  margin-top: 5px;
  font-style: italic;
`;

interface ProjectSettingsFormProps {
  settings: ProjectSettings;
  onChange: (settings: ProjectSettings) => void;
}

const ProjectSettingsForm: React.FC<ProjectSettingsFormProps> = ({ settings, onChange }) => {
  const handleInputChange = (field: keyof ProjectSettings, value: any) => {
    onChange({
      ...settings,
      [field]: value
    });
  };

  const toggleTimecodeStart = () => {
    const newStart = settings.timecode_start === '01:00:00:00' ? '00:00:00:00' : '01:00:00:00';
    handleInputChange('timecode_start', newStart);
  };

  const toggleStandard = () => {
    const newStandard = settings.standard === 'ГФФ' ? 'Красногорский' : 'ГФФ';
    handleInputChange('standard', newStandard);
  };

  return (
    <FormContainer>
      <FormTitle>Настройки проекта</FormTitle>
      
      <FormGroup>
        <Label>Стартовая точка таймкода</Label>
        <ToggleContainer>
          <ToggleLabel active={settings.timecode_start === '00:00:00:00'}>
            00:00:00:00
          </ToggleLabel>
          <ToggleSwitch 
            active={settings.timecode_start === '01:00:00:00'}
            onClick={toggleTimecodeStart}
          />
          <ToggleLabel active={settings.timecode_start === '01:00:00:00'}>
            01:00:00:00
          </ToggleLabel>
        </ToggleContainer>
        <InfoText>
          Выберите начальную точку отсчета таймкода для монтажного листа
        </InfoText>
      </FormGroup>

      <FormGroup>
        <Label>Стандарт</Label>
        <ToggleContainer>
          <ToggleLabel active={settings.standard === 'ГФФ'}>
            ГФФ
          </ToggleLabel>
          <ToggleSwitch 
            active={settings.standard === 'Красногорский'}
            onClick={toggleStandard}
          />
          <ToggleLabel active={settings.standard === 'Красногорский'}>
            Красногорский
          </ToggleLabel>
        </ToggleContainer>
        <InfoText>
          Выберите стандарт форматирования монтажного листа
        </InfoText>
      </FormGroup>

      <FormRow>
        <FormGroup>
          <Label>Частота кадров (FPS)</Label>
          <Select
            value={settings.fps}
            onChange={(e) => handleInputChange('fps', parseFloat(e.target.value))}
          >
            <option value={23.976}>23.976 fps (Cinema)</option>
            <option value={24}>24 fps (Cinema)</option>
            <option value={25}>25 fps (PAL)</option>
            <option value={29.97}>29.97 fps (NTSC)</option>
            <option value={30}>30 fps</option>
            <option value={50}>50 fps (PAL Progressive)</option>
            <option value={59.94}>59.94 fps (NTSC Progressive)</option>
            <option value={60}>60 fps</option>
          </Select>
          <InfoText>
            Частота кадров влияет на точность расчета таймкодов
          </InfoText>
        </FormGroup>
      </FormRow>
    </FormContainer>
  );
};

export default ProjectSettingsForm;