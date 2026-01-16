'use client';

import { useAuth } from '@/contexts/AuthContext';
import { useState, useRef, useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { tenantsApi } from '@/lib/api';
import { Tenant } from '@/types';

export default function UserProfileDropdown() {
  const { user, logout, selectedTenantId, setSelectedTenantId } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [isOpen, setIsOpen] = useState(false);
  const [currentTenant, setCurrentTenant] = useState<Tenant | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Don't show on login/forgot password pages
  const shouldShow = user && pathname !== '/' && !pathname?.includes('forgot-password');

  useEffect(() => {
    if (selectedTenantId) {
      loadTenantInfo();
    } else {
      setCurrentTenant(null);
    }
  }, [selectedTenantId]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  const loadTenantInfo = async () => {
    if (!selectedTenantId) return;
    try {
      const response = await tenantsApi.get(selectedTenantId);
      if (response.tenant) {
        setCurrentTenant(response.tenant);
      }
    } catch (error) {
      console.error('Error loading tenant info:', error);
    }
  };

  const handleBackToGlobal = () => {
    setSelectedTenantId(null);
    setIsOpen(false);
  };

  if (!shouldShow) return null;

  const getInitials = () => {
    if (user.name) {
      return user.name
        .split(' ')
        .map(n => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2);
    }
    return user.email[0].toUpperCase();
  };

  const isSuperAdmin = user.role === 'SuperAdmin';

  return (
    <div className="fixed top-3 right-3 sm:top-4 sm:right-4 lg:top-12 lg:right-8 z-50 flex items-center gap-2 lg:gap-3" ref={dropdownRef}>
      {/* Search bar - Hidden on mobile */}
      <div className="hidden md:flex relative items-center h-12 w-[200px]">
        <input
          type="text"
          className="w-full h-full px-3.5 py-2.5 bg-white border border-gray-200 rounded-lg text-sm text-gray-700 transition-all shadow-[0_0_8px_rgba(99,102,241,0.15),0_0_16px_rgba(99,102,241,0.1)] focus:outline-none focus:border-[#0881aa] focus:shadow-[0_0_12px_rgba(99,102,241,0.25),0_0_24px_rgba(99,102,241,0.15),0_0_0_3px_rgba(8,129,170,0.1)] placeholder:text-gray-400"
          placeholder="Cerca..."
        />
      </div>
      
      {/* User profile button */}
      <div className="relative">
        <div className="bg-white/90 backdrop-blur-sm rounded-lg shadow-xl px-3.5 py-2.5 h-12 relative overflow-hidden">
          {/* Fog effect at edges */}
          <div className="absolute inset-0 pointer-events-none">
            <div className="absolute inset-y-0 left-0 w-7 bg-gradient-to-r from-white to-transparent"></div>
            <div className="absolute inset-y-0 right-0 w-7 bg-gradient-to-l from-white to-transparent"></div>
          </div>
          <button
            onClick={() => setIsOpen(!isOpen)}
            className="flex items-center gap-3 text-gray-800 relative z-10 h-full"
          >
            <div className="w-8 h-8 rounded-full bg-orange-500 flex items-center justify-center text-white relative overflow-hidden">
              {/* Person character icon */}
              <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="16" cy="16" r="16" fill="#FF6B35"/>
                <g transform="translate(8, 6)">
                  {/* Capelli */}
                  <path d="M8 2 Q6 0 4 2 Q2 4 2 6 Q2 8 4 8 Q6 10 8 8 Q10 8 12 6 Q12 4 10 2 Q8 0 8 2 Z" fill="#1E3A8A"/>
                  {/* Faccia */}
                  <ellipse cx="8" cy="10" rx="4" ry="5" fill="#FED7AA"/>
                  {/* Top/Corpo */}
                  <path d="M4 14 Q4 16 6 16 Q8 16 10 16 Q12 16 12 14" stroke="#14B8A6" strokeWidth="2" fill="none"/>
                  <rect x="5" y="14" width="6" height="4" fill="#14B8A6" rx="1"/>
                </g>
              </svg>
            </div>
            <div className="text-left min-w-[120px]">
              <div className="text-sm font-medium text-gray-800 leading-tight">
                {user.name || user.email.split('@')[0]}
              </div>
              <div className="text-xs text-gray-600 leading-tight">{user.role.toLowerCase()}</div>
            </div>
          </button>
        </div>

        {isOpen && (
          <div className="absolute right-0 lg:right-0 mt-2 w-64 max-w-[calc(100vw-0.75rem)] sm:max-w-[calc(100vw-1rem)] bg-white rounded-lg shadow-xl border border-gray-200 z-50">
          <div className="p-4 border-b border-gray-200">
            <div className="font-semibold text-gray-800">{user.name || 'User'}</div>
            <div className="text-sm text-gray-600 mt-1">{user.email}</div>
            {selectedTenantId && (
              <div className="mt-2">
                <div className="text-xs text-gray-500">Tenant ID</div>
                <div className="text-sm font-medium text-gray-800">
                  {currentTenant?.name || selectedTenantId}
                </div>
              </div>
            )}
          </div>

          <div className="p-2">
            {isSuperAdmin && selectedTenantId && (
              <button
                onClick={handleBackToGlobal}
                className="w-full text-left px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
              >
                Torna alla Dashboard SuperAdmin
              </button>
            )}
            <button
              onClick={() => {
                logout();
                setIsOpen(false);
                router.push('/');
              }}
              className="w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors mt-1"
            >
              Logout
            </button>
          </div>
        </div>
      )}
      </div>
    </div>
  );
}

