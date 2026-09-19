import axios from 'axios';
import { FilmMetadata, ProcessingTask, Project, User, MontageRow } from '../types';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Add response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Log error for debugging
    console.error('API Error:', {
      status: error.response?.status,
      data: error.response?.data,
      message: error.message,
      url: error.config?.url
    });
    
    // Handle 401 errors (unauthorized)
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token');
      // Optionally redirect to login page
      // window.location.href = '/login';
    }
    
    return Promise.reject(error);
  }
);

export const apiService = {
  // Auth endpoints
  login: async (email: string, password: string) => {
    try {
      const response = await api.post('/auth/login', { email, password });
      return response.data;
    } catch (error: any) {
      // Extract error message from different possible response structures
      const errorMessage = 
        error.response?.data?.detail || 
        error.response?.data?.message || 
        error.response?.data?.error || 
        error.message || 
        'Произошла ошибка при входе';
      throw new Error(errorMessage);
    }
  },

  register: async (email: string, password: string) => {
    try {
      const response = await api.post('/auth/register', { email, password });
      return response.data;
    } catch (error: any) {
      // Extract error message from different possible response structures
      const errorMessage = 
        error.response?.data?.detail || 
        error.response?.data?.message || 
        error.response?.data?.error || 
        error.message || 
        'Произошла ошибка при регистрации';
      throw new Error(errorMessage);
    }
  },

  getCurrentUser: async (): Promise<User> => {
    const response = await api.get('/auth/me');
    return response.data;
  },

  // Upload endpoints
  uploadVideo: async (
    file: File, 
    metadata: FilmMetadata,
    settings: { timecode_start: string; standard: string; use_srt: boolean },
    onProgress?: (progress: number) => void
  ) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('metadata', JSON.stringify(metadata));
    formData.append('settings', JSON.stringify(settings));

    const response = await api.post('/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(progress);
        }
      },
    });
    return response.data;
  },

  uploadSrt: async (taskId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await api.post(`/upload_srt/${taskId}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // Task endpoints
  getTaskStatus: async (taskId: string): Promise<ProcessingTask> => {
    const response = await api.get(`/status/${taskId}`);
    return response.data;
  },

  updateMontage: async (taskId: string, rows: MontageRow[]) => {
    const response = await api.patch(`/montage/${taskId}`, { rows });
    return response.data;
  },

  saveProject: async (taskId: string, rows: MontageRow[]) => {
    const response = await api.post(`/save/${taskId}`, { rows });
    return response.data;
  },

  downloadDocx: async (taskId: string) => {
    const response = await api.get(`/download/${taskId}`, {
      responseType: 'blob',
    });
    return response.data;
  },

  // Project endpoints
  getProjects: async (): Promise<Project[]> => {
    const response = await api.get('/projects');
    const data = response.data;
    // Backend returns PaginatedResponse { items, total, ... }
    if (Array.isArray(data)) return data;
    if (data?.items) return data.items;
    return [];
  },

  getProject: async (projectId: string): Promise<Project> => {
    const response = await api.get(`/projects/${projectId}`);
    return response.data;
  },

  deleteProject: async (projectId: string) => {
    const response = await api.delete(`/projects/${projectId}`);
    return response.data;
  },

  // Billing endpoints
  getBalance: async () => {
    const response = await api.get('/billing/balance');
    return response.data;
  },

  createPayment: async (amount: number) => {
    const response = await api.post('/payments/create', { amount });
    return response.data;
  },
};