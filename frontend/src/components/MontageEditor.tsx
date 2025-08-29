import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import styled from 'styled-components';
import ReactPlayer from 'react-player';
import { MontageRow, ShotType, ProcessingTask } from '../types';
import { apiService } from '../services/api';

const EditorContainer = styled.div`
  display: flex;
  height: 100vh;
  background-color: #f5f5f5;
`;

const VideoSection = styled.div`
  width: 40%;
  padding: 20px;
  background-color: white;
  border-right: 1px solid #ddd;
`;

const TableSection = styled.div`
  width: 60%;
  padding: 20px;
  overflow-y: auto;
`;

const VideoContainer = styled.div`
  margin-bottom: 20px;
`;

const VideoPlayer = styled.div`
  width: 100%;
  aspect-ratio: 16/9;
  background-color: #000;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 15px;
`;

const VideoControls = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  background-color: #f8f9fa;
  border-radius: 6px;
`;

const TimeDisplay = styled.div`
  font-family: monospace;
  font-size: 14px;
  color: #495057;
  min-width: 80px;
`;

const PlayButton = styled.button`
  padding: 8px 16px;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  
  &:hover {
    background-color: #0056b3;
  }
`;

const TableContainer = styled.div`
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  overflow: hidden;
`;

const TableHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px;
  border-bottom: 1px solid #ddd;
`;

const Title = styled.h2`
  margin: 0;
  color: #333;
`;

const ActionButtons = styled.div`
  display: flex;
  gap: 10px;
`;

const Button = styled.button`
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: background-color 0.2s;
`;

const PrimaryButton = styled(Button)`
  background-color: #28a745;
  color: white;
  
  &:hover {
    background-color: #218838;
  }
`;

const SecondaryButton = styled(Button)`
  background-color: #6c757d;
  color: white;
  
  &:hover {
    background-color: #545b62;
  }
`;

const Table = styled.table`
  width: 100%;
  border-collapse: collapse;
`;

const TableHead = styled.thead`
  background-color: #f8f9fa;
`;

const TableRow = styled.tr<{ clickable?: boolean; selected?: boolean }>`
  ${props => props.clickable && `
    cursor: pointer;
    &:hover {
      background-color: #f8f9fa;
    }
  `}
  
  ${props => props.selected && `
    background-color: #e3f2fd;
  `}
`;

const TableHeader2 = styled.th`
  padding: 12px 8px;
  text-align: left;
  font-weight: 600;
  color: #495057;
  border-bottom: 2px solid #dee2e6;
  font-size: 14px;
`;

const TableCell = styled.td`
  padding: 8px;
  border-bottom: 1px solid #dee2e6;
  font-size: 14px;
  vertical-align: top;
`;

const EditableCell = styled(TableCell)`
  padding: 4px;
`;

const Input = styled.input`
  width: 100%;
  padding: 4px 8px;
  border: 1px solid #ddd;
  border-radius: 3px;
  font-size: 12px;
  
  &:focus {
    outline: none;
    border-color: #007bff;
  }
`;

const TextArea = styled.textarea`
  width: 100%;
  padding: 4px 8px;
  border: 1px solid #ddd;
  border-radius: 3px;
  font-size: 12px;
  min-height: 40px;
  resize: vertical;
  
  &:focus {
    outline: none;
    border-color: #007bff;
  }
`;

const ShotTypeSelect = styled.select`
  width: 100%;
  padding: 4px 8px;
  border: 1px solid #ddd;
  border-radius: 3px;
  font-size: 12px;
  
  &:focus {
    outline: none;
    border-color: #007bff;
  }
`;

const ShotTypeTag = styled.span<{ shotType: ShotType }>`
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
  color: white;
  background-color: ${props => {
    switch (props.shotType) {
      case 'Дальний': return '#6f42c1';
      case 'Общий': return '#007bff';
      case 'Средний': return '#28a745';
      case 'Крупный': return '#fd7e14';
      case 'Деталь': return '#dc3545';
      default: return '#6c757d';
    }
  }};
`;

const SpeakerTag = styled.span`
  display: inline-block;
  padding: 2px 8px;
  background-color: #e9ecef;
  border-radius: 12px;
  font-size: 11px;
  margin-right: 4px;
  cursor: pointer;
  
  &:hover {
    background-color: #dee2e6;
  }
`;

