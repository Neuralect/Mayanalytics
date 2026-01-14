'use client';

export default function LicenzePage() {
  return (
    <div className="dashboard-content min-h-screen flex justify-center items-center">
      <div className="content-card max-w-2xl w-full text-center py-12">
        <div className="mb-6">
          <div className="inline-flex items-center justify-center w-24 h-24 rounded-full bg-gradient-to-br from-[#286291] to-[#113357] mb-6">
            <svg className="w-12 h-12 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          </div>
        </div>
        <h2 className="text-3xl font-bold text-gray-800 mb-3">Licenze</h2>
        <p className="text-lg text-gray-600 mb-2">Sezione in fase di sviluppo</p>
        <p className="text-sm text-gray-500">Stiamo lavorando per offrirti una gestione completa delle licenze e dei permessi.</p>
      </div>
    </div>
  );
}

