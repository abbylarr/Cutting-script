import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import styled, { keyframes, css } from 'styled-components';
import { ProcessingTask, ProcessingStep } from '../types';
import { apiService } from '../services/api';
import { websocketService, WebSocketMessage } from '../services/websocket';

const fadeIn = keyframes`
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
`;

const pulse = keyframes`
  0% { transform: scale(1); }
  50% { transform: scale(1.05); }
  100% { transform: scale(1); }
`;

const shimmer = keyframes`
  0% { background-position: -200px 0; }
  100% { background-position: calc(200px + 100%) 0; }
`;

const ProgressContainer = styled.div`
  max-width: 800px;
  margin: 0 auto;
  padding: 40px 20px;
  animation: ${fadeIn} 0.6s ease-out;
`;

const Header = styled.div`
  text-align: center;
  margin-bottom: 40px;
`;

const Title = styled.h1`
  color: #333;
  margin-bottom: 10px;
  font-size: 28px;
`;

const Subtitle = styled.p`
  color: #666;
  font-size: 16px;
  margin: 0;
`;

const ProgressCard = styled.div`
  background: white;
  border-radius: 12px;
  padding: 30px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
  margin-bottom: 30px;
`;

const OverallProgress = styled.div`
  margin-bottom: 30px;
`;

const ProgressLabel = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
`;

const ProgressText = styled.span`
  font-weight: 600;
  color: #333;
`;

const ProgressPercentage = styled.span`
  font-weight: 700;
  color: #007bff;
  font-size: 18px;
`;

const ProgressBarContainer = styled.div`
  width: 100%;
  height: 12px;
  background-color: #e9ecef;
  border-radius: 6px;
  overflow: hidden;
  position: relative;
