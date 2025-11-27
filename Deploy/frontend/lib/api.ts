// ========================================
// API UTILITIES
// ========================================

import { API_BASE_URL } from './config';
import { ApiResponse } from '@/types';

export async function apiCall<T = any>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = API_BASE_URL + endpoint;
  
  // Get token from localStorage or sessionStorage
  const token = typeof window !== 'undefined' 
    ? localStorage.getItem('cognito_id_token') || sessionStorage.getItem('cognito_id_token')
    : null;

  const config: RequestInit = {
    headers: {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...options.headers,
    },
    ...options,
  };

  try {
    const response = await fetch(url, config);
    const data: ApiResponse<T> = await response.json();

    if (!response.ok) {
      throw new Error(data.error || `HTTP ${response.status}: ${response.statusText}`);
    }

    return data as T;
  } catch (error) {
    console.error('❌ API Error:', { endpoint, error });
    throw error;
  }
}

// ========================================
// API ENDPOINTS
// ========================================

// Profile
export const profileApi = {
  get: () => apiCall<{ user: any }>('/profile'),
  update: (data: any) => apiCall('/profile', { method: 'PUT', body: JSON.stringify(data) }),
};

// Tenants
export const tenantsApi = {
  list: () => apiCall<{ tenants: any[] }>('/tenants'),
  get: (tenantId: string) => apiCall<{ tenant: any }>(`/tenants/${tenantId}`),
  create: (data: any) => apiCall('/tenants', { method: 'POST', body: JSON.stringify(data) }),
  delete: (tenantId: string) => apiCall(`/tenants/${tenantId}`, { method: 'DELETE' }),
  createAdmin: (tenantId: string, data: any) => 
    apiCall(`/tenants/${tenantId}/admin`, { method: 'POST', body: JSON.stringify(data) }),
};

// Users
export const usersApi = {
  list: (tenantId: string) => apiCall<{ users: any[] }>(`/tenants/${tenantId}/users`),
  get: (userId: string) => apiCall<{ user: any }>(`/users/${userId}`),
  create: (tenantId: string, data: any) => 
    apiCall(`/tenants/${tenantId}/users`, { method: 'POST', body: JSON.stringify(data) }),
  update: (userId: string, data: any) => 
    apiCall(`/users/${userId}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (userId: string) => apiCall(`/users/${userId}`, { method: 'DELETE' }),
};

// Resellers
export const resellersApi = {
  list: () => apiCall<{ resellers: any[] }>('/resellers'),
  create: (data: any) => apiCall('/resellers', { method: 'POST', body: JSON.stringify(data) }),
  delete: (resellerId: string) => apiCall(`/resellers/${resellerId}`, { method: 'DELETE' }),
  getTenants: (resellerId: string) => 
    apiCall<{ tenants: any[]; reseller_id: string; count: number }>(`/resellers/${resellerId}/tenants`),
  assignTenant: (data: any) => 
    apiCall('/resellers/assign-tenant', { method: 'POST', body: JSON.stringify(data) }),
  removeTenant: (data: any) => 
    apiCall('/resellers/remove-tenant', { method: 'POST', body: JSON.stringify(data) }),
};

// SuperAdmins
export const superadminsApi = {
  list: () => apiCall<{ superadmins: any[] }>('/superadmins'),
  create: (data: any) => apiCall('/superadmins', { method: 'POST', body: JSON.stringify(data) }),
  delete: (superadminId: string) => apiCall(`/superadmins/${superadminId}`, { method: 'DELETE' }),
};

// Reports
export const reportsApi = {
  listAll: () => apiCall<{ reports: any[] }>('/reports'),
  listTenant: (tenantId: string) => apiCall<{ reports: any[] }>(`/tenants/${tenantId}/reports`),
  listUser: (userId: string) => apiCall<{ reports: any[] }>(`/users/${userId}/reports`),
};

