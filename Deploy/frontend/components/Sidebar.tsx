'use client';

import { useAuth } from '@/contexts/AuthContext';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

export default function Sidebar() {
  const { user, selectedTenantId } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // Don't show sidebar on login/forgot password pages
  const shouldShowSidebar = user && pathname !== '/' && !pathname?.includes('forgot-password');

  useEffect(() => {
    // Set data attribute for CSS
    if (shouldShowSidebar) {
      document.body.setAttribute('data-sidebar-visible', 'true');
    } else {
      document.body.removeAttribute('data-sidebar-visible');
    }
  }, [shouldShowSidebar]);

  // Close mobile menu when route changes
  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [pathname]);

  if (!shouldShowSidebar) return null;

  // If in tenant context, show only Dashboard
  // Otherwise show all menu items for SuperAdmin/Reseller
  const allMenuItems = [
    { path: '/dashboard', label: 'Dashboard' },
    { path: '/reseller', label: 'Reseller' },
    { path: '/tenants', label: 'Tenants' },
    { path: '/statistiche', label: 'Statistiche' },
    { path: '/impostazioni', label: 'Impostazioni' },
  ];

  const menuItems = selectedTenantId 
    ? [{ path: '/dashboard', label: 'Dashboard' }]
    : allMenuItems;

  const isActive = (path: string) => {
    return pathname === path || pathname?.startsWith(path + '/');
  };

  const handleNavigation = (path: string) => {
    router.push(path);
  };

  return (
    <>
      {/* Mobile menu button */}
      <button
        onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
        className="lg:hidden fixed top-3 left-3 sm:top-4 sm:left-4 z-[60] bg-[#113357] text-white p-2 rounded-lg shadow-lg"
        aria-label="Toggle menu"
      >
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          {isMobileMenuOpen ? (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          ) : (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          )}
        </svg>
      </button>

      {/* Mobile overlay */}
      {isMobileMenuOpen && (
        <div
          className="lg:hidden fixed inset-0 bg-black bg-opacity-50 z-[55]"
          onClick={() => setIsMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div className={`fixed left-0 top-0 h-full w-72 bg-[#113357] text-white flex flex-col z-[55] transition-transform duration-300 ${
        isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
      }`}>
      {/* Logo Section */}
      <div className="p-6">
        <div className="relative">
          <img 
            src="/images/logo.svg" 
            alt="SeteraAI VoiceNote" 
            className="w-full h-auto scale-125"
          />
        </div>
        <div className="mt-3 mx-4 h-px bg-[#286291]"></div>
      </div>

      {/* Navigation Menu */}
      <nav className="flex-1 py-4 overflow-visible">
        {menuItems.map((item) => {
          const active = isActive(item.path);
          return (
            <button
              key={item.path}
              onClick={() => handleNavigation(item.path)}
              className={`w-full px-6 py-3 text-left flex items-center transition-all relative group overflow-visible ${
                active
                  ? 'text-white'
                  : 'text-gray-300 hover:text-white'
              }`}
            >
              {/* Background color layer */}
              {active ? (
                <div className="absolute inset-0 bg-[#0881aa] z-0"></div>
              ) : (
                <div className="absolute inset-0 opacity-0 group-hover:opacity-100 bg-[#1a3f5f] transition-opacity z-0"></div>
              )}
              
              {/* SVG layer - MUST be above background color */}
              {active && (
                <div 
                  className="absolute inset-0 z-[5] pointer-events-none"
                  style={{
                    backgroundImage: 'url("/svg/menu-detail.svg")',
                    backgroundSize: 'cover',
                    backgroundPosition: 'center',
                    backgroundRepeat: 'no-repeat',
                    mixBlendMode: 'normal'
                  }}
                ></div>
              )}
              <div 
                className={`absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity z-[5] pointer-events-none ${active ? 'hidden' : ''}`}
                style={{
                  backgroundImage: 'url("/svg/menu-detail.svg")',
                  backgroundSize: 'cover',
                  backgroundPosition: 'center',
                  backgroundRepeat: 'no-repeat',
                  mixBlendMode: 'normal'
                }}
              ></div>
              
              <span className="font-medium relative z-10">{item.label}</span>
              {active && (
                <div className="absolute left-[calc(100%+2px)] top-0 bottom-0 w-0 h-0 border-l-[18px] border-l-[#0881aa] border-t-[24px] border-t-transparent border-b-[24px] border-b-transparent z-[60] pointer-events-none"></div>
              )}
            </button>
          );
        })}
      </nav>

      </div>
    </>
  );
}