const SpeakerInput = styled.input`
  padding: 2px 8px;
  border: 1px solid #007bff;
  border-radius: 12px;
  font-size: 11px;
  width: 80px;
`;

const LoadingContainer = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
  height: 200px;
  color: #666;
`;

const ErrorContainer = styled.div`
  padding: 20px;
  text-align: center;
  color: #dc3545;
`;

const MontageEditor: React.FC = () => {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const playerRef = useRef<ReactPlayer>(null);
  
  const [task, setTask] = useState<ProcessingTask | null>(null);
  const [montageRows, setMontageRows] = useState<MontageRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedRow, setSelectedRow] = useState<number | null>(null);
  const [editingSpeaker, setEditingSpeaker] = useState<number | null>(null);
  const [newSpeakerName, setNewSpeakerName] = useState('');
  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  useEffect(() => {
    if (!taskId) {
      setError('ID задачи не найден');
      setLoading(false);
      return;
    }

    const fetchTaskData = async () => {
      try {
        const taskData = await apiService.getTaskStatus(taskId);
        setTask(taskData);
        
        if (taskData.result) {
          setMontageRows(taskData.result);
        }
      } catch (err) {
        setError('Не удалось загрузить данные задачи');
      } finally {
        setLoading(false);
      }
    };

    fetchTaskData();
  }, [taskId]);

  const parseTimecode = (timecode: string): number => {
    const parts = timecode.split(':');
    if (parts.length === 4) {
      const [hours, minutes, seconds, frames] = parts.map(Number);
      return hours * 3600 + minutes * 60 + seconds + frames / 25; // Assuming 25 fps
    }
    return 0;
  };

  const formatTimecode = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    const frames = Math.floor((seconds % 1) * 25);
    
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}:${frames.toString().padStart(2, '0')}`;
  };

  const handleRowClick = (row: MontageRow) => {
    const startTime = parseTimecode(row.start_timecode);
    if (playerRef.current) {
      playerRef.current.seekTo(startTime);
      setSelectedRow(row.number);
    }
  };

  const handleCellEdit = (rowNumber: number, field: keyof MontageRow, value: any) => {
    setMontageRows(prev => prev.map(row => 
      row.number === rowNumber ? { ...row, [field]: value } : row
    ));
    setHasChanges(true);
  };

  const handleSpeakerEdit = (rowNumber: number) => {
    setEditingSpeaker(rowNumber);
    const row = montageRows.find(r => r.number === rowNumber);
    setNewSpeakerName(row?.speaker || '');
  };

  const handleSpeakerSave = (rowNumber: number) => {
    handleCellEdit(rowNumber, 'speaker', newSpeakerName);
    setEditingSpeaker(null);
    setNewSpeakerName('');
  };

  const handleSpeakerCancel = () => {
    setEditingSpeaker(null);
    setNewSpeakerName('');
  };

  const handleSave = async () => {
    if (!taskId) return;
    
    try {
      await apiService.updateMontage(taskId, montageRows);
      setHasChanges(false);
      alert('Изменения сохранены');
    } catch (error) {
      alert('Ошибка при сохранении');
    }
  };

  const handleExport = async () => {
    if (!taskId) return;
    
    try {
      const blob = await apiService.downloadDocx(taskId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `montage_list_${taskId}.docx`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      alert('Ошибка при экспорте');
    }
  };

  const handleProgress = (state: { played: number, playedSeconds: number }) => {
    setCurrentTime(state.playedSeconds);
  };

  if (loading) {
    return (
      <EditorContainer>
        <LoadingContainer>
          Загрузка монтажного листа...
        </LoadingContainer>
      </EditorContainer>
    );
  }

  if (error || !task) {
    return (
      <EditorContainer>
        <ErrorContainer>
          <h3>Ошибка</h3>
          <p>{error || 'Задача не найдена'}</p>
          <SecondaryButton onClick={() => navigate('/upload')}>
            Вернуться к загрузке
          </SecondaryButton>
        </ErrorContainer>
      </EditorContainer>
    );
  }

  return (
    <EditorContainer>
      <VideoSection>
        <VideoContainer>
          <h3>Видеоплеер</h3>
          <VideoPlayer>
            <ReactPlayer
              ref={playerRef}
              url={task.video_path}
              width="100%"
              height="100%"
              controls={true}
              playing={isPlaying}
              onProgress={handleProgress}
              onPlay={() => setIsPlaying(true)}
              onPause={() => setIsPlaying(false)}
            />
          </VideoPlayer>
          <VideoControls>
            <PlayButton onClick={() => setIsPlaying(!isPlaying)}>
              {isPlaying ? 'Пауза' : 'Воспроизвести'}
            </PlayButton>
            <TimeDisplay>
              {formatTimecode(currentTime)}
            </TimeDisplay>
          </VideoControls>
        </VideoContainer>
      </VideoSection>

      <TableSection>
        <TableContainer>
          <TableHeader>
            <Title>Монтажный лист</Title>
            <ActionButtons>
              <PrimaryButton onClick={handleSave} disabled={!hasChanges}>
                {hasChanges ? 'Сохранить изменения' : 'Сохранено'}
              </PrimaryButton>
              <SecondaryButton onClick={handleExport}>
                Экспорт DOCX
              </SecondaryButton>
            </ActionButtons>
          </TableHeader>

          <Table>
            <TableHead>
              <TableRow>
                <TableHeader2>№</TableHeader2>
                <TableHeader2>Начало</TableHeader2>
                <TableHeader2>Конец</TableHeader2>
                <TableHeader2>Тип плана</TableHeader2>
                <TableHeader2>Описание</TableHeader2>
                <TableHeader2>Диалоги</TableHeader2>
                <TableHeader2>Спикер</TableHeader2>
              </TableRow>
            </TableHead>
            <tbody>
              {montageRows.map((row) => (
                <TableRow
                  key={row.number}
                  clickable
                  selected={selectedRow === row.number}
                  onClick={() => handleRowClick(row)}
                >
                  <TableCell>{row.number}</TableCell>
                  
                  <EditableCell>
                    <Input
                      value={row.start_timecode}
                      onChange={(e) => handleCellEdit(row.number, 'start_timecode', e.target.value)}
                      onClick={(e) => e.stopPropagation()}
                    />
                  </EditableCell>
                  
                  <EditableCell>
                    <Input
                      value={row.end_timecode}
                      onChange={(e) => handleCellEdit(row.number, 'end_timecode', e.target.value)}
                      onClick={(e) => e.stopPropagation()}
                    />
                  </EditableCell>
                  
                  <EditableCell>
                    <ShotTypeSelect
                      value={row.shot_type}
                      onChange={(e) => handleCellEdit(row.number, 'shot_type', e.target.value as ShotType)}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <option value="Дальний">Дальний</option>
                      <option value="Общий">Общий</option>
                      <option value="Средний">Средний</option>
                      <option value="Крупный">Крупный</option>
                      <option value="Деталь">Деталь</option>
                    </ShotTypeSelect>
                    <div style={{ marginTop: '4px' }}>
                      <ShotTypeTag shotType={row.shot_type}>
                        {row.shot_type}
                      </ShotTypeTag>
                    </div>
                  </EditableCell>
                  
                  <EditableCell>
                    <TextArea
                      value={row.description}
                      onChange={(e) => handleCellEdit(row.number, 'description', e.target.value)}
                      onClick={(e) => e.stopPropagation()}
                      placeholder="Описание сцены..."
                    />
                  </EditableCell>
                  
                  <EditableCell>
                    <TextArea
                      value={row.dialogue}
                      onChange={(e) => handleCellEdit(row.number, 'dialogue', e.target.value)}
                      onClick={(e) => e.stopPropagation()}
                      placeholder="Текст диалогов..."
                    />
                  </EditableCell>
                  
                  <EditableCell>
                    {editingSpeaker === row.number ? (
                      <div onClick={(e) => e.stopPropagation()}>
                        <SpeakerInput
                          value={newSpeakerName}
                          onChange={(e) => setNewSpeakerName(e.target.value)}
                          onKeyPress={(e) => {
                            if (e.key === 'Enter') {
                              handleSpeakerSave(row.number);
                            } else if (e.key === 'Escape') {
                              handleSpeakerCancel();
                            }
                          }}
                          onBlur={() => handleSpeakerSave(row.number)}
                          autoFocus
                        />
                      </div>
                    ) : (
                      <SpeakerTag
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSpeakerEdit(row.number);
                        }}
                      >
                        {row.speaker || 'Без имени'}
                      </SpeakerTag>
                    )}
                  </EditableCell>
                </TableRow>
              ))}
            </tbody>
          </Table>
        </TableContainer>
      </TableSection>
    </EditorContainer>
  );
};

export default MontageEditor;