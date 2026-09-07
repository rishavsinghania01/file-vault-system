import axios, { AxiosProgressEvent } from 'axios';
import { FileItem, FileStatsData, PaginatedResponse, UploadResponse } from '../types/file';

export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
const TOKEN_STORAGE_KEY = 'file-vault-tokens';

export interface AuthTokens {
  access: string;
  refresh: string;
  username?: string;
}

export const getAuthTokens = (): AuthTokens | null => {
  const value = localStorage.getItem(TOKEN_STORAGE_KEY);
  if (!value) return null;
  try {
    return JSON.parse(value) as AuthTokens;
  } catch {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    return null;
  }
};

export const setAuthTokens = (tokens: AuthTokens | null) => {
  if (tokens) localStorage.setItem(TOKEN_STORAGE_KEY, JSON.stringify(tokens));
  else localStorage.removeItem(TOKEN_STORAGE_KEY);
};

export const api = axios.create({ baseURL: API_BASE_URL });
api.interceptors.request.use((config) => {
  const token = getAuthTokens()?.access;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export const login = async (username: string, password: string): Promise<AuthTokens> => {
  const { data } = await api.post<AuthTokens>('/auth/token/', { username, password });
  const tokens = { ...data, username };
  setAuthTokens(tokens);
  return tokens;
};

export const register = async (username: string, password: string): Promise<AuthTokens> => {
  const { data } = await api.post<AuthTokens>('/auth/register/', { username, password });
  setAuthTokens(data);
  return data;
};

export interface ListFilesParams {
  page?: number;
  page_size?: number;
  search?: string;
  file_type?: string;
  min_size?: number;
  max_size?: number;
  start_date?: string;
  end_date?: string;
  ordering?: string;
}

export const listFiles = async (params: ListFilesParams): Promise<PaginatedResponse<FileItem>> => {
  const { data } = await api.get<PaginatedResponse<FileItem>>('/files/', { params });
  return data;
};

export const semanticSearch = async (
  query: string,
  filters: ListFilesParams
): Promise<PaginatedResponse<FileItem>> => {
  const { data } = await api.get<PaginatedResponse<FileItem>>('/files/semantic-search/', {
    params: { ...filters, page: undefined, search: undefined, q: query },
  });
  return data;
};

export const uploadFile = async (
  file: File,
  onProgress?: (percent: number) => void
): Promise<UploadResponse> => {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await api.post<UploadResponse>('/files/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event: AxiosProgressEvent) => {
      if (onProgress && event.total) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    },
  });
  return data;
};

export const deleteFile = async (id: string): Promise<void> => {
  await api.delete(`/files/${id}/`);
};

export const downloadFile = async (id: string, filename: string): Promise<void> => {
  const response = await api.get(`/files/${id}/download/`, { responseType: 'blob' });
  const url = URL.createObjectURL(response.data);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
};

export const getStats = async (): Promise<FileStatsData> => {
  const { data } = await api.get<FileStatsData>('/files/stats/');
  return data;
};

export const getFileTypes = async (): Promise<string[]> => {
  const { data } = await api.get<string[]>('/files/file_types/');
  return data;
};
