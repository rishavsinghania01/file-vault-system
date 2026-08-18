import axios, { AxiosProgressEvent } from 'axios';
import { FileItem, FileStatsData, PaginatedResponse, UploadResponse } from '../types/file';

export const API_BASE_URL =
  process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

export const api = axios.create({ baseURL: API_BASE_URL });

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

export const listFiles = async (
  params: ListFilesParams
): Promise<PaginatedResponse<FileItem>> => {
  const { data } = await api.get<PaginatedResponse<FileItem>>('/files/', { params });
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

export const getStats = async (): Promise<FileStatsData> => {
  const { data } = await api.get<FileStatsData>('/files/stats/');
  return data;
};

export const getFileTypes = async (): Promise<string[]> => {
  const { data } = await api.get<string[]>('/files/file_types/');
  return data;
};

export const getDownloadUrl = (id: string): string =>
  `${API_BASE_URL}/files/${id}/download/`;