`;

const ProgressBarFill = styled.div<{ progress: number; animated?: boolean }>`
  height: 100%;
  background: linear-gradient(90deg, #007bff, #0056b3);
  border-radius: 6px;
  transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
  width: ${props => props.progress}%;
  position: relative;
  
  ${props => props.animated && css`
    &::after {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      bottom: 0;
      right: 0;
      background-image: linear-gradient(
        -45deg,
        rgba(255, 255, 255, .2) 25%,
        transparent 25%,
        transparent 50%,
        rgba(255, 255, 255, .2) 50%,
        rgba(255, 255, 255, .2) 75%,
        transparent 75%,
        transparent
      );
      background-size: 50px 50px;
      animation: ${shimmer} 2s linear infinite;
    }
  `}
`;

const CurrentStepContainer = styled.div`
  margin-bottom: 30px;
`;

const StepTitle = styled.h3`
  color: #333;
  margin-bottom: 15px;
  display: flex;
  align-items: center;
  gap: 10px;
`;

const StepIcon = styled.div<{ spinning?: boolean }>`
  width: 24px;
  height: 24px;
  border: 3px solid #007bff;
  border-top: 3px solid transparent;
  border-radius: 50%;
  
  ${props => props.spinning && css`
    animation: ${pulse} 2s ease-in-out infinite;
  `}
`;

const StepDescription = styled.p`
  color: #666;
  font-size: 16px;
  line-height: 1.6;
  margin-bottom: 15px;
`;

const EtaContainer = styled.div`
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 15px;
  background-color: #f8f9fa;
  border-radius: 8px;
  margin-bottom: 20px;
`;

const EtaIcon = styled.div`
  font-size: 20px;
`;

const EtaText = styled.span`
  color: #495057;
  font-weight: 500;
`;

const StepsTimeline = styled.div`
  margin-top: 30px;
`;

const TimelineTitle = styled.h4`
  color: #333;
  margin-bottom: 20px;
`;

const TimelineStep = styled.div<{ completed: boolean; current: boolean }>`
  display: flex;
  align-items: center;
  padding: 12px 0;
  position: relative;
  
  &:not(:last-child)::after {
    content: '';
    position: absolute;
    left: 11px;
    top: 40px;
    width: 2px;
    height: 20px;
    background-color: ${props => props.completed ? '#28a745' : '#dee2e6'};
  }
`;

const TimelineIcon = styled.div<{ completed: boolean; current: boolean }>`
  width: 24px;
  height: 24px;
  border-radius: 50%;
  margin-right: 15px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: bold;
  
  ${props => {
    if (props.completed) {
      return css`
        background-color: #28a745;
        color: white;
      `;
    } else if (props.current) {
      return css`
        background-color: #007bff;
        color: white;
        animation: ${pulse} 2s ease-in-out infinite;
      `;
    } else {
      return css`
        background-color: #dee2e6;
        color: #6c757d;
      `;
    }
  }}
`;

const TimelineText = styled.span<{ completed: boolean; current: boolean }>`
  color: ${props => props.completed ? '#28a745' : props.current ? '#007bff' : '#6c757d'};
  font-weight: ${props => props.current ? '600' : '400'};
`;

const ActionButtons = styled.div`
  display: flex;
  gap: 15px;
  justify-content: center;
  margin-top: 30px;
`;

const Button = styled.button`
  padding: 12px 24px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
`;

const PrimaryButton = styled(Button)`
  background-color: #007bff;
  color: white;
  
  &:hover {
    background-color: #0056b3;
  }
`;

const SecondaryButton = styled(Button)`
  background-color: #6c757d;
  color: white;
  
  &:hover {
    background-color: #545b62;
  }
`;

const ErrorContainer = styled.div`
  background-color: #f8d7da;
  color: #721c24;
  padding: 20px;
  border-radius: 8px;
  border: 1px solid #f5c6cb;
  text-align: center;
`;

const ProcessingProgress: React.FC = () => {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const [task, setTask] = useState<ProcessingTask | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [useWebSocket, setUseWebSocket] = useState(true);

  // Processing steps with magical descriptions
  const processingSteps: ProcessingStep[] = [
    {
      name: 'video_validation',
      description: '🎬 Проверяем ваше видео на совместимость с нашими алгоритмами...',
      progress: 0,
      eta_seconds: 10
    },
    {
      name: 'audio_extraction',
      description: '🎵 Извлекаем звуковую дорожку и готовим её для анализа...',
      progress: 0,
      eta_seconds: 30
    },
    {
      name: 'scene_detection',
      description: '🎯 Анализируем смену планов и находим границы сцен...',
      progress: 0,
      eta_seconds: 120
    },
    {
      name: 'transcription',
      description: '🗣️ Преобразуем речь в текст с помощью нейросетей...',
      progress: 0,
      eta_seconds: 180
    },
    {
      name: 'speaker_diarization',
      description: '👥 Определяем, кто и когда говорит в вашем видео...',
      progress: 0,
      eta_seconds: 90
    },
    {
      name: 'visual_analysis',
      description: '👁️ Анализируем кадры и определяем типы планов...',
      progress: 0,
      eta_seconds: 240
    },
    {
      name: 'music_detection',
      description: '🎼 Ищем музыкальные фрагменты и звуковые эффекты...',
      progress: 0,
      eta_seconds: 60
    },
    {
      name: 'document_generation',
      description: '📄 Создаём монтажный лист в формате DOCX...',
      progress: 0,
      eta_seconds: 20
    }
  ];

  const handleWebSocketMessage = useCallback((message: WebSocketMessage) => {
    if (message.task_id === taskId) {
      setTask(prevTask => {
        if (!prevTask) return prevTask;
        
        const updatedTask = { ...prevTask, ...message.data };
        
        if (message.type === 'task_completed') {
          // Redirect to editor after a short delay
          setTimeout(() => {
            navigate(`/editor/${taskId}`);
          }, 2000);
        } else if (message.type === 'task_failed') {
          setError(updatedTask.error || 'Произошла ошибка при обработке');
        }
        
        return updatedTask;
      });
    }
  }, [taskId, navigate]);

  useEffect(() => {
    if (!taskId) {
      setError('ID задачи не найден');
      setLoading(false);
      return;
    }

    const fetchTaskStatus = async () => {
      try {
        const taskData = await apiService.getTaskStatus(taskId);
        setTask(taskData);
        
        if (taskData.status === 'completed') {
          // Redirect to editor after a short delay
          setTimeout(() => {
            navigate(`/editor/${taskId}`);
          }, 2000);
        } else if (taskData.status === 'failed') {
          setError(taskData.error || 'Произошла ошибка при обработке');
        }
      } catch (err) {
        setError('Не удалось получить статус задачи');
      } finally {
        setLoading(false);
      }
    };

    // Initial fetch
    fetchTaskStatus();

    // Try to establish WebSocket connection for real-time updates
    if (useWebSocket && taskId) {
      const connectWebSocket = async () => {
        try {
          await websocketService.connect(taskId);
          websocketService.subscribe(taskId, handleWebSocketMessage);
        } catch (error) {
          console.warn('WebSocket connection failed, falling back to polling:', error);
          setUseWebSocket(false);
        }
      };
      
      connectWebSocket();
    }

    // Fallback polling if WebSocket is not available or fails
    let interval: NodeJS.Timeout | null = null;
    if (!useWebSocket) {
      interval = setInterval(() => {
        if (task?.status === 'processing') {
          fetchTaskStatus();
        }
      }, 2000);
    }

    return () => {
      if (interval) {
        clearInterval(interval);
      }
      if (useWebSocket) {
        websocketService.unsubscribe(taskId);
        websocketService.disconnect();
      }
    };
  }, [taskId, navigate, useWebSocket, handleWebSocketMessage, task?.status]);

  const getCurrentStep = () => {
    if (!task) return processingSteps[0];
    
    const stepIndex = processingSteps.findIndex(step => 
      step.name === task.current_step
    );
    
    return stepIndex >= 0 ? processingSteps[stepIndex] : processingSteps[0];
  };

  const getCurrentStepIndex = () => {
    if (!task) return 0;
    
    const stepIndex = processingSteps.findIndex(step => 
      step.name === task.current_step
    );
    
    return stepIndex >= 0 ? stepIndex : 0;
  };

  const formatEta = (seconds: number) => {
    if (seconds < 60) return `${seconds} сек`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return remainingSeconds > 0 ? `${minutes} мин ${remainingSeconds} сек` : `${minutes} мин`;
  };

  const handleBackToUpload = () => {
    navigate('/upload');
  };

  const handleViewResult = () => {
    if (task) {
      navigate(`/editor/${task.task_id}`);
    }
  };

  if (loading) {
    return (
      <ProgressContainer>
        <ProgressCard>
          <StepTitle>
            <StepIcon spinning />
            Загрузка...
          </StepTitle>
        </ProgressCard>
      </ProgressContainer>
    );
  }

  if (error) {
    return (
      <ProgressContainer>
        <ErrorContainer>
          <h3>Ошибка обработки</h3>
          <p>{error}</p>
          <ActionButtons>
            <SecondaryButton onClick={handleBackToUpload}>
              Вернуться к загрузке
            </SecondaryButton>
          </ActionButtons>
        </ErrorContainer>
      </ProgressContainer>
    );
  }

  if (!task) {
    return (
      <ProgressContainer>
        <ErrorContainer>
          <h3>Задача не найдена</h3>
          <p>Не удалось найти задачу с указанным ID</p>
          <ActionButtons>
            <SecondaryButton onClick={handleBackToUpload}>
              Вернуться к загрузке
            </SecondaryButton>
          </ActionButtons>
        </ErrorContainer>
      </ProgressContainer>
    );
  }

  const currentStep = getCurrentStep();
  const currentStepIndex = getCurrentStepIndex();
  const isCompleted = task.status === 'completed';
  const isProcessing = task.status === 'processing';

  return (
    <ProgressContainer>
      <Header>
        <Title>
          {isCompleted ? '✨ Обработка завершена!' : '🎬 Обрабатываем ваше видео'}
        </Title>
        <Subtitle>
          {isCompleted 
            ? 'Монтажный лист готов к редактированию'
            : 'Пожалуйста, подождите, пока мы анализируем ваш материал'
          }
        </Subtitle>
      </Header>

      <ProgressCard>
        <OverallProgress>
          <ProgressLabel>
            <ProgressText>Общий прогресс</ProgressText>
            <ProgressPercentage>{Math.round(task.progress)}%</ProgressPercentage>
          </ProgressLabel>
          <ProgressBarContainer>
            <ProgressBarFill 
              progress={task.progress} 
              animated={isProcessing}
            />
          </ProgressBarContainer>
        </OverallProgress>

        {isProcessing && (
          <CurrentStepContainer>
            <StepTitle>
              <StepIcon spinning />
              {currentStep.name.replace('_', ' ').toUpperCase()}
            </StepTitle>
            <StepDescription>
              {currentStep.description}
            </StepDescription>
            {currentStep.eta_seconds && (
              <EtaContainer>
                <EtaIcon>⏱️</EtaIcon>
                <EtaText>
                  Примерное время: {formatEta(currentStep.eta_seconds)}
                </EtaText>
              </EtaContainer>
            )}
          </CurrentStepContainer>
        )}

        <StepsTimeline>
          <TimelineTitle>Этапы обработки</TimelineTitle>
          {processingSteps.map((step, index) => (
            <TimelineStep
              key={step.name}
              completed={index < currentStepIndex || isCompleted}
              current={index === currentStepIndex && isProcessing}
            >
              <TimelineIcon
                completed={index < currentStepIndex || isCompleted}
                current={index === currentStepIndex && isProcessing}
              >
                {index < currentStepIndex || isCompleted ? '✓' : index + 1}
              </TimelineIcon>
              <TimelineText
                completed={index < currentStepIndex || isCompleted}
                current={index === currentStepIndex && isProcessing}
              >
                {step.description}
              </TimelineText>
            </TimelineStep>
          ))}
        </StepsTimeline>

        <ActionButtons>
          {isCompleted ? (
            <PrimaryButton onClick={handleViewResult}>
              Перейти к редактированию
            </PrimaryButton>
          ) : (
            <SecondaryButton onClick={handleBackToUpload}>
              Загрузить другое видео
            </SecondaryButton>
          )}
        </ActionButtons>
      </ProgressCard>
    </ProgressContainer>
  );
};

export default ProcessingProgress;