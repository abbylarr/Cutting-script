import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import styled from 'styled-components';
import { User, Project } from '../types';
import { apiService } from '../services/api';

const SidebarContainer = styled.div`
  width: 320px;
  background-color: #2c3e50;
  color: white;
  padding: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  height: 100vh;
`;

const UserSection = styled.div`
  padding: 20px;
  background-color: #34495e;
  border-bottom: 1px solid #4a5f7a;
`;

const UserInfo = styled.div`
  margin-bottom: 15px;
`;

const UserEmail = styled.div`
  font-weight: 600;
  margin-bottom: 8px;
  font-size: 16px;
`;

const UserBalance = styled.div`
  font-size: 14px;
  color: #bdc3c7;
  margin-bottom: 8px;
`;

const BalanceAmount = styled.span`
  font-weight: 600;
  color: #2ecc71;
`;

const UserActions = styled.div`
  display: flex;
  gap: 10px;
`;

const ActionButton = styled.button`
  flex: 1;
  padding: 8px 12px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  transition: background-color 0.2s;
`;

const TopUpButton = styled(ActionButton)`
  background-color: #3498db;
  color: white;

  &:hover {
    background-color: #2980b9;
  }
`;

const LogoutButton = styled(ActionButton)`
  background-color: #e74c3c;
  color: white;

  &:hover {
    background-color: #c0392b;
  }
`;

const ProjectsSection = styled.div`
  flex: 1;
  padding: 20px;
  overflow-y: auto;
`;

const SectionTitle = styled.h3`
  margin: 0 0 20px 0;
  font-size: 18px;
  color: #ecf0f1;
`;

const SearchContainer = styled.div`
  margin-bottom: 20px;
`;

const SearchInput = styled.input`
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #4a5f7a;
  border-radius: 6px;
  background-color: #34495e;
  color: white;
  font-size: 14px;

  &::placeholder {
    color: #95a5a6;
  }

  &:focus {
    outline: none;
    border-color: #3498db;
    background-color: #2c3e50;
  }
`;

const FilterContainer = styled.div`
  margin-bottom: 20px;
`;

const FilterSelect = styled.select`
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #4a5f7a;
  border-radius: 6px;
  background-color: #34495e;
  color: white;
  font-size: 14px;

  &:focus {
    outline: none;
    border-color: #3498db;
  }
`;

const ProjectsList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const ProjectItem = styled.div<{ active?: boolean }>`
  padding: 15px;
  background-color: ${props => props.active ? '#3498db' : '#34495e'};
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid ${props => props.active ? '#2980b9' : 'transparent'};

  &:hover {
    background-color: ${props => props.active ? '#2980b9' : '#4a5f7a'};
    transform: translateY(-1px);
  }
`;

const ProjectTitle = styled.div`
  font-weight: 600;
  margin-bottom: 6px;
  font-size: 14px;
  color: ${props => props.color || '#ecf0f1'};
`;

const ProjectMeta = styled.div`
  font-size: 12px;
  color: #bdc3c7;
  margin-bottom: 4px;
`;

const ProjectStatus = styled.span<{ status: string }>`
  display: inline-block;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 10px;
  font-weight: 500;
  text-transform: uppercase;
  
  ${props => {
    switch (props.status) {
      case 'completed':
        return 'background-color: #27ae60; color: white;';
      case 'processing':
        return 'background-color: #f39c12; color: white;';
      case 'failed':
        return 'background-color: #e74c3c; color: white;';
      default:
        return 'background-color: #95a5a6; color: white;';
    }
  }}
`;

const ProjectActions = styled.div`
  display: flex;
  gap: 8px;
  margin-top: 8px;
`;

const ProjectActionButton = styled.button`
  padding: 4px 8px;
  border: none;
  border-radius: 4px;
  font-size: 10px;
  cursor: pointer;
  transition: background-color 0.2s;
`;

const EditButton = styled(ProjectActionButton)`
  background-color: #3498db;
  color: white;

  &:hover {
    background-color: #2980b9;
  }
`;

const DeleteButton = styled(ProjectActionButton)`
  background-color: #e74c3c;
  color: white;

  &:hover {
    background-color: #c0392b;
  }
`;

const DuplicateButton = styled(ProjectActionButton)`
  background-color: #95a5a6;
  color: white;

  &:hover {
    background-color: #7f8c8d;
  }
`;

const EmptyState = styled.div`
  text-align: center;
  padding: 40px 20px;
  color: #95a5a6;
`;

const EmptyStateIcon = styled.div`
  font-size: 48px;
  margin-bottom: 16px;
`;

const EmptyStateText = styled.p`
  margin: 0;
  font-size: 14px;
`;

const NewProjectButton = styled.button`
  width: 100%;
  padding: 12px;
  background-color: #27ae60;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  margin-bottom: 20px;
  transition: background-color 0.2s;

  &:hover {
    background-color: #229954;
  }
`;

const LoadingContainer = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 40px;
  color: #95a5a6;
