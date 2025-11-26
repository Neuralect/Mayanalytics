'use client';

import { useState } from 'react';

export interface FilterOption {
  label: string;
  value: string;
}

export interface SearchAndFilterProps {
  searchPlaceholder?: string;
  searchValue: string;
  onSearchChange: (value: string) => void;
  filters?: {
    label: string;
    key: string;
    options: FilterOption[];
    value: string;
    onChange: (value: string) => void;
  }[];
  showFilters?: boolean;
  onToggleFilters?: () => void;
}

export default function SearchAndFilter({
  searchPlaceholder = 'Cerca...',
  searchValue,
  onSearchChange,
  filters = [],
  showFilters = false,
  onToggleFilters,
}: SearchAndFilterProps) {
  const hasFilters = filters.length > 0;

  return (
    <div className="mb-6 space-y-4">
      <div className="flex flex-col md:flex-row gap-4 items-start md:items-center">
        {/* Search Bar */}
        <div className="flex-1 w-full md:w-auto">
          <div className="relative">
            <input
              type="text"
              placeholder={searchPlaceholder}
              value={searchValue}
              onChange={(e) => onSearchChange(e.target.value)}
              className="input pr-10"
            />
            <svg
              className="absolute right-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
          </div>
        </div>

        {/* Toggle Filters Button */}
        {hasFilters && onToggleFilters && (
          <button
            onClick={onToggleFilters}
            className="btn btn-secondary btn-small flex items-center gap-2"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"
              />
            </svg>
            {showFilters ? 'Nascondi Filtri' : 'Mostra Filtri'}
          </button>
        )}
      </div>

      {/* Filters Panel */}
      {hasFilters && showFilters && (
        <div className="card bg-gray-50 p-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filters.map((filter) => (
              <div key={filter.key}>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  {filter.label}
                </label>
                <select
                  value={filter.value}
                  onChange={(e) => filter.onChange(e.target.value)}
                  className="input py-2"
                >
                  {filter.options.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

