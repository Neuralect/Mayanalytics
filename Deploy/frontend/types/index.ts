// ========================================
// TYPES DEFINITIONS
// ========================================

export type UserRole = 'SuperAdmin' | 'Reseller' | 'Admin' | 'User';

export interface User {
  user_id: string;
  tenant_id?: string;
  email: string;
  name?: string;
  role: UserRole;
  xml_endpoint?: string;
  xml_token?: string;
  report_enabled?: boolean;
  report_schedule?: string;
  report_email?: string;
  created_at?: string;
}

export interface Tenant {
  tenant_id: string;
  name: string;
  admin_email?: string;  // Optional - admin can be created separately
  admin_name?: string;
  status?: string;
  created_at?: string;
}

export interface Reseller {
  user_id: string;
  email: string;
  name?: string;
  role: 'Reseller';
  assigned_tenants?: string[];
  assigned_tenants_count?: number;
  created_at?: string;
}

export interface SuperAdmin {
  user_id: string;
  email: string;
  name?: string;
  role: 'SuperAdmin';
  created_at?: string;
}

export interface ReportSchedule {
  frequency: 'daily' | 'weekly' | 'monthly';
  time: string;
  day_of_week?: number;
  day_of_month?: number;
}

export interface CreateResellerInput {
  name: string;
  email: string;
  password: string;
}

export interface CreateSuperAdminInput {
  name: string;
  email: string;
  password: string;
}

export interface CreateTenantInput {
  name: string;
}

export interface CreateUserInput {
  name: string;
  email: string;
  xml_endpoint: string;
  xml_token?: string;
  report_schedule?: string;
  report_email?: string;
}

export interface UpdateUserInput {
  name?: string;
  xml_endpoint?: string;
  xml_token?: string;
  report_enabled?: boolean;
  report_schedule?: string;
  report_email?: string;
}

export interface AssignTenantInput {
  reseller_id: string;
  tenant_id: string;
}

export interface ResellerOrganization {
  org_id: string;
  name: string;
  description?: string;
  users?: string[];
  users_count?: number;
  tenants?: string[];
  tenants_count?: number;
  created_at?: string;
  created_by?: string;
}

export interface CreateResellerOrganizationInput {
  name: string;
  description?: string;
}

export interface AssignUserToOrganizationInput {
  user_id: string;
}

export interface AssignTenantToOrganizationInput {
  tenant_id: string;
}

export interface CreateTenantAdminInput {
  email: string;
  name: string;
  password: string;
}

export interface ApiResponse<T = any> {
  message?: string;
  error?: string;
  [key: string]: any;
}