`;

interface SidebarProps {
  user: User;
  onLogout: () => void;
  currentTaskId: string | null;
  onTaskSelect: (taskId: string) => void;
}

const Sidebar: React.FC<SidebarProps> = ({ user, onLogout, currentTaskId, onTaskSelect }) => {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  useEffect(() => {
    const fetchProjects = async () => {
      try {
        const projectsData = await apiService.getProjects();
        setProjects(projectsData);
      } catch (error) {
        console.error('Failed to fetch projects:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchProjects();
  }, []);

  const filteredProjects = projects.filter(project => {
    const matchesSearch = project.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         project.metadata.production_company.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesStatus = statusFilter === 'all' || 
                         (statusFilter === 'completed' && project.montage_rows && project.montage_rows.length > 0) ||
                         (statusFilter === 'processing' && !project.montage_rows) ||
                         (statusFilter === 'recent' && new Date(project.created_at) > new Date(Date.now() - 7 * 24 * 60 * 60 * 1000));
    
    return matchesSearch && matchesStatus;
  });

  const handleProjectClick = (project: Project) => {
    if (project.task_id) {
      onTaskSelect(project.task_id);
      if (project.montage_rows && project.montage_rows.length > 0) {
        navigate(`/editor/${project.task_id}`);
      } else {
        navigate(`/task/${project.task_id}`);
      }
    }
  };

  const handleDeleteProject = async (e: React.MouseEvent, projectId: string) => {
    e.stopPropagation();
    if (window.confirm('Вы уверены, что хотите удалить этот проект?')) {
      try {
        await apiService.deleteProject(projectId);
        setProjects(prev => prev.filter(p => p.id !== projectId));
      } catch (error) {
        alert('Ошибка при удалении проекта');
      }
    }
  };

  const handleDuplicateProject = async (e: React.MouseEvent, project: Project) => {
    e.stopPropagation();
    // This would create a new project with the same metadata
    console.log('Duplicate project:', project.title);
    alert('Функция дублирования будет добавлена в следующей версии');
  };

  const handleTopUp = () => {
    // Navigate to payment page or open payment modal
    alert('Функция пополнения баланса будет добавлена в следующей версии');
  };

  const handleNewProject = () => {
    navigate('/upload');
  };

  const getProjectStatus = (project: Project) => {
    if (project.montage_rows && project.montage_rows.length > 0) {
      return 'completed';
    }
    return 'processing';
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric'
    });
  };

  return (
    <SidebarContainer>
      <UserSection>
        <UserInfo>
          <UserEmail>{user.email}</UserEmail>
          <UserBalance>
            Баланс: <BalanceAmount>{user.balance} ₽</BalanceAmount>
          </UserBalance>
        </UserInfo>
        <UserActions>
          <TopUpButton onClick={handleTopUp}>
            Пополнить
          </TopUpButton>
          <LogoutButton onClick={onLogout}>
            Выйти
          </LogoutButton>
        </UserActions>
      </UserSection>

      <ProjectsSection>
        <SectionTitle>Проекты</SectionTitle>
        
        <NewProjectButton onClick={handleNewProject}>
          + Новый проект
        </NewProjectButton>

        <SearchContainer>
          <SearchInput
            type="text"
            placeholder="Поиск проектов..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </SearchContainer>

        <FilterContainer>
          <FilterSelect
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">Все проекты</option>
            <option value="completed">Завершенные</option>
            <option value="processing">В обработке</option>
            <option value="recent">Недавние</option>
          </FilterSelect>
        </FilterContainer>

        {loading ? (
          <LoadingContainer>
            Загрузка проектов...
          </LoadingContainer>
        ) : filteredProjects.length === 0 ? (
          <EmptyState>
            <EmptyStateIcon>📁</EmptyStateIcon>
            <EmptyStateText>
              {searchTerm || statusFilter !== 'all' 
                ? 'Проекты не найдены' 
                : 'У вас пока нет проектов'
              }
            </EmptyStateText>
          </EmptyState>
        ) : (
          <ProjectsList>
            {filteredProjects.map((project) => (
              <ProjectItem
                key={project.id}
                active={project.task_id === currentTaskId}
                onClick={() => handleProjectClick(project)}
              >
                <ProjectTitle>{project.title}</ProjectTitle>
                <ProjectMeta>
                  {project.metadata.production_company} • {formatDate(project.created_at)}
                </ProjectMeta>
                <ProjectMeta>
                  <ProjectStatus status={getProjectStatus(project)}>
                    {getProjectStatus(project) === 'completed' ? 'Готов' : 'Обработка'}
                  </ProjectStatus>
                </ProjectMeta>
                <ProjectActions>
                  <EditButton
                    onClick={(e) => {
                      e.stopPropagation();
                      handleProjectClick(project);
                    }}
                  >
                    Открыть
                  </EditButton>
                  <DuplicateButton
                    onClick={(e) => handleDuplicateProject(e, project)}
                  >
                    Копировать
                  </DuplicateButton>
                  <DeleteButton
                    onClick={(e) => handleDeleteProject(e, project.id)}
                  >
                    Удалить
                  </DeleteButton>
                </ProjectActions>
              </ProjectItem>
            ))}
          </ProjectsList>
        )}
      </ProjectsSection>
    </SidebarContainer>
  );
};

export default Sidebar;