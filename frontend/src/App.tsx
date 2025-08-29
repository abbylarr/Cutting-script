import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import styled from 'styled-components';
import { User } from './types';
import { apiService } from './services/api';
import Sidebar from './components/Sidebar';
import VideoUpload from './components/VideoUpload';
import ProcessingProgress from './components/ProcessingProgress';
import MontageEditor from './components/MontageEditor';
import Login from './components/Login';

const AppContainer = styled.div`
  display: flex;
  height: 100vh;
  background-color: #f5f5f5;
`;

const MainContent = styled.div`
  flex: 1;
  overflow-y: auto;
  padding: 20px;
`;

const App: React.FC = () => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);

  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem('auth_token');
      if (token) {
        try {
          const userData = await apiService.getCurrentUser();
          setUser(userData);
        } catch (error) {
          localStorage.removeItem('auth_token');
        }
      }
      setLoading(false);
    };

    checkAuth();
  }, []);

  const handleLogin = (userData: User, token: string) => {
    localStorage.setItem('auth_token', token);
    setUser(userData);
  };

  const handleLogout = () => {
    localStorage.removeItem('auth_token');
    setUser(null);
    setCurrentTaskId(null);
  };

  const handleTaskCreated = (taskId: string) => {
    setCurrentTaskId(taskId);
  };

  if (loading) {
    return <div>Загрузка...</div>;
  }

  if (!user) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <Router>
      <AppContainer>
        <Sidebar 
          user={user} 
          onLogout={handleLogout}
          currentTaskId={currentTaskId}
          onTaskSelect={setCurrentTaskId}
        />
        <MainContent>
          <Routes>
            <Route 
              path="/" 
              element={
                currentTaskId ? (
                  <Navigate to={`/task/${currentTaskId}`} replace />
                ) : (
                  <VideoUpload onTaskCreated={handleTaskCreated} />
                )
              } 
            />
            <Route 
              path="/upload" 
              element={<VideoUpload onTaskCreated={handleTaskCreated} />} 
            />
            <Route 
              path="/task/:taskId" 
              element={<ProcessingProgress />} 
            />
            <Route 
              path="/editor/:taskId" 
              element={<MontageEditor />} 
            />
          </Routes>
        </MainContent>
      </AppContainer>
    </Router>
  );
};

export default App;