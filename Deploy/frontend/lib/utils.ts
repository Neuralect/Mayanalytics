// ========================================
// UTILITY FUNCTIONS
// ========================================

import { ReportSchedule } from '@/types';

/**
 * Convert local time to UTC time for storage
 */
export function convertLocalTimeToUTC(localTime: string): string {
  if (!localTime) return '09:00';
  
  try {
    const [hours, minutes] = localTime.split(':').map(Number);
    const localDate = new Date();
    localDate.setHours(hours, minutes, 0, 0);
    
    const utcHours = localDate.getUTCHours();
    const utcMinutes = localDate.getUTCMinutes();
    
    return `${String(utcHours).padStart(2, '0')}:${String(utcMinutes).padStart(2, '0')}`;
  } catch (error) {
    console.error('Error converting local time to UTC:', error);
    return localTime;
  }
}

/**
 * Convert UTC time to local time for display
 */
export function convertUTCToLocalTime(utcTime: string): string {
  if (!utcTime) return '09:00';
  
  try {
    const [hours, minutes] = utcTime.split(':').map(Number);
    const now = new Date();
    const utcDate = new Date(Date.UTC(
      now.getFullYear(),
      now.getMonth(),
      now.getDate(),
      hours,
      minutes,
      0
    ));
    
    const localHours = utcDate.getHours();
    const localMinutes = utcDate.getMinutes();
    
    return `${String(localHours).padStart(2, '0')}:${String(localMinutes).padStart(2, '0')}`;
  } catch (error) {
    console.error('Error converting UTC to local time:', error);
    return utcTime;
  }
}

/**
 * Parse report schedule from string or object
 */
export function parseReportScheduleObject(scheduleStr: string | object | null): ReportSchedule | null {
  if (!scheduleStr || scheduleStr === 'N/A') return null;
  
  try {
    if (typeof scheduleStr === 'object') {
      const schedule = scheduleStr as ReportSchedule;
      if (schedule.time) {
        schedule.time = convertUTCToLocalTime(schedule.time);
      }
      return schedule;
    }
    
    const schedule: ReportSchedule = JSON.parse(scheduleStr as string);
    if (schedule.time) {
      schedule.time = convertUTCToLocalTime(schedule.time);
    }
    return schedule;
  } catch {
    return {
      frequency: 'daily',
      time: '09:00'
    };
  }
}

/**
 * Format report schedule for display
 */
export function formatReportSchedule(scheduleStr: string | object | null): string {
  if (!scheduleStr || scheduleStr === 'N/A') return 'N/A';
  
  try {
    const schedule = typeof scheduleStr === 'object' 
      ? scheduleStr as ReportSchedule
      : JSON.parse(scheduleStr as string) as ReportSchedule;
    
    const displayTime = schedule.time ? convertUTCToLocalTime(schedule.time) : '09:00';
    
    switch (schedule.frequency) {
      case 'daily':
        return `Giornaliero alle ${displayTime}`;
      case 'weekly':
        const days = ['Dom', 'Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab'];
        return `Settimanale - ${days[schedule.day_of_week || 0]} alle ${displayTime}`;
      case 'monthly':
        return `Mensile - giorno ${schedule.day_of_month || 1} alle ${displayTime}`;
      default:
        return String(scheduleStr);
    }
  } catch {
    return String(scheduleStr) || 'N/A';
  }
}

/**
 * Get role badge class for styling
 */
export function getRoleBadgeClass(role: string): string {
  switch (role) {
    case 'SuperAdmin': return 'bg-red-100 text-red-800';
    case 'Reseller': return 'bg-blue-100 text-blue-800';
    case 'Admin': return 'bg-yellow-100 text-yellow-800';
    default: return 'bg-gray-100 text-gray-800';
  }
}

